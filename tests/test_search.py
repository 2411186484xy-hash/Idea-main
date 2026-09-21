"""L2 search: inverted-index restore, adapters behind the transport seam, envelopes."""

from __future__ import annotations

import json

from pipelines import search


def test_restore_abstract_rebuilds_order():
    assert search.restore_abstract({"world": [3], "hello": [1], "brave": [2]}) == "hello brave world"
    assert search.restore_abstract(None) == ""
    assert search.restore_abstract({}) == ""


def test_openalex_adapter_restores_and_gates(monkeypatch):
    body = json.dumps({
        "results": [
            {
                "title": "Deep read",
                "doi": "https://doi.org/10.1/deep",
                "abstract_inverted_index": {"read": [1], "deep": [0]},
                "publication_year": 2025,
                "cited_by_count": 42,
                "is_retracted": False,
                "primary_location": {"source": {"display_name": "Nature"}},
            },
            {"title": "No identifier", "abstract_inverted_index": {"x": [0]}},
        ]
    })
    monkeypatch.setattr(search, "_fetch", lambda url, params, timeout: (body, None))
    results, errors = search.openalex_search("deep read", limit=2)
    assert len(results) == 1 and len(errors) == 1
    cand = results[0]
    assert cand["paper_key"] == "doi:10.1/deep"
    assert cand["abstract"] == "deep read"
    assert cand["venue"] == "Nature" and cand["cited_by_count"] == 42
    assert cand["retraction"]["status"] == "none"
    assert errors[0]["category"] == "gate"  # identifier-less work dropped, not crash


def test_openalex_retracted_flag(monkeypatch):
    body = json.dumps({
        "results": [{"title": "Retracted", "doi": "https://doi.org/10.1/bad", "is_retracted": True}]
    })
    monkeypatch.setattr(search, "_fetch", lambda url, params, timeout: (body, None))
    results, _ = search.openalex_search("x")
    assert results[0]["retraction"]["status"] == "flagged"
    assert results[0]["retraction"]["checked_backends"] == ["openalex_is_retracted"]


def test_transport_failure_returns_envelope(monkeypatch):
    def boom(req, timeout):
        raise OSError("sandbox proxy fake 502")

    monkeypatch.setattr(search, "_urlopen_noproxy", boom)
    results, errors = search.openalex_search("anything")
    assert results == []
    assert errors[0]["category"] == "network"
    assert "OSError" in errors[0]["message"]


ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2501.12345v1</id>
    <title> A  Title </title>
    <summary>  abstract text  </summary>
    <published>2025-01-15T00:00:00Z</published>
  </entry>
</feed>"""


def test_arxiv_adapter_parses(monkeypatch):
    monkeypatch.setattr(search, "_LAST_ARXIV_AT", None)
    monkeypatch.setattr(search, "_fetch", lambda url, params, timeout: (ARXIV_XML, None))
    results, errors = search.arxiv_search("quantum", limit=1)
    assert errors == [] and len(results) == 1
    cand = results[0]
    assert cand["paper_key"] == "arxiv:2501.12345v1"
    assert cand["abstract"] == "abstract text"
    assert cand["year"] == 2025 and cand["venue"] == "arXiv"


def test_arxiv_bad_xml_is_parse_envelope(monkeypatch):
    monkeypatch.setattr(search, "_LAST_ARXIV_AT", None)
    monkeypatch.setattr(search, "_fetch", lambda url, params, timeout: ("<not-xml", None))
    results, errors = search.arxiv_search("q")
    assert results == [] and errors[0]["category"] == "parse"


def test_search_dedups_and_rejects_unknown_backend(monkeypatch):
    body = json.dumps({"results": [{"title": "T", "doi": "https://doi.org/10.1/x"}]})
    monkeypatch.setattr(search, "_fetch", lambda url, params, timeout: (body, None))
    result = search.search("q", backends=["openalex", "openalex"])
    assert result["ok"] and len(result["results"]) == 1
    bad = search.search("q", backends=["crossref"])
    assert not bad["ok"] and "unknown backends" in bad["error"]
