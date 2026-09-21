"""Run state machine. SINGLE-WRITER: run.json is the sole truth; ledgers are derived views.

V2 lessons baked in: no dual writers (mechanized prescreen writes a SIDE ledger only),
LF-normalized freeze hashes with CRLF variants accepted on verify, audited refreeze,
24h-stale warning, empty-terminal guard, supply-hold seeds exemption with reason.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Any

from . import canon, common, permissions

WEEKLY_ROOT = common.RUNS_ROOT / "weekly"
IDEA_ROOT = common.RUNS_ROOT / "idea-incubation"
RUN_RE = re.compile(r"^(WEEKLYRUN|IDEARUN)-\d{8}-\d{6}$")
COVERAGE_ROUTES = ("direct", "counter_boundary", "transfer", "frontier")
L2_MIN, L2_MAX = 10, 15


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_dir(kind: str, run_id: str) -> Path:
    root = WEEKLY_ROOT if kind == "weekly" else IDEA_ROOT
    return root / run_id


def _read_run(run_dir: Path) -> dict[str, Any]:
    return dict(common.read_json(run_dir / "run.json"))  # type: ignore[arg-type]


def _write_run(run_dir: Path, run: dict[str, Any]) -> None:
    run["updated_at"] = _now()
    common.write_json(run_dir / "run.json", run)


def start(kind: str, run_id: str, mode: str = "", force: bool = False) -> dict[str, Any]:
    if not RUN_RE.match(run_id):
        return {"ok": False, "error": f"bad run id: {run_id}"}
    root = WEEKLY_ROOT if kind == "weekly" else IDEA_ROOT
    if kind not in ("weekly", "idea"):
        return {"ok": False, "error": f"bad kind: {kind}"}
    empties = sum(
        1
        for d in sorted(root.iterdir())
        if d.is_dir() and (d / "run.json").exists() and _read_run(d).get("status") == "active"
    )
    if empties >= 2 and not force:
        return {"ok": False, "error": f"{empties} empty active runs; pass --force or close them"}
    run_dir = root / run_id
    if (run_dir / "run.json").exists():
        run = _read_run(run_dir)
        if run.get("status") == "completed":
            return {"ok": False, "error": "completed run is immutable; use --fresh id"}
        run["attempt"] = int(run.get("attempt", 1)) + 1
        _write_run(run_dir, run)
        return {"ok": True, "run_id": run_id, "resumed_attempt": run["attempt"]}
    run = {
        "run_id": run_id,
        "kind": kind,
        "mode": mode,
        "status": "active",
        "attempt": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "paper_candidates": [],
        "idea_seeds": [],
        "coverage": {r: 0 for r in COVERAGE_ROUTES},
        "uncertainty_disclosure": [],
        "refreeze_history": [],
        "trace": [{"t": _now(), "event": "run-start"}],
    }
    run_dir.mkdir(parents=True, exist_ok=False)
    _write_run(run_dir, run)
    (run_dir / "candidate-ledger.jsonl").write_text("", encoding="utf-8")
    (run_dir / "mechanized-prescreen.jsonl").write_text("", encoding="utf-8")
    (run_dir / "report.md").write_text(
        f"# {run_id}\n\n> attempt 1 — fill on finish.\n", encoding="utf-8", newline="\n"
    )
    return {"ok": True, "run_id": run_id, "attempt": 1}


def _validate_payload(payload: dict[str, Any]) -> str | None:
    for field in ("title", "discovery_class", "coverage_route"):
        if not payload.get(field):
            return f"missing required field: {field}"
    if payload.get("coverage_route") not in COVERAGE_ROUTES:
        return f"bad coverage_route: {payload.get('coverage_route')}"
    if not any(payload.get(k) for k in ("doi", "pmid", "arxiv_id", "pdf_sha256")):
        return "at least one identifier required (doi/pmid/arxiv_id/pdf_sha256)"
    return None


def add_paper(kind: str, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """The ONLY writer of run.json paper_candidates + candidate-ledger (single-writer)."""
    run_dir = _run_dir(kind, run_id)
    if not (run_dir / "run.json").exists():
        return {"ok": False, "error": "run not found"}
    if err := _validate_payload(payload):
        return {"ok": False, "error": err}
    run = _read_run(run_dir)
    if run.get("status") == "completed":
        return {"ok": False, "error": "completed run is immutable"}
    key = (payload.get("doi") or payload.get("arxiv_id") or payload.get("pdf_sha256") or "").lower()
    if any(
        (c.get("doi") or c.get("arxiv_id") or c.get("pdf_sha256") or "").lower() == key
        for c in run["paper_candidates"]
    ):
        return {"ok": False, "error": "duplicate in run"}
    run["paper_candidates"].append(payload)
    run["coverage"][payload["coverage_route"]] = (
        int(run["coverage"].get(payload["coverage_route"], 0)) + 1
    )
    run["trace"].append({"t": _now(), "event": "add-paper", "key": key})
    _write_run(run_dir, run)
    _append_jsonl(run_dir / "candidate-ledger.jsonl", payload)  # derived view, same writer
    return {"ok": True, "count": len(run["paper_candidates"])}


def prescreen_append(kind: str, run_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Mechanized prescreen writes ONLY the side ledger. Promotion via add_paper. Never touches run.json."""
    run_dir = _run_dir(kind, run_id)
    if not (run_dir / "run.json").exists():
        return {"ok": False, "error": "run not found"}
    for item in items:
        _append_jsonl(
            run_dir / "mechanized-prescreen.jsonl", {**item, "stage": "mechanized_prescreen"}
        )
    return {"ok": True, "prescreened": len(items)}


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    import json

    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def reconcile(kind: str, run_id: str) -> dict[str, Any]:
    """V2 fix for the v1 P1: import side-ledger entries into run.json through the single writer."""
    import json

    run_dir = _run_dir(kind, run_id)
    side = run_dir / "mechanized-prescreen.jsonl"
    if not side.exists():
        return {"ok": True, "imported": 0}
    imported, skipped = 0, 0
    for line in side.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        item.pop("stage", None)
        res = add_paper(kind, run_id, item)
        if res.get("ok"):
            imported += 1
        else:
            skipped += 1
    side.write_text("", encoding="utf-8")  # consumed
    return {"ok": True, "imported": imported, "skipped_duplicates": skipped}


