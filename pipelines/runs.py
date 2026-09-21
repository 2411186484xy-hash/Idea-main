"""L2 runs: run state machine with absorb-then-delete lifecycle.

A run is temporary working state. On close (finish or absorb) the products
already live in the knowledge layer / delivery area, so the run file is
DELETED and session-log.jsonl keeps exactly one line as the only remnant.
No freeze hashes, no side ledgers, no refreeze — single writer, atomic writes.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from . import canon, contracts, store
from .contracts import TRACE_EVENTS


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **extra}


def load(run_id: str) -> contracts.Run | None:
    path = store.run_dir(run_id) / "run.json"
    if not path.exists():
        return None
    try:
        return store.from_dict("Run", dict(store.read_json(path)))
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError(f"run file corrupt: {run_id}: {exc}") from exc


def save(run: contracts.Run) -> None:
    run.updated_at = store.now()
    store.write_json_atomic(store.run_dir(run.run_id) / "run.json", store.to_dict(run))


def append_trace(run: contracts.Run, event: str, detail: str | None = None) -> None:
    if event not in TRACE_EVENTS:
        raise ValueError(f"unknown trace event: {event}")
    entry: dict[str, str] = {"at": store.now(), "event": event}
    if detail:
        entry["detail"] = detail
    run.trace.append(entry)


def start(kind: str, run_id: str, resume: bool = False) -> dict[str, Any]:
    prefix_ok = run_id.startswith("WEEKLYRUN-") or run_id.startswith("IDEARUN-")
    if not prefix_ok:
        return _fail(f"bad run_id (need WEEKLYRUN-/IDEARUN- prefix): {run_id}")
    existing = load(run_id)
    if existing is None:
        try:
            run = contracts.Run(
                run_id=run_id,
                kind=kind,
                status="active",
                attempt=1,
                created_at=store.now(),
                updated_at=store.now(),
            )
        except ValueError as exc:
            return _fail(f"bad run: {exc}")
        append_trace(run, "RUN_START")
        save(run)
        return {"ok": True, "run_id": run_id, "attempt": 1, "resumed": False}
    if existing.status == "active":
        return _fail(f"run already active: {run_id}")
    if existing.status == "completed":
        return _fail(f"terminal run file leaked (should have been deleted): {run_id}")
    if existing.status == "partial":
        if not resume:
            return _fail(f"run is partial; use --resume to continue or --absorb to close: {run_id}")
        existing.attempt += 1
        existing.status = "active"
        append_trace(existing, "RUN_RESUME", f"attempt {existing.attempt}")
        save(existing)
        return {"ok": True, "run_id": run_id, "attempt": existing.attempt, "resumed": True}
    return _fail(f"unknown status: {existing.status}")


def _run_claims_count(run: contracts.Run) -> int:
    """Claims whose paper_key belongs to this run (read-only ledger scan)."""
    paper_keys = {c.paper_key for c in run.paper_candidates}
    if not paper_keys:
        return 0
    return sum(
        1
        for row in store.read_jsonl(store.claims_path())
        if row.get("paper_key") in paper_keys
    )


def _parse_ts(ts: str) -> _dt.datetime:
    return _dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.UTC)


def finish(
    run_id: str, partial_note: str | None = None, absorb_note: str | None = None
) -> dict[str, Any]:
    run = load(run_id)
    if run is None:
        return _fail(f"run not found: {run_id}")
    if run.status == "completed":
        return _fail(f"run already terminal: {run_id}")
    if partial_note is not None and absorb_note is not None:
        return _fail("--partial and --absorb are mutually exclusive")
    if partial_note is not None:
        if not partial_note.strip():
            return _fail("--partial requires a non-empty gap note")
        run.status = "partial"
        run.gap_note = partial_note.strip()
        run.uncertainty_disclosure.append(f"gap: {partial_note.strip()}")
        save(run)
        return {
            "ok": True,
            "run_id": run_id,
            "status": "partial",
            "note": "resumable with run-start --resume",
        }
    if run.status == "partial" and absorb_note is None:
        return _fail(
            f"partial run needs --resume (continue) or --absorb <note> (abandon): {run_id}"
        )
    gap_note = absorb_note.strip() if absorb_note and absorb_note.strip() else None
    if gap_note:
        run.uncertainty_disclosure.append(f"absorbed gap: {gap_note}")
    # L2 quota dual channel (canon quotas.l2_per_run): the complete channel never
    # blocks on quota (V1 G3.2: quotas are soft); a shortfall is disclosed, while
    # the partial channel carries an explicit gap note instead.
    quota_min = int(list(canon.value("quotas.l2_per_run"))[0])
    quota_gap = max(0, quota_min - len(run.paper_candidates))
    if quota_gap:
        run.uncertainty_disclosure.append(
            f"quota gap: {len(run.paper_candidates)}/{quota_min} L2 "
            "(soft: completed below canon quotas.l2_per_run floor)"
        )
    run.status = "completed"
    run.completed_at = store.now()
    summary = {
        "at": store.now(),
        "run_id": run_id,
        "kind": run.kind,
        "papers": len(run.paper_candidates),
        "claims": _run_claims_count(run),
        "ideas": len(run.idea_seeds),
    }
    if gap_note:
        summary["gap_note"] = gap_note
    if quota_gap:
        summary["quota_gap"] = quota_gap
    store.append_jsonl(store.session_log_path(), summary)
    store.delete_tree(store.run_dir(run_id))
    return {"ok": True, "run_id": run_id, **{k: v for k, v in summary.items() if k != "at"}}


def active_runs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in store.list_run_dirs():
        run = load(d.name)
        if run is None:
            continue
        out.append(
            {
                "run_id": run.run_id,
                "kind": run.kind,
                "status": run.status,
                "attempt": run.attempt,
                "papers": len(run.paper_candidates),
                "seeds": len(run.idea_seeds),
                "coverage": run.coverage,
                "updated_at": run.updated_at,
            }
        )
    return out


def stale_warnings() -> list[str]:
    """Active, zero candidates, untouched longer than canon limits.stale_hours."""
    stale_hours = int(canon.value("limits.stale_hours"))
    cutoff = _parse_ts(store.now()) - _dt.timedelta(hours=stale_hours)
    warnings: list[str] = []
    for d in store.list_run_dirs():
        run = load(d.name)
        if run is None or run.status != "active" or run.paper_candidates:
            continue
        if _parse_ts(run.updated_at) < cutoff:
            warnings.append(
                f"stale active run (no candidates, >{stale_hours}h): {run.run_id}; "
                "absorb or delete it"
            )
    return warnings
