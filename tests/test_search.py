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
    bad = search.search("q", backends=["no-such-backend"])
    assert not bad["ok"] and "unknown backends" in bad["error"]


def test_crossref_adapter_strips_abstract_and_flags_retraction(monkeypatch):
    body = json.dumps({"message": {"items": [
        {"DOI": "10.1/clean", "title": ["Clean"],
         "abstract": "<jats:p>plain abstract</jats:p>",
         "container-title": ["Nature"], "published-print": {"date-parts": [[2024]]},
         "is-referenced-by-count": 7},
        {"DOI": "10.1/bad", "title": ["Bad"], "updated-by": [{"type": "retraction"}]},
        {"title": ["No DOI"]},
    ]}})
    monkeypatch.setattr(search, "_fetch", lambda url, params, timeout: (body, None))
    results, errors = search.crossref_search("x", limit=3)
    assert len(results) == 2 and len(errors) == 1 and errors[0]["category"] == "gate"
    clean = next(c for c in results if c["paper_key"] == "doi:10.1/clean")
    assert clean["abstract"] == "plain abstract" and clean["year"] == 2024
    assert clean["venue"] == "Nature" and clean["retraction"]["status"] == "none"
    bad = next(c for c in results if c["paper_key"] == "doi:10.1/bad")
    assert bad["retraction"]["status"] == "flagged"
    assert bad["retraction"]["checked_backends"] == ["crossref_update_to"]


def test_crossref_transport_failure_is_envelope(monkeypatch):
    def boom(req, timeout):
        raise OSError("offline")

    monkeypatch.setattr(search, "_urlopen_noproxy", boom)
    results, errors = search.crossref_search("anything")
    assert results == [] and errors[0]["category"] in ("network", "http")


def test_europepmc_adapter_maps_doi_and_pmid(monkeypatch):
    body = json.dumps({"resultList": {"result": [
        {"doi": "10.2/a", "title": "A", "abstractText": "abs",
         "pubYear": "2023", "journalTitle": "J", "citedByCount": 3},
        {"pmid": "123", "title": "B"},
        {"title": "No id"},
    ]}})
    monkeypatch.setattr(search, "_fetch", lambda url, params, timeout: (body, None))
    results, errors = search.europepmc_search("x", limit=3)
    assert len(results) == 2 and len(errors) == 1
    assert results[0]["paper_key"] == "doi:10.2/a" and results[0]["abstract"] == "abs"
    assert results[0]["year"] == 2023 and results[1]["paper_key"] == "pmid:123"


def test_search_all_four_backends_dispatch(monkeypatch):
    seen: list[str] = []

    def fake(url, params, timeout):
        seen.append(url)
        if "openalex" in url:
            return json.dumps({"results": []}), None
        if "arxiv" in url:
            return ("""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>""", None)
        if "crossref" in url:
            return json.dumps({"message": {"items": []}}), None
        return json.dumps({"resultList": {"result": []}}), None

    monkeypatch.setattr(search, "_fetch", fake)
    monkeypatch.setattr(search, "_LAST_ARXIV_AT", None)
    result = search.search("q")
    assert result["ok"] and result["errors"] == []
    assert len(seen) == 4


def test_search_tags_sources(monkeypatch):
    body = json.dumps({"results": [{"title": "T", "doi": "https://doi.org/10.1/x"}]})
    monkeypatch.setattr(search, "_fetch", lambda url, params, timeout: (body, None))
    result = search.search("my query", backends=["openalex"])
    assert result["results"][0]["sources"] == [{"backend": "openalex", "query": "my query"}]


def test_search_multi_merges_trails_and_rejects_bad(monkeypatch):
    def fake(url, params, timeout):
        term = params.get("search", params.get("query", params.get("search_query", "")))
        if "second" in str(term):
            return json.dumps({"results": [
                {"title": "Shared", "doi": "https://doi.org/10.1/s"},
                {"title": "New", "doi": "https://doi.org/10.1/n"}]}), None
        return json.dumps({"results": [
            {"title": "Shared", "doi": "https://doi.org/10.1/s"}]}), None

    monkeypatch.setattr(search, "_fetch", fake)
    out = search.search_multi(["first", "second"], backends=["openalex"])
    assert out["ok"] and out["queries"] == ["first", "second"]
    shared = next(c for c in out["results"] if c["paper_key"] == "doi:10.1/s")
    assert [s["query"] for s in shared["sources"]] == ["first", "second"]
    assert search.search_multi([], backends=["openalex"])["ok"] is False
    assert search.search_multi(["q"], backends=["nope"])["ok"] is False


def test_search_expand_logs_all_queries(monkeypatch, frozen_clock, capsys):
    from cli import main
    from pipelines import runs

    monkeypatch.setattr(search, "_respect_arxiv_interval", lambda: None)
    monkeypatch.setattr(search, "_fetch", lambda url, params, timeout: (
        json.dumps({"results": []}), None) if "openalex" in url else (
        """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>""", None)
        if "arxiv" in url else (json.dumps({"message": {"items": []}}), None)
        if "crossref" in url else (json.dumps({"resultList": {"result": []}}), None))
    runs.start("weekly", "WEEKLYRUN-20260921-120000")
    rc = main(["search", "base q", "--run", "WEEKLYRUN-20260921-120000", "--expand"])
    assert rc == 0
    run = runs.load("WEEKLYRUN-20260921-120000")
    assert len(run.query_log) == 4
    assert run.trace[-1]["event"] == "SEARCH"
