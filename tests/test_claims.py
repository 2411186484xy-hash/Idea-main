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
