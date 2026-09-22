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
    assert cold["coverage"]["total"] == 0 and cold["coverage"]["supply_open"]
    assert cold["lessons"] == []
    assert any("knowledge empty" in todo for todo in cold["todos"])
    assert any("fresh ledger" in todo for todo in cold["todos"])
    feedback.add_feedback("v1-a", "accept", "confirmed")
    warm = report.session_brief()
    assert warm["coverage"]["decided"] == 1 and warm["coverage"]["supply_open"]
    assert not any("supply closed" in todo for todo in warm["todos"])


def test_query_brief_flags_repeat_queries(frozen_clock):
    runs.start("weekly", "WEEKLYRUN-20260921-120000")
    first = report.query_brief("crispr off-target", "WEEKLYRUN-20260921-120000")
    assert first["ok"] and len(first["perspectives"]) == 4
    assert not any(p["duplicate"] for p in first["perspectives"])
    run = runs.load("WEEKLYRUN-20260921-120000")
    run.query_log.append({"query": "crispr off-target", "backend": "openalex",
                          "at": "2026-09-21T12:00:00Z"})
    runs.save(run)
    second = report.query_brief("crispr off-target", "WEEKLYRUN-20260921-120000")
    direct = next(p for p in second["perspectives"] if p["route"] == "direct")
    assert direct["duplicate"] and len(direct["hits"]) == 1
    assert report.query_brief("", None)["ok"] is False
    assert report.query_brief("x", "WEEKLYRUN-00000000-000000")["ok"] is False


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


def test_deepread_brief_is_blind():
    pack = report.deepread_brief("doi:10.1/x", "full text here")
    assert pack["ok"] and pack["blind"] is True
    assert pack["writer"]["text_md"] == "full text here"
    assert pack["verifier"]["claims_to_check"] == []
    assert pack["verifier"]["sees_writer_notes"] is False
    assert "notes" not in pack["verifier"]
    assert report.deepread_brief("", "text")["ok"] is False
    assert report.deepread_brief("doi:10.1/x", "  ")["ok"] is False


def test_query_brief_topic_family(frozen_clock):
    brief = report.query_brief("", None, "single-shot-sl")
    assert brief["ok"] and brief["topic"]["id"] == "single-shot-sl"
    assert brief["base"].startswith("fringe projection profilometry")
    routes = [p["route"] for p in brief["perspectives"]]
    assert routes[:4] == ["direct", "counter_boundary", "transfer", "frontier"]
    transfers = [r for r in routes if r.startswith("transfer:")]
    assert len(transfers) == 4  # one explicit query per transfer_pair in the pack
    first_transfer = next(p for p in brief["perspectives"] if p["route"].startswith("transfer:"))
    assert first_transfer["query"].endswith("fringe projection profilometry")
    explicit = report.query_brief("explicit query", None, "single-shot-sl")
    assert explicit["base"] == "explicit query" and len(explicit["perspectives"]) == 8
    assert report.query_brief("", None, "ghost-topic")["ok"] is False


def test_session_brief_lists_topics(frozen_clock):
    brief = report.session_brief()
    ids = [t["id"] for t in brief["topics"]]
    assert "single-shot-sl" in ids
    entry = next(t for t in brief["topics"] if t["id"] == "single-shot-sl")
    assert entry["status"] == "active" and entry["name"]
