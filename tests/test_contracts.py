"""L0 contracts: construction validation, paper_key precedence, schema reject."""

from __future__ import annotations

import pytest

from pipelines import contracts


def _payload(**over):
    base = {
        "title": "A paper",
        "identifiers": {"doi": "10.1234/abc"},
        "source_backend": "openalex",
        "abstract": "abs",
        "abstract_sha256": contracts.sha256_hex("abs"),
    }
    base.update(over)
    return base


def test_paper_key_precedence():
    assert (
        contracts.make_paper_key({"doi": "d", "arxiv_id": "a", "pmid": "p", "pdf_sha256": "s" * 64})
        == "doi:d"
    )
    assert contracts.make_paper_key({"arxiv_id": "2501.1", "pmid": "1"}) == "arxiv:2501.1"
    assert contracts.make_paper_key({"pmid": "123"}) == "pmid:123"
    assert contracts.make_paper_key({"pdf_sha256": "ABCDEF" * 11}) == "sha12:abcdefabcdef"


def test_identifier_gate():
    with pytest.raises(ValueError, match="identifier"):
        contracts.PaperCandidate(**_payload(identifiers={}))


def test_paper_key_drift_rejected():
    with pytest.raises(ValueError, match="paper_key drift"):
        contracts.PaperCandidate(**_payload(paper_key="doi:other"))


def test_default_retraction_none():
    cand = contracts.PaperCandidate(**_payload())
    assert cand.retraction == {"status": "none", "checked_backends": [], "checked_at": ""}


def test_bad_discovery_class():
    with pytest.raises(ValueError, match="discovery_class"):
        contracts.PaperCandidate(**_payload(discovery_class="random"))


def _claim(**over):
    base = {
        "id": "CLM-20260921-001",
        "paper_key": "doi:10.1/x",
        "topic": "calibration",
        "text": "the claim",
        "quote": "verbatim text",
        "page_anchor": 3,
        "confidence": "high",
        "verifier_verdict": "CONFIRMED",
        "created_at": "2026-09-21T00:00:00Z",
    }
    base.update(over)
    return contracts.Claim(**base)


def test_claim_page_anchor_and_quote_gates():
    with pytest.raises(ValueError, match="page_anchor"):
        _claim(page_anchor=0)
    with pytest.raises(ValueError, match="quote"):
        _claim(quote="  ")
    with pytest.raises(ValueError, match="bad claim id"):
        _claim(id="CLM-XX")
    with pytest.raises(ValueError, match="topic"):
        _claim(topic="")


def test_claim_verdict_enum():
    with pytest.raises(ValueError, match="verifier_verdict"):
        _claim(verifier_verdict="MAYBE")


def test_error_envelope_category():
    with pytest.raises(ValueError, match="category"):
        contracts.ErrorEnvelope(source="x", category="weird", message="m")


def test_quality_card_and_attacks_gates():
    card = {d: {"score": 3, "rationale": "r"} for d in contracts.QUALITY_DIMS}
    idea = {
        "slug": "my-idea",
        "title": "T",
        "hypothesis": "H",
        "collision": {"seed": "s", "source_domain": "a", "target_domain": "b"},
        "quality_card": card,
        "attacks": ["a"] * 6,
        "novelty_log": [{"query": "q", "backend": "b", "top_match": "t", "note": "n"}],
        "evidence_refs": ["doi:1", "doi:2", "doi:3"],
    }
    assert contracts.IdeaCandidate(**idea).status == "draft"
    with pytest.raises(ValueError, match="slug"):
        contracts.IdeaCandidate(**{**idea, "slug": "UP"})
    with pytest.raises(ValueError, match="score"):
        contracts.IdeaCandidate(**{**idea, "quality_card": {**card, "novelty": {"score": 9, "rationale": "r"}}})
    with pytest.raises(ValueError, match="attacks"):
        contracts.IdeaCandidate(**{**idea, "attacks": ["a"] * 5})


def test_manifest_hash_gate():
    with pytest.raises(ValueError, match="sha256"):
        contracts.ZoteroManifest(items=[{"a": 1}], sha256="nope", created_at="t")


def test_run_coverage_defaults():
    run = contracts.Run(
        run_id="WEEKLYRUN-20260921-120000",
        kind="weekly",
        status="active",
        attempt=1,
        created_at="t",
        updated_at="t",
    )
    assert run.coverage == {r: 0 for r in contracts.COVERAGE_ROUTES}
    with pytest.raises(ValueError, match="prefix/kind mismatch"):
        contracts.Run(
            run_id="IDEARUN-20260921-120000",
            kind="weekly",
            status="active",
            attempt=1,
            created_at="t",
            updated_at="t",
        )
