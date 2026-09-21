"""L2 papers: registration gates, retraction veto, screen-rank + stop criterion."""

from __future__ import annotations

from pipelines import papers, runs

RUN = "WEEKLYRUN-20260921-120000"


def _payload(**over):
    base = {
        "title": "T",
        "identifiers": {"doi": "10.1/x"},
        "source_backend": "openalex",
        "abstract": "a",
        "abstract_sha256": "0" * 64,
    }
    base.update(over)
    return base


def test_add_paper_gates_and_traces(frozen_clock):
    runs.start("weekly", RUN)
    assert papers.add_paper(RUN, _payload())["ok"]
    run = runs.load(RUN)
    assert run.paper_candidates[0].screen_status == "pending"
    assert run.coverage["direct"] == 1
    assert run.trace[-1]["event"] == "PAPER_ADD"
    dup = papers.add_paper(RUN, _payload())
    assert not dup["ok"] and "duplicate" in dup["error"]
    assert not papers.add_paper("WEEKLYRUN-20260921-999999", _payload())["ok"]


def test_retraction_veto(frozen_clock):
    runs.start("weekly", RUN)
    flagged = _payload(
        identifiers={"doi": "10.1/bad"},
        retraction={"status": "flagged", "checked_backends": ["openalex_is_retracted"],
                    "checked_at": "t"},
    )
    result = papers.add_paper(RUN, flagged)
    assert not result["ok"] and "retraction veto" in result["error"]
    run = runs.load(RUN)
    assert run.trace[-1]["event"] == "RETRACT_HIT"
    assert run.paper_candidates == []


def test_pdf_flag_deferred(frozen_clock):
    runs.start("weekly", RUN)
    result = papers.add_paper(RUN, _payload(), pdf="some.pdf")
    assert not result["ok"] and "M2b" in result["error"]


def test_screen_rank_orders_and_stops(frozen_clock):
    runs.start("weekly", RUN)
    for i in range(5):
        assert papers.add_paper(RUN, _payload(identifiers={"doi": f"10.1/weak{i}"}))["ok"]
    strong = _payload(identifiers={"doi": "10.1/strong"}, cited_by_count=500, year=2026,
                      evidence={"one_line_evidence": "e", "evidence_role": "r"})
    mid = _payload(identifiers={"doi": "10.1/mid"}, cited_by_count=10, year=2025)
    assert papers.add_paper(RUN, strong)["ok"]
    assert papers.add_paper(RUN, mid)["ok"]
    result = papers.screen_rank(RUN)
    assert result["ok"]
    keys = [r["paper_key"] for r in result["ranked"]]
    assert keys[0] == "doi:10.1/strong" and keys[1] == "doi:10.1/mid"
    assert all(r["screen_status"] == "ranked" for r in result["ranked"])
    assert result["stop_hint"] is True  # 5 consecutive candidates below stop_score
    assert runs.load(RUN).trace[-1]["event"] == "SCREEN"


def test_screen_rank_no_stop_when_tail_strong(frozen_clock):
    runs.start("weekly", RUN)
    for i in range(3):
        payload = _payload(identifiers={"doi": f"10.1/s{i}"}, cited_by_count=100)
        assert papers.add_paper(RUN, payload)["ok"]
    result = papers.screen_rank(RUN)
    assert result["stop_hint"] is False


def test_screen_rank_vetoes_confirmed_after_add(frozen_clock):
    runs.start("weekly", RUN)
    papers.add_paper(RUN, _payload())
    run = runs.load(RUN)
    run.paper_candidates[0].retraction = {
        "status": "confirmed", "checked_backends": ["crossref_update_to"], "checked_at": "t"}
    runs.save(run)
    result = papers.screen_rank(RUN)
    assert result["ranked"] == [] and len(result["vetoed"]) == 1


def test_set_screen_status(frozen_clock):
    runs.start("weekly", RUN)
    papers.add_paper(RUN, _payload())
    assert papers.set_screen_status(RUN, "doi:10.1/x", "selected")["ok"]
    assert runs.load(RUN).paper_candidates[0].screen_status == "selected"
    assert not papers.set_screen_status(RUN, "doi:10.1/x", "maybe")["ok"]
    assert not papers.set_screen_status(RUN, "doi:10.1/nope", "rejected")["ok"]
