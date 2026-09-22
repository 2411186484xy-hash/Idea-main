"""L2 papers: registration gates, retraction veto, screen-rank + stop criterion."""

from __future__ import annotations

from pipelines import papers, runs

RUN = "WEEKLYRUN-20260921-120000"
GOOD_PDF = b"%PDF-1.4\n" + b"0" * 100_100 + b"\n%%EOF\n"


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


def test_pdf_archive_mirrors_with_sha(frozen_clock, tmp_path):
    runs.start("weekly", RUN)
    src = tmp_path / "paper.pdf"
    src.write_bytes(GOOD_PDF)
    result = papers.add_paper(RUN, _payload(), pdf=str(src))
    assert result["ok"] and result["archive"]["sha_match"] is True
    from pipelines import canon, store

    lib = canon.paper_root() / "library" / "doi_10.1_x" / "paper.pdf"
    mirror = canon.paper_mirror_root() / "library" / "doi_10.1_x" / "paper.pdf"
    assert lib.is_file() and mirror.is_file()
    assert store.sha256_file(lib) == store.sha256_file(mirror)
    dup = papers.add_paper(RUN, _payload(), pdf=str(src))
    assert not dup["ok"] and "duplicate" in dup["error"]


def test_pdf_archive_refuses_forbidden_and_missing(frozen_clock):
    runs.start("weekly", RUN)
    assert not papers.add_paper(RUN, _payload(), pdf="nope.pdf")["ok"]
    hit = papers.add_paper(RUN, _payload(), pdf="E:\\Project\\x.pdf")
    assert not hit["ok"] and "forbidden" in hit["error"]
    assert runs.load(RUN).paper_candidates == []


def test_pdf_archive_gate_rejects_incomplete(frozen_clock, tmp_path):
    runs.start("weekly", RUN)
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4 tiny")
    result = papers.add_paper(RUN, _payload(), pdf=str(bad))
    assert not result["ok"] and "integrity gate" in result["error"]
    assert runs.load(RUN).paper_candidates == []


def test_batch_adds_and_replays_idempotently(frozen_clock, tmp_path):
    from pipelines import canon

    runs.start("weekly", RUN)
    pdf = tmp_path / "b3.pdf"
    pdf.write_bytes(GOOD_PDF)
    batch = [
        _payload(identifiers={"doi": "10.1/b1"}),
        _payload(identifiers={"doi": "10.1/b2"}),
        {**_payload(identifiers={"doi": "10.1/b3"}), "pdf": str(pdf)},
    ]
    first = papers.add_batch(RUN, batch)
    assert first["ok"] and first["added"] == 3 and first["count"] == 3
    assert (canon.paper_root() / "library" / "doi_10.1_b3" / "b3.pdf").is_file()
    replay = papers.add_batch(RUN, batch)
    assert not replay["ok"] and replay["added"] == 0 and replay["failed"] == 3
    assert replay["count"] == 3  # idempotent in state: replay changes nothing
    assert all("duplicate" in r["error"] for r in replay["results"])
    assert not papers.add_batch(RUN, [])["ok"]
    assert not papers.add_batch("WEEKLYRUN-20260921-999999", batch)["ok"]


def test_screen_rank_stable_over_twenty(frozen_clock):
    runs.start("weekly", RUN)
    for i in range(20):
        cited = 500 - i * 23
        assert papers.add_paper(RUN, _payload(
            identifiers={"doi": f"10.1/p{i:02d}"}, cited_by_count=cited,
            year=2026 if i % 3 == 0 else 2010))["ok"]
    first = [r["paper_key"] for r in papers.screen_rank(RUN)["ranked"]]
    second = [r["paper_key"] for r in papers.screen_rank(RUN)["ranked"]]
    assert first == second and len(first) == 20
    assert first[0] == "doi:10.1/p00"


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


def test_stoppers_are_named_and_independent():
    assert papers.stop_consecutive_low([0, 0, 0, 0, 0], 2, 5)["triggered"]
    assert papers.stop_consecutive_low([0, 0, 5, 0, 0], 2, 5)["triggered"] is False
    assert papers.stop_all_low([0, 0, 0, 0, 0], 2, 5)["triggered"]
    assert papers.stop_all_low([0, 0, 0], 2, 5)["triggered"] is False
    assert papers.stop_all_low([], 2, 5)["triggered"] is False


def test_screen_rank_reports_stoppers_and_balance(frozen_clock):
    runs.start("weekly", RUN)
    for i in range(5):
        assert papers.add_paper(RUN, _payload(identifiers={"doi": f"10.1/w{i}"}))["ok"]
    out = papers.screen_rank(RUN)
    names = {s["name"]: s["triggered"] for s in out["stoppers"]}
    assert names == {"consecutive_low": True, "all_low": True}
    assert out["stop_note"] is not None and out["coverage_balance"] == {"direct": 5}
