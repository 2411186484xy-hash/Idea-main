"""L2 runs: state machine, absorb-then-delete, session-log remnant, stale."""

from __future__ import annotations

from pipelines import runs, store

RUN = "WEEKLYRUN-20260921-120000"


def _session_log_rows():
    return store.read_jsonl(store.session_log_path())


def test_start_creates_active_run(frozen_clock):
    result = runs.start("weekly", RUN)
    assert result["ok"] and result["attempt"] == 1
    run = runs.load(RUN)
    assert run.status == "active"
    assert run.trace[0]["event"] == "RUN_START"


def test_double_start_rejected(frozen_clock):
    assert runs.start("weekly", RUN)["ok"]
    again = runs.start("weekly", RUN)
    assert not again["ok"] and "already active" in again["error"]


def test_finish_deletes_run_and_logs_one_line(frozen_clock):
    runs.start("weekly", RUN)
    before = len(_session_log_rows())
    result = runs.finish(RUN)
    assert result["ok"]
    assert result["papers"] == 0 and result["claims"] == 0 and result["ideas"] == 0
    assert runs.load(RUN) is None
    assert not store.run_dir(RUN).exists()
    after = _session_log_rows()
    assert len(after) == before + 1
    assert after[-1]["run_id"] == RUN and after[-1]["kind"] == "weekly"


def test_finish_twice_rejected(frozen_clock):
    runs.start("weekly", RUN)
    runs.finish(RUN)
    second = runs.finish(RUN)
    assert not second["ok"] and "not found" in second["error"]


def test_partial_resume_absorb_cycle(frozen_clock):
    runs.start("weekly", RUN)
    partial = runs.finish(RUN, partial_note="supply hold this week")
    assert partial["ok"] and partial["status"] == "partial"
    run = runs.load(RUN)
    assert run.gap_note == "supply hold this week"
    assert "gap: supply hold this week" in run.uncertainty_disclosure
    # plain finish on partial is rejected
    plain = runs.finish(RUN)
    assert not plain["ok"] and "--absorb" in plain["error"]
    # resume bumps attempt
    resumed = runs.start("weekly", RUN, resume=True)
    assert resumed["ok"] and resumed["attempt"] == 2
    assert runs.load(RUN).trace[-1]["event"] == "RUN_RESUME"
    # abandon-close with gap note
    absorbed = runs.finish(RUN, absorb_note="not enough evidence")
    assert absorbed["ok"]
    assert runs.load(RUN) is None
    rows = _session_log_rows()
    assert rows[-1]["gap_note"] == "not enough evidence"


def test_finish_counts_papers_and_claims(frozen_clock):
    from pipelines import claims, papers, store

    runs.start("weekly", RUN)
    store.write_json_atomic(
        store.cache_dir() / "extracts" / "by-key" / "doi_10.1_x.json",
        {"pages": [{"page_no": 2, "raw_text": "q lands here"}]},
    )
    payload = {
        "title": "T",
        "identifiers": {"doi": "10.1/x"},
        "source_backend": "openalex",
        "abstract": "a",
        "abstract_sha256": "0" * 64,
    }
    assert papers.add_paper(RUN, payload)["ok"]
    claims.add_claim(
        {
            "paper_key": "doi:10.1/x",
            "topic": "t",
            "text": "c",
            "quote": "q",
            "page_anchor": 2,
            "verifier_verdict": "CONFIRMED",
        },
        run_id=RUN,
    )
    result = runs.finish(RUN, absorb_note="wrap")
    assert result["papers"] == 1
    assert result["claims"] == 1
    row = _session_log_rows()[-1]
    assert row["papers"] == 1 and row["claims"] == 1


def test_stale_warning_after_24h(frozen_clock):
    runs.start("weekly", RUN)
    assert runs.stale_warnings() == []
    frozen_clock.advance(hours=25)
    warnings = runs.stale_warnings()
    assert len(warnings) == 1 and RUN in warnings[0]


def test_bad_run_id_rejected(frozen_clock):
    result = runs.start("weekly", "NOT-A-RUN")
    assert not result["ok"]


def test_kind_prefix_mismatch_rejected(frozen_clock):
    result = runs.start("weekly", "IDEARUN-20260921-120000")
    assert not result["ok"] and "prefix/kind" in result["error"]


def test_finish_below_quota_soft_discloses_gap(frozen_clock):
    """Complete channel never blocks on quota (soft); the gap is disclosed."""
    runs.start("weekly", RUN)
    result = runs.finish(RUN)
    assert result["ok"] and result["quota_gap"] == 10


def test_finish_meeting_quota_has_no_gap(frozen_clock):
    from pipelines import papers

    runs.start("weekly", RUN)
    for i in range(10):
        payload = {
            "title": f"T{i}",
            "identifiers": {"doi": f"10.1/x{i}"},
            "source_backend": "openalex",
            "abstract": "a",
            "abstract_sha256": "0" * 64,
        }
        assert papers.add_paper(RUN, payload)["ok"]
    result = runs.finish(RUN)
    assert result["ok"] and "quota_gap" not in result
