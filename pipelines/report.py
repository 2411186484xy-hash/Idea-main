"""L3 report: structured task packs for the in-session model (pure read).

The CLI never does cognition; it renders briefs. session-brief is the first
screen with four blocks (M1.6): feedback coverage first, active run states,
lesson digest from the failure ledger, and pending todos. Legacy keys
(purpose/knowledge/stale_warnings) stay for compatibility.
"""

from __future__ import annotations

from typing import Any

from . import canon, feedback, runs, store

_LESSON_DISPLAY_CAP = 5  # display truncation only, not a governance gate

_QUERY_ROUTES = (
    ("direct", ""),
    ("counter_boundary", " limitations OR counter-evidence OR boundary conditions"),
    ("transfer", " transfer OR analogy OR cross-domain application"),
    ("frontier", " frontier OR emerging OR review"),
)


def query_brief(base: str, run_id: str | None = None) -> dict[str, Any]:
    """M2a: mechanical multi-perspective pack + query_log dedup flags (pure read)."""
    query = (base or "").strip()
    if not query:
        return {"ok": False, "error": "query required"}
    logged: list[dict[str, Any]] = []
    if run_id:
        run = runs.load(run_id)
        if run is None:
            return {"ok": False, "error": f"run not found: {run_id}"}
        logged = list(run.query_log)
    seen: dict[str, list[dict[str, Any]]] = {}
    for entry in logged:
        seen.setdefault(str(entry.get("query", "")).casefold().strip(), []).append(entry)
    perspectives = []
    for route, suffix in _QUERY_ROUTES:
        text = query + suffix
        hits = seen.get(text.casefold().strip(), [])
        perspectives.append({"route": route, "query": text, "duplicate": bool(hits), "hits": hits})
    return {"ok": True, "base": query, "run_id": run_id,
            "perspectives": perspectives, "logged_queries": len(logged)}


def _count_jsonl(path) -> int:
    return len(store.read_jsonl(path))


def _lessons() -> list[dict[str, Any]]:
    rows = store.read_jsonl(store.failure_ledger_path())
    digest: list[dict[str, Any]] = []
    for row in rows[-_LESSON_DISPLAY_CAP:]:
        digest.append(
            {
                "slug": row.get("slug"),
                "stage": row.get("stage"),
                "lesson": row.get("lesson") or row.get("reason"),
                "at": row.get("at"),
            }
        )
    return digest


def _todos(coverage: dict[str, Any], knowledge: dict[str, int]) -> list[str]:
    pending: list[str] = []
    if coverage["pending"]:
        pending.append(
            f"backfill {coverage['pending']} researcher verdicts "
            f"(coverage {coverage['decided']}/{coverage['total']})"
        )
    if not coverage["supply_open"]:
        pending.append(
            f"supply closed (ratio {coverage['ratio']} < {coverage['threshold']}): "
            "no new ideas until coverage recovers"
        )
    for warning in runs.stale_warnings():
        pending.append(f"stale run: {warning}")
    if not knowledge["claims"]:
        pending.append("knowledge empty: run search to seed L2 candidates")
    return pending


def session_brief() -> dict[str, Any]:
    coverage = feedback.stats()
    knowledge = {
        "claims": _count_jsonl(store.claims_path()),
        "feedback": _count_jsonl(store.feedback_path()),
        "failure_ledger": _count_jsonl(store.failure_ledger_path()),
        "idea_pool": (
            len(store.read_json(store.idea_pool_path())) if store.idea_pool_path().exists() else 0
        ),
        "session_log": _count_jsonl(store.session_log_path()),
    }
    return {
        "ok": True,
        "coverage": coverage,
        "active_runs": runs.active_runs(),
        "lessons": _lessons(),
        "todos": _todos(coverage, knowledge),
        "knowledge": knowledge,
        "purpose": str(canon.value("purpose")),
        "stale_warnings": runs.stale_warnings(),
    }
