"""L2 claims: lint-gated append ledger, auto ids, on-the-fly views."""

from __future__ import annotations

from pipelines import claims, runs

RUN = "WEEKLYRUN-20260921-120000"


def _payload(**over):
    base = {
        "paper_key": "doi:10.1/x",
        "topic": "calibration",
        "text": "the claim",
        "quote": "verbatim",
        "page_anchor": 3,
        "verifier_verdict": "CONFIRMED",
    }
    base.update(over)
    return base


def test_add_claim_appends_and_traces(frozen_clock):
    runs.start("weekly", RUN)
    result = claims.add_claim(_payload(), run_id=RUN)
    assert result["ok"] and result["id"] == "CLM-20260921-001"
    rows = claims.load_claims()
    assert len(rows) == 1 and rows[0]["created_at"] == "2026-09-21T12:00:00Z"
    assert runs.load(RUN).trace[-1]["event"] == "CLAIM_ADD"
    assert claims.add_claim(_payload(quote="another"))["id"] == "CLM-20260921-002"


def test_lint_gates(frozen_clock):
    assert not claims.add_claim(_payload(quote="  "))["ok"]
    assert not claims.add_claim(_payload(page_anchor=0))["ok"]
    assert not claims.add_claim(_payload(verifier_verdict="MAYBE"))["ok"]
    assert not claims.add_claim(_payload(id="CLM-BAD"))["ok"]


def test_duplicate_id_rejected(frozen_clock):
    assert claims.add_claim(_payload(id="CLM-20260921-001"))["ok"]
    dup = claims.add_claim(_payload(id="CLM-20260921-001", quote="other"))
    assert not dup["ok"] and "duplicate" in dup["error"]


def test_page_anchor_coercion(frozen_clock):
    assert claims.add_claim(_payload(page_anchor="7"))["ok"]
    assert claims.load_claims()[-1]["page_anchor"] == 7
    assert not claims.add_claim(_payload(page_anchor="seven"))["ok"]


def test_view_filters(frozen_clock):
    claims.add_claim(_payload(topic="a", verifier_verdict="CONFIRMED"))
    claims.add_claim(_payload(topic="b", verifier_verdict="NOT_FOUND", quote="q2"))
    assert claims.view()["count"] == 2
    assert claims.view(topic="a")["count"] == 1
    assert claims.view(verdict="NOT_FOUND")["count"] == 1
    assert claims.view(paper_key="doi:10.1/x")["count"] == 2
    assert claims.view(topic="a")["topics"] == {"a": 1}


def _opposite_pair_setup():
    claims.add_claim(
        _payload(paper_key="doi:10.1/a", topic="cal", text="holds", quote="holds",
                 verifier_verdict="CONFIRMED")
    )
    claims.add_claim(
        _payload(paper_key="doi:10.1/b", topic="cal", text="fails", quote="fails",
                 verifier_verdict="DEVIATED")
    )


def test_view_verdict_opposite_pairs(frozen_clock):
    _opposite_pair_setup()
    assert claims.view()["pairs"][0]["kind"] == "verdict_opposite"
    same_paper = claims.view(paper_key="doi:10.1/a")
    assert same_paper["pairs"] == []


def test_view_confirmed_vs_not_found_is_opposite(frozen_clock):
    claims.add_claim(_payload(paper_key="doi:10.1/a", verifier_verdict="CONFIRMED"))
    claims.add_claim(
        _payload(paper_key="doi:10.1/b", quote="other", verifier_verdict="NOT_FOUND")
    )
    assert claims.view()["pairs"][0]["kind"] == "verdict_opposite"


def test_view_numeric_conflict_pairs(frozen_clock):
    claims.add_claim(
        _payload(paper_key="doi:10.1/a", topic="err", text="rmse 0.05 mm", quote="0.05",
                 verifier_verdict="CONFIRMED")
    )
    claims.add_claim(
        _payload(paper_key="doi:10.1/b", topic="err", text="rmse 0.5 mm", quote="0.5",
                 verifier_verdict="CONFIRMED")
    )
    pairs = claims.view()["pairs"]
    assert [p["kind"] for p in pairs] == ["numeric_conflict"]
    only = claims.view(pairs_only=True)
    assert only["count"] == 2
    claims.add_claim(
        _payload(paper_key="doi:10.1/c", topic="err", text="rmse 0.5 mm", quote="0.5",
                 verifier_verdict="CONFIRMED")
    )
    same_numbers = [p for p in claims.view()["pairs"] if p["kind"] == "numeric_conflict"]
    assert len(same_numbers) == 2  # a-c still conflicts; b-c shares numbers


def test_view_writes_nothing_to_disk(frozen_clock, tmp_path):
    from pipelines import store

    _opposite_pair_setup()
    before = {str(p) for p in store.knowledge_root().rglob("*")}
    claims.view()
    claims.view(pairs_only=True)
    assert {str(p) for p in store.knowledge_root().rglob("*")} == before


def test_numeric_years_do_not_clash(frozen_clock):
    claims.add_claim(
        _payload(paper_key="doi:10.1/a", topic="yr", text="study 2024 shows gain",
                 quote="2024", verifier_verdict="CONFIRMED")
    )
    claims.add_claim(
        _payload(paper_key="doi:10.1/b", topic="yr", text="study 2025 shows gain",
                 quote="2025", verifier_verdict="CONFIRMED")
    )
    assert claims.view()["pairs"] == []


def test_numeric_unit_mismatch_suppressed(frozen_clock):
    claims.add_claim(
        _payload(paper_key="doi:10.1/a", topic="u", text="error 0.05 mm",
                 quote="0.05 mm", verifier_verdict="CONFIRMED")
    )
    claims.add_claim(
        _payload(paper_key="doi:10.1/b", topic="u", text="rate 5 %",
                 quote="5 %", verifier_verdict="CONFIRMED")
    )
    assert claims.view()["pairs"] == []


def test_pairs_carry_severity(frozen_clock):
    _opposite_pair_setup()
    claims.add_claim(
        _payload(paper_key="doi:10.1/c", topic="err", text="rmse 0.05 mm", quote="0.05",
                 verifier_verdict="CONFIRMED")
    )
    claims.add_claim(
        _payload(paper_key="doi:10.1/d", topic="err", text="rmse 0.5 mm", quote="0.5",
                 verifier_verdict="CONFIRMED")
    )
    by_kind = {p["kind"]: p["severity"] for p in claims.view()["pairs"]}
    assert by_kind["verdict_opposite"] == "high"
    assert by_kind["numeric_conflict"] == "medium"
