"""L3 validate: cold start green, corruption pinpointed, strict absorbs warnings."""

from __future__ import annotations

import json

from pipelines import runs, store, validate


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_cold_start_strict_green():
    result = validate.validate(strict=True)
    assert result["ok"], result
    assert result["errors"] == [] and result["warnings"] == []


def test_corrupt_ledger_line_pinpointed():
    _write(store.claims_path(), '{"id": "CLM-20260921-001", "schema_version": 3}\nnot-json\n')
    result = validate.validate()
    assert not result["ok"]
    assert any("not valid JSON" in e for e in result["errors"])
    assert any("missing verbatim quote" in e for e in result["errors"])


def test_unknown_schema_version_flagged():
    _write(store.claims_path(), json.dumps({"id": "x", "schema_version": 99}) + "\n")
    result = validate.validate()
    assert any("unknown/missing schema_version" in e for e in result["errors"])


def test_session_log_missing_keys():
    _write(store.session_log_path(), '{"run_id": "x"}\n')
    result = validate.validate()
    assert any("session-log" in e for e in result["errors"])


def test_strict_fails_on_stale_warning(frozen_clock):
    runs.start("weekly", "WEEKLYRUN-20260921-120000")
    frozen_clock.advance(hours=25)
    assert validate.validate()["ok"]
    assert not validate.validate(strict=True)["ok"]
