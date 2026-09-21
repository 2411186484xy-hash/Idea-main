"""L2 feedback: verdict ledger, coverage supply gate, read-only V1 import."""

from __future__ import annotations

import json
from pathlib import Path

from pipelines import feedback, runs


def test_add_feedback_validates(frozen_clock):
    ok = feedback.add_feedback("v1-cand-01", "accept", "gap confirmed")
    assert ok["ok"] and ok["verdict"] == "accept"
    assert not feedback.add_feedback("x", "MAYBE", "r")["ok"]
    assert not feedback.add_feedback("x", "reject", "  ")["ok"]
    rows = feedback.load_feedback()
    assert rows[0]["at"] == "2026-09-21T12:00:00Z"


def test_add_feedback_traces_run(frozen_clock):
    runs.start("weekly", "WEEKLYRUN-20260921-120000")
    feedback.add_feedback("v1-cand-01", "uncertain", "need data", run_id="WEEKLYRUN-20260921-120000")
    assert runs.load("WEEKLYRUN-20260921-120000").trace[-1]["event"] == "FEEDBACK"


def test_reject_feeds_failure_ledger(frozen_clock):
    from pipelines import store

    feedback.add_feedback("doomed-idea", "accept", "solid evidence")
    assert store.read_jsonl(store.failure_ledger_path()) == []
    feedback.add_feedback("doomed-idea", "reject", "prior work exists")
    ledger = store.read_jsonl(store.failure_ledger_path())
    assert len(ledger) == 1 and ledger[0]["slug"] == "doomed-idea"
    assert ledger[0]["stage"] == "verdict" and ledger[0]["lesson"] == "prior work exists"


def test_supply_gate_first_boot_then_ratio(frozen_clock):
    cold = feedback.stats()
    assert cold["bootstrap"] and cold["supply_open"]
    assert feedback.check_supply()["open"]
    feedback.add_feedback("v1-a", "uncertain", "pending researcher")
    assert not feedback.check_supply()["open"]
    feedback.add_feedback("v1-b", "accept", "confirmed by researcher")
    gate = feedback.check_supply()
    assert gate["open"] and "1/2" in gate["reason"]


def _write_decision(root: Path, dirname: str, doc: dict | None) -> None:
    target = root / dirname
    target.mkdir(parents=True, exist_ok=True)
    if doc is not None:
        (target / "researcher-decision.json").write_text(
            json.dumps(doc), encoding="utf-8"
        )


def _snapshot(root: Path) -> dict[str, float]:
    return {
        str(p.relative_to(root)): p.stat().st_mtime_ns
        for p in root.rglob("*")
        if p.is_file()
    }


def test_import_v1_readonly_and_idempotent(tmp_path, frozen_clock):
    delivery = tmp_path / "E-Idea"
    _write_decision(
        delivery,
        "Some Idea",
        {
            "candidate_id": "CAND-01",
            "decision": "researcher_confirmed",
            "approved_by": "researcher",
            "note": "champion",
            "decided_at": "2026-08-16T00:00:00Z",
            "portfolio": {"tier": "champion"},
        },
    )
    _write_decision(
        delivery,
        "Other Idea",
        {"candidate_id": "C4", "decision": "auto_approved", "decided_at": "2026-08-23T12:30:10Z"},
    )
    _write_decision(delivery, "Empty Idea", None)
    before = _snapshot(delivery)
    first = feedback.import_v1(delivery)
    assert first["ok"] and first["scanned"] == 2 and first["imported"] == 2
    assert len(first["skipped"]) == 1 and first["skipped"][0]["dir"] == "Empty Idea"
    assert _snapshot(delivery) == before, "import must never write under the delivery root"
    rows = {r["slug"]: r for r in feedback.load_feedback()}
    assert rows["cand-01"]["verdict"] == "accept"
    assert rows["v1-c4"]["verdict"] == "uncertain"
    assert "awaiting researcher backfill" in rows["v1-c4"]["reason"]
    second = feedback.import_v1(delivery)
    assert second["imported"] == 0 and len(feedback.load_feedback()) == 2


def test_import_v1_missing_root():
    result = feedback.import_v1(Path("/nonexistent-root-idea-os"))
    assert not result["ok"] and "not found" in result["error"]
