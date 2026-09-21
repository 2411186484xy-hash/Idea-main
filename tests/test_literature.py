"""Literature gates: retraction dual-channel, JCR soft, lint hard."""

from pipelines import literature, papers


def test_second_pass_retracted():
    assert (
        literature.second_pass_verify({"doi": "10.1/x", "is_retracted": True})["status"]
        == "fail_retracted"
    )
    assert literature.second_pass_verify({"title": "no id"})["status"] == "fail"
    assert literature.second_pass_verify({"doi": "10.1/x"})["status"] == "ok"


def test_jcr_soft_never_blocks():
    assert literature.jcr_soft_gate({"issn": "0000-0000"}, {"0000-0000": "Q1"}) == "ok"
    assert literature.jcr_soft_gate({"issn": "0000-0000"}, {}) == "watchlist"
    assert literature.jcr_soft_gate({}, {}) == "watchlist"


def test_lint_page_anchor_and_placeholder():
    note = {
        "key_claims": [{"id": "c1", "text": "提升 12% (p.3, 'quote')"}],
        "formula_ledger": "E=mc^2 (p.4)",
    }
    assert papers.lint_note(note)["ok"]
    bad = papers.lint_note(
        {"key_claims": [{"id": "c1", "text": "提升 12% 无页锚"}], "formula_ledger": "TBD"}
    )
    assert not bad["ok"] and len(bad["violations"]) == 2
