"""L3 report: structured task packs for the in-session model (pure read).

The CLI never does cognition; it renders briefs. session-brief is the first
screen: purpose, active runs, knowledge-layer counts, stale warnings. The
coverage-first redesign lands in M1.6.
"""

from __future__ import annotations

from typing import Any

from . import canon, runs, store


def _count_jsonl(path) -> int:
    return len(store.read_jsonl(path))


def session_brief() -> dict[str, Any]:
    return {
        "ok": True,
        "purpose": str(canon.value("purpose")),
        "active_runs": runs.active_runs(),
        "knowledge": {
            "claims": _count_jsonl(store.claims_path()),
            "feedback": _count_jsonl(store.feedback_path()),
            "failure_ledger": _count_jsonl(store.failure_ledger_path()),
            "idea_pool": (
                len(store.read_json(store.idea_pool_path()))
                if store.idea_pool_path().exists()
                else 0
            ),
            "session_log": _count_jsonl(store.session_log_path()),
        },
        "stale_warnings": runs.stale_warnings(),
    }
