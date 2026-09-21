"""L3 report: session-brief first screen, four blocks (pure read)."""

from __future__ import annotations

from pipelines import feedback, report, runs, store


def test_session_brief_cold_and_active(frozen_clock):
    cold = report.session_brief()
    assert cold["ok"]
    assert cold["knowledge"]["claims"] == 0
    assert cold["active_runs"] == []
    runs.start("weekly", "WEEKLYRUN-20260921-120000")
    warm = report.session_brief()
    assert warm["active_runs"][0]["run_id"] == "WEEKLYRUN-20260921-120000"
    assert warm["stale_warnings"] == []
    frozen_clock.advance(hours=25)
    assert len(report.session_brief()["stale_warnings"]) == 1


def test_session_brief_four_blocks(frozen_clock):
    cold = report.session_brief()
    assert cold["coverage"]["total"] == 0 and not cold["coverage"]["supply_open"]
    assert cold["lessons"] == []
    assert any("knowledge empty" in todo for todo in cold["todos"])
    feedback.add_feedback("v1-a", "accept", "confirmed")
    warm = report.session_brief()
    assert warm["coverage"]["decided"] == 1 and warm["coverage"]["supply_open"]
    assert not any("supply closed" in todo for todo in warm["todos"])


def test_session_brief_lessons_and_todos(frozen_clock):
    for i in range(7):
        store.append_jsonl(
            store.failure_ledger_path(),
            {
                "schema_version": 3,
                "slug": f"idea-{i}",
                "stage": "screen",
                "reason": f"reason {i}",
                "lesson": f"lesson {i}",
                "at": "2026-09-21T12:00:00Z",
            },
        )
    feedback.add_feedback("v1-a", "uncertain", "pending")
    brief = report.session_brief()
    assert len(brief["lessons"]) == 5
    assert brief["lessons"][-1]["lesson"] == "lesson 6"
    assert any("backfill 1 researcher verdicts" in todo for todo in brief["todos"])
    assert any("supply closed" in todo for todo in brief["todos"])
