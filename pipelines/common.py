"""Single-sourced constants + deterministic IO. All paths/names exist exactly once here."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# --- identity (mirror of governance/workflow_authority.json#identity; canon wins on conflict)
OPERATOR = "opencode"
ID_PREFIX = "OPENCODE-"
ZOTERO_SIDEBAR_ROOT = "paper"
ZOTERO_COLLECTIONS = (
    "01_recent-week",
    "02_researcher-reviewed-for-followup",
    "03_researcher-E-drive",
    "04_all-opencode-found",
)
DELIVERY_ROOT = Path("E:/Idea")
PAPER_ROOT = Path("E:/Paper")
PAPER_MIRROR_ROOT = Path("E:/Backup/Paper")
FORBIDDEN_INPUT_ROOTS = ("E:/Project", "trae-input", "C:/Users/User/Documents/3D重建科研")

RUNS_ROOT = REPO_ROOT / "runs"
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"
GOVERNANCE_ROOT = REPO_ROOT / "governance"


def ensure_ssl_cert_env() -> None:
    """Code-level certifi fallback (V2 lesson: user-level SSL_CERT_FILE dies with the session/venv)."""
    if os.environ.get("SSL_CERT_FILE") and Path(os.environ["SSL_CERT_FILE"]).exists():
        return
    try:
        import certifi

        bundle = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle)
    except ImportError:
        pass


def disable_proxy_for_local() -> None:
    for key in ("NO_PROXY", "no_proxy"):
        existing = os.environ.get(key, "")
        if "23119" not in existing and "localhost" not in existing:
            os.environ[key] = (existing + ",localhost,127.0.0.1,::1").strip(",")


def write_json(path: Path, payload: object) -> None:
    """Canonical JSON write: UTF-8, LF only, trailing newline. All frozen-hash inputs go through here."""
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file_variants(path: Path) -> set[str]:
    """Accept CRLF/LF/missing-trailing-newline variants (V2 lesson: freeze drift false alarms)."""
    raw = path.read_bytes()
    variants = {raw, raw.replace(b"\r\n", b"\n")}
    stripped = raw.replace(b"\r\n", b"\n").rstrip(b"\n")
    variants.add(stripped + b"\n")
    variants.add(stripped)
    return {hashlib.sha256(v).hexdigest() for v in variants}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_forbidden(path_str: str) -> bool:
    lowered = path_str.replace("\\", "/").lower()
    return any(
        lowered.startswith(root.replace("\\", "/").lower()) for root in FORBIDDEN_INPUT_ROOTS
    )
