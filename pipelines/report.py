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
