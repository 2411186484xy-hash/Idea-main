"""Idea gates: corpus 3+1+1, 6-dim card HOLD, feedback loop -> failure ledger."""

from pipelines import common, idea


def test_corpus_gate():
    assert idea.check_corpus_gate({"direct_fulltext": 3, "recent": 1, "counter_or_boundary": 1})[
        "ok"
    ]
    bad = idea.check_corpus_gate({"direct_fulltext": 2, "recent": 1, "counter_or_boundary": 1})
    assert not bad["ok"] and "direct_fulltext" in bad["missing"]


def test_quality_card_hold():
    scores = {
        "novelty": 4,
        "rigor": 4,
        "feasibility": 4,
        "clarity": 4,
        "data_availability": 1.5,
        "venue_fit": 4,
    }
    res = idea.score_card(scores)
    assert res["ok"] and res["hold"] and res["low_dims"] == ["data_availability"]


def test_feedback_reject_writes_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(idea, "POOL_PATH", tmp_path / "pool.json")
    monkeypatch.setattr(idea, "FEEDBACK_PATH", tmp_path / "fb.jsonl")
    monkeypatch.setattr(idea, "FAILURE_PATH", tmp_path / "fail.json")
    assert idea.add_candidate({"slug": "demo-x", "title": "Demo"})["ok"]
    assert idea.record_feedback("demo-x", "reject", "换皮既有工作")["ok"]
    stats = idea.feedback_stats()
    assert stats["reject"] == 1 and stats["coverage"] == 1.0
    ledger = list(common.read_json(tmp_path / "fail.json"))
    assert ledger[0]["stage"] == "researcher_rejection"


def test_publish_slug_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DELIVERY_ROOT", tmp_path)
    first = idea.publish("slug-a", "core")
    assert first["ok"] and len(first["files"]) == 4
    assert not idea.publish("slug-a", "core")["ok"]