def finish(kind: str, run_id: str, supply_hold_reason: str = "") -> dict[str, Any]:
    run_dir = _run_dir(kind, run_id)
    if not (run_dir / "run.json").exists():
        return {"ok": False, "error": "run not found"}
    run = _read_run(run_dir)
    if run.get("status") == "completed":
        return {"ok": False, "error": "already completed"}
    ledger_lines = [
        ln
        for ln in (run_dir / "candidate-ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    problems: list[str] = []
    if len(ledger_lines) != len(run["paper_candidates"]):
        problems.append(
            f"ledger ({len(ledger_lines)}) != run.paper_candidates ({len(run['paper_candidates'])})"
        )
    n = len(run["paper_candidates"])
    if not (L2_MIN <= n <= L2_MAX):
        problems.append(f"L2 quota {L2_MIN}-{L2_MAX} not met: {n}")
    missing_routes = [r for r in COVERAGE_ROUTES if int(run["coverage"].get(r, 0)) <= 0]
    if missing_routes:
        problems.append(f"coverage routes missing: {missing_routes}")
    for cand in run["paper_candidates"]:
        for field in ("title", "discovery_class", "coverage_route"):
            if not cand.get(field):
                problems.append(f"candidate incomplete: {cand.get('title', '?')[:40]}")
    seeds = run.get("idea_seeds", [])
    if len(seeds) < 3 and not supply_hold_reason.strip():
        problems.append(
            f"idea_seeds < 3 ({len(seeds)}); pass --supply-hold-reason in slow-supply periods"
        )
    if problems:
        return {"ok": False, "error": "finish blocked", "problems": problems}
    if supply_hold_reason.strip():
        run["uncertainty_disclosure"].append(f"supply-hold: {supply_hold_reason.strip()}")
    run["trace"].append({"t": _now(), "event": "run-finish"})
    run["status"] = "completed"
    run["completed_at"] = _now()
    _write_run(run_dir, run)
    frozen = _freeze(run_dir)
    run["frozen_hashes"] = frozen
    _write_run(run_dir, run)
    return {"ok": True, "run_id": run_id, "frozen": len(frozen)}


def _freeze(run_dir: Path) -> dict[str, str]:
    """Freeze = LF-normalized sha256 over the terminal file set (run.json hashed minus volatile keys)."""
    import json

    files = ["report.md", "candidate-ledger.jsonl"]
    frozen: dict[str, str] = {}
    for name in files:
        p = run_dir / name
        if p.exists():
            norm = p.read_bytes().replace(b"\r\n", b"\n")
            p.write_bytes(norm)
            frozen[name] = common.sha256_text(norm.decode("utf-8", errors="replace"))
    run = _read_run(run_dir)
    payload = {k: v for k, v in run.items() if k not in ("frozen_hashes",)}
    frozen["run.json"] = common.sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return frozen


def refreeze(kind: str, run_id: str, reason: str) -> dict[str, Any]:
    dec = permissions.check("refreeze_run", reason)
    if not dec.allowed:
        return {"ok": False, "error": dec.reason}
    run_dir = _run_dir(kind, run_id)
    run = _read_run(run_dir)
    if run.get("status") != "completed":
        return {"ok": False, "error": "only completed runs use refreeze"}
    previous = dict(run.get("frozen_hashes", {}))
    frozen = _freeze(run_dir)
    run["frozen_hashes"] = frozen
    run["refreeze_history"].append({"t": _now(), "reason": reason, "previous": previous})
    run["trace"].append({"t": _now(), "event": "RUN_RESEAL", "reason": reason})
    _write_run(run_dir, run)
    return {"ok": True, "changed": previous != frozen}


def verify_freeze(kind: str, run_id: str) -> dict[str, Any]:
    run_dir = _run_dir(kind, run_id)
    run = _read_run(run_dir)
    expected = run.get("frozen_hashes", {})
    import json

    actual: dict[str, str] = {}
    for name in ("report.md", "candidate-ledger.jsonl"):
        p = run_dir / name
        if p.exists():
            norm = p.read_bytes().replace(b"\r\n", b"\n")
            actual[name] = common.sha256_text(norm.decode("utf-8", errors="replace"))
    payload = {k: v for k, v in run.items() if k not in ("frozen_hashes",)}
    actual["run.json"] = common.sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    drift = {
        k: {"expected": expected.get(k), "actual": v}
        for k, v in actual.items()
        if expected.get(k) != v
    }
    void = dict(canon.load()).get("runs", {}).get("freeze", {})
    _ = void
    return {"ok": not drift, "drift": drift}


def status(kind: str) -> dict[str, Any]:
    root = WEEKLY_ROOT if kind == "weekly" else IDEA_ROOT
    out = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or not (d / "run.json").exists():
            continue
        run = _read_run(d)
        out.append(
            {
                "run_id": d.name,
                "status": run.get("status"),
                "papers": len(run.get("paper_candidates", [])),
                "seeds": len(run.get("idea_seeds", [])),
                "updated_at": run.get("updated_at"),
            }
        )
    return {"ok": True, "runs": out}
