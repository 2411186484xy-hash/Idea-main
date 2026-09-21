"""L3 report: session-brief first screen (pure read)."""

from __future__ import annotations

from pipelines import report, runs


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
