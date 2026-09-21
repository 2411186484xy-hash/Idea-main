"""L1 store: the ONLY module that touches the filesystem for state.

Owns the record codec (to_dict/from_dict) — everything crossing the disk
boundary is serialized and schema-checked here. Atomic writes (tmp +
os.replace), fsync'd appends, read-back helpers, injectable clock. All roots
are env-overridable (IDEAOS_*) so tests redirect knowledge/runs/E-drive
roots without touching the real machine state.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from collections.abc import Callable
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from . import contracts

REPO_ROOT = Path(__file__).resolve().parent.parent

Clock = Callable[[], "_dt.datetime"]


def _env_path(var: str, default: Path) -> Path:
    override = os.environ.get(var)
    return Path(override) if override else default


def knowledge_root() -> Path:
    return _env_path("IDEAOS_KNOWLEDGE_ROOT", REPO_ROOT / "knowledge")


def runs_root() -> Path:
    return _env_path("IDEAOS_RUNS_ROOT", REPO_ROOT / "runs")


def claims_path() -> Path:
    return knowledge_root() / "corpus-claims.jsonl"


def idea_pool_path() -> Path:
    return knowledge_root() / "idea-pool.json"


def feedback_path() -> Path:
    return knowledge_root() / "feedback.jsonl"


def failure_ledger_path() -> Path:
    return knowledge_root() / "failure-ledger.jsonl"


def session_log_path() -> Path:
    return knowledge_root() / "session-log.jsonl"


def jcr_registry_path() -> Path:
    return knowledge_root() / "jcr-registry.json"


def run_dir(run_id: str) -> Path:
    return runs_root() / run_id


# --- record codec (the disk boundary; schema discipline lives here) --------


def to_dict(record: Any) -> dict[str, Any]:
    """Json-ready dict; None fields dropped, nested records flattened."""
    if is_dataclass(record):
        return {f.name: to_dict(getattr(record, f.name)) for f in fields(record)
                if getattr(record, f.name) is not None}
    if isinstance(record, list):
        return [to_dict(v) for v in record]
    if isinstance(record, dict):
        return {k: to_dict(v) for k, v in record.items()}
    return record


def is_known_schema(data: Any) -> bool:
    """Ledger integrity helper: dict carrying this build's schema_version."""
    return isinstance(data, dict) and data.get("schema_version") == contracts.SCHEMA_VERSION


CONTRACT_TYPES: dict[str, type] = {
    cls.__name__: cls
    for cls in (contracts.Run, contracts.PaperCandidate, contracts.Claim,
                contracts.IdeaCandidate, contracts.Feedback, contracts.FailureEntry,
                contracts.ZoteroManifest, contracts.ReadbackReport)
}


def from_dict(cls_name: str, data: dict[str, Any]) -> Any:
    """Loader: rejects unknown schema_version, then re-validates on construction."""
    version = data.get("schema_version")
    if version != contracts.SCHEMA_VERSION:
        raise ValueError(
            f"unknown schema_version {version!r}; "
            f"this build only accepts {contracts.SCHEMA_VERSION}"
        )
    if cls_name == "Run":
        data = {**data, "paper_candidates": [
            from_dict("PaperCandidate", c) for c in data.get("paper_candidates", [])
        ]}
    return CONTRACT_TYPES[cls_name](**data)


# --- injectable clock -------------------------------------------------------

_clock: Clock | None = None


def set_clock(clock: Clock | None) -> None:
    """Tests inject a frozen clock; production uses real UTC time."""
    global _clock
    _clock = clock


def now() -> str:
    current = _clock() if _clock else _dt.datetime.now(_dt.UTC)
    return current.strftime("%Y-%m-%dT%H:%M:%SZ")


# --- primitives (mutation lives here and nowhere else) ----------------------


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json_atomic(path: Path, payload: Any) -> None:
    """Canonical write: UTF-8, LF, trailing newline, tmp + os.replace + fsync."""
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def append_jsonl(path: Path, record: Any) -> None:
    """Append one jsonl line with fsync (crash-safe ledger)."""
    line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    ensure_dir(path.parent)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def read_jsonl_raw(path: Path) -> list[tuple[int, str]]:
    """(lineno, raw_line) for non-blank lines; validator uses it to pinpoint corruption."""
    if not path.exists():
        return []
    return [(i, ln) for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if ln.strip()]


def delete_tree(path: Path) -> None:
    """Absorb-then-delete lifecycle: only runs.py calls this on run close."""
    import shutil

    shutil.rmtree(path, ignore_errors=False)


def copy_file(src: Path, dst: Path) -> None:
    """Crash-safe copy (tmp + os.replace); the only copy primitive in the repo."""
    import shutil

    ensure_dir(dst.parent)
    tmp = dst.with_name(dst.name + ".tmp")
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def sha256_file(path: Path) -> str:
    """Content hash for archive/mirror integrity checks."""
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dir_exists(path: Path) -> bool:
    return path.is_dir()


def list_run_dirs() -> list[Path]:
    root = runs_root()
    if not root.is_dir():
        return []
    return sorted(d for d in root.iterdir() if d.is_dir())


def read_bytes(path: Path) -> bytes:
    """Raw byte read (pdf port); the only byte-read primitive in the repo."""
    with open(path, "rb") as fh:
        return fh.read()


def read_text(path: Path) -> str:
    """UTF-8 text read (brief inputs); the only text-read primitive in the repo."""
    return path.read_text(encoding="utf-8")


def write_text_atomic(path: Path, text: str) -> None:
    """LF + trailing newline, tmp + os.replace + fsync (delivery docs)."""
    if not text.endswith("\n"):
        text += "\n"
    ensure_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
