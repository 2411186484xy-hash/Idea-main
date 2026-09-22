"""L2 search: adapters behind the net transport seam, fan-out, health, expansion."""

from __future__ import annotations

import json

from pipelines import net, search, sources


def test_restore_abstract_rebuilds_order_and_caps():
    assert net.restore_abstract({"world": [3], "hello": [1], "brave": [2]}) == "hello brave world"
    assert net.restore_abstract(None) == ""
    assert net.restore_abstract({}) == ""
    long_index = {f"w{i}": [i] for i in range(400)}  # ~2400 chars unrolled
    capped = net.restore_abstract(long_index)
    assert len(capped) == 601 and capped.endswith("…")  # 600 + ellipsis (V1 LST:1870)


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
                "authorships": [{"author": {"display_name": "Ada Lovelace"}},
                                {"author": {"display_name": "  "}}],
            },
            {"title": "No identifier", "abstract_inverted_index": {"x": [0]}},
        ]
    })
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: (body, None))
    results, errors = sources.openalex_search("deep read", limit=2)
    assert len(results) == 1 and len(errors) == 1
    cand = results[0]
    assert cand["paper_key"] == "doi:10.1/deep"
    assert cand["abstract"] == "deep read"
    assert cand["venue"] == "Nature" and cand["cited_by_count"] == 42
    assert cand["authors"] == ["Ada Lovelace"]  # blank author rows normalised away
    assert cand["retraction"]["status"] == "none"
    assert errors[0]["category"] == "gate"  # identifier-less work dropped, not crash


def test_openalex_retracted_flag(monkeypatch):
    body = json.dumps({
        "results": [{"title": "Retracted", "doi": "https://doi.org/10.1/bad", "is_retracted": True}]
    })
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: (body, None))
    results, _ = sources.openalex_search("x")
    assert results[0]["retraction"]["status"] == "flagged"
    assert results[0]["retraction"]["checked_backends"] == ["openalex_is_retracted"]


def test_openalex_bad_json_is_parse_envelope(monkeypatch):
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: ("{not json", None))
    results, errors = sources.openalex_search("x")
    assert results == [] and errors[0]["category"] == "parse"


def test_transport_failure_returns_envelope(monkeypatch):
    def boom(req, timeout):
        raise OSError("sandbox proxy fake 502")

    monkeypatch.setattr(net, "_urlopen_noproxy", boom)
    results, errors = sources.openalex_search("anything")
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
    <author><name>Grace Hopper</name></author>
    <author><name> Alan Turing </name></author>
  </entry>
</feed>"""


def test_arxiv_adapter_parses(monkeypatch):
    monkeypatch.setattr(sources, "_LAST_ARXIV_AT", None)
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: (ARXIV_XML, None))
    results, errors = sources.arxiv_search("quantum", limit=1)
    assert errors == [] and len(results) == 1
    cand = results[0]
    assert cand["paper_key"] == "arxiv:2501.12345v1"
    assert cand["abstract"] == "abstract text"
    assert cand["authors"] == ["Grace Hopper", "Alan Turing"]
    assert cand["year"] == 2025 and cand["venue"] == "arXiv"


def test_arxiv_bad_xml_is_parse_envelope(monkeypatch):
    monkeypatch.setattr(sources, "_LAST_ARXIV_AT", None)
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: ("<not-xml", None))
    results, errors = sources.arxiv_search("q")
    assert results == [] and errors[0]["category"] == "parse"


def test_crossref_adapter_strips_abstract_and_flags_retraction(monkeypatch):
    body = json.dumps({"message": {"items": [
        {"DOI": "10.1/clean", "title": ["Clean"],
         "abstract": "<jats:p>plain abstract</jats:p>",
         "container-title": ["Nature"], "published-print": {"date-parts": [[2024]]},
         "is-referenced-by-count": 7,
         "author": [{"given": "Alan", "family": "Turing"}, {"name": "Endo Group"}]},
        {"DOI": "10.1/bad", "title": ["Bad"], "updated-by": [{"type": "retraction"}]},
        {"title": ["No DOI"]},
    ]}})
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: (body, None))
    results, errors = sources.crossref_search("x", limit=3)
    assert len(results) == 2 and len(errors) == 1 and errors[0]["category"] == "gate"
    clean = next(c for c in results if c["paper_key"] == "doi:10.1/clean")
    assert clean["abstract"] == "plain abstract" and clean["year"] == 2024
    assert clean["venue"] == "Nature" and clean["retraction"]["status"] == "none"
    assert clean["authors"] == ["Alan Turing", "Endo Group"]
    bad = next(c for c in results if c["paper_key"] == "doi:10.1/bad")
    assert bad["retraction"]["status"] == "flagged"
    assert bad["retraction"]["checked_backends"] == ["crossref_update_to"]


def test_crossref_transport_failure_is_envelope(monkeypatch):
    def boom(req, timeout):
        raise OSError("offline")

    monkeypatch.setattr(net, "_urlopen_noproxy", boom)
    results, errors = sources.crossref_search("anything")
    assert results == [] and errors[0]["category"] in ("network", "http")


def test_crossref_titleless_row_is_gated_not_raised(monkeypatch):
    """Real-registry rows can lack a title; that must be a gate envelope, not a raise."""
    body = json.dumps({"message": {"items": [
        {"DOI": "10.1/blank-title", "title": [""]},
        {"DOI": "10.1/no-title-key"},
        {"DOI": "10.1/ok", "title": ["Kept"]},
    ]}})
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: (body, None))
    results, errors = sources.crossref_search("x", limit=3)
    assert [c["paper_key"] for c in results] == ["doi:10.1/ok"]
    assert len(errors) == 2 and all(e["category"] == "gate" for e in errors)


def test_europepmc_adapter_maps_doi_and_pmid(monkeypatch):
    body = json.dumps({"resultList": {"result": [
        {"doi": "10.2/a", "title": "A", "abstractText": "abs",
         "pubYear": "2023", "journalTitle": "J", "citedByCount": 3,
         "authorList": {"author": [{"fullName": "Jia-Yi Huo"},
                                   {"collectiveName": "Endo Group"}]}},
        {"pmid": "123", "title": "B"},
        {"title": "No id"},
    ]}})
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: (body, None))
    results, errors = sources.europepmc_search("x", limit=3)
    assert len(results) == 2 and len(errors) == 1
    assert results[0]["paper_key"] == "doi:10.2/a" and results[0]["abstract"] == "abs"
    assert results[0]["year"] == 2023 and results[1]["paper_key"] == "pmid:123"
    assert results[0]["authors"] == ["Jia-Yi Huo", "Endo Group"]
    assert results[1]["authors"] == []


def test_doaj_adapter_parses_bibjson(monkeypatch):
    body = json.dumps({"results": [{"bibjson": {
        "title": "Hybrid Fringe",
        "abstract": "<p>html abstract</p>",
        "year": "2021",
        "identifier": [{"type": "eissn", "id": "2169-3536"},
                       {"type": "doi", "id": "10.1109/ACCESS.2021.3061415"}],
        "journal": {"title": "IEEE Access"},
        "author": [{"name": "A B"}, {"name": ""}],
    }}, {"bibjson": {"title": "No DOI row"}}]})
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: (body, None))
    results, errors = sources.doaj_search("fringe", limit=2)
    assert len(results) == 1 and len(errors) == 1
    cand = results[0]
    assert cand["paper_key"] == "doi:10.1109/access.2021.3061415"
    assert cand["abstract"] == "html abstract" and cand["year"] == 2021
    assert cand["venue"] == "IEEE Access" and cand["authors"] == ["A B"]


def test_openreview_adapter_identifier_cascade(monkeypatch):
    body = json.dumps({"notes": [
        {"id": "n1", "pdate": 1672531200000, "content": {
            "title": {"value": "Doi Paper"}, "abstract": {"value": "abs"},
            "authors": {"value": [{"fullname": "X Y"}]},
            "html": {"value": "https://doi.org/10.1007/978-3-031-46311-2_18"},
            "venue": {"value": "ICIG 2023"}}},
        {"id": "n2", "cdate": 1672531200000, "content": {
            "title": {"value": "Arxiv Paper"}, "authors": {"value": ["A", "B"]},
            "html": {"value": "https://doi.org/10.48550/arXiv.2303.07606"}}},
        {"id": "n3", "content": {"title": {"value": "Bare Note"}}},
        {"id": "n4", "content": {"abstract": {"value": "no title"}}},
    ]})
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: (body, None))
    results, errors = sources.openreview_search("fringe", limit=4)
    keys = [c["paper_key"] for c in results]
    assert keys == ["doi:10.1007/978-3-031-46311-2_18", "arxiv:2303.07606", "openreview:n3"]
    assert results[0]["year"] == 2023 and results[0]["venue"] == "ICIG 2023"
    assert results[1]["authors"] == ["A", "B"]
    assert len(errors) == 1 and errors[0]["category"] == "gate"  # title-less note


def test_search_dedups_and_rejects_unknown_backend(monkeypatch):
    body = json.dumps({"results": [{"title": "T", "doi": "https://doi.org/10.1/x"}]})
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: (body, None))
    result = search.search("q", backends=["openalex", "openalex"])
    assert result["ok"] and len(result["results"]) == 1
    bad = search.search("q", backends=["no-such-backend"])
    assert not bad["ok"] and "unknown backends" in bad["error"]


def test_available_backend_reachable_only_when_named(monkeypatch):
    body = json.dumps({"notes": []})
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: (body, None))
    result = search.search("q", backends=["openreview"])
    assert result["ok"] and list(result["channel_health"]) == ["openreview"]


def test_search_fans_out_all_active_backends(monkeypatch):
    seen: list[str] = []

    def fake(url, params, timeout):
        seen.append(url)
        if "openalex" in url:
            return json.dumps({"results": []}), None
        if "arxiv" in url:
            return ("""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>""", None)
        if "crossref" in url:
            return json.dumps({"message": {"items": []}}), None
        if "doaj" in url:
            return json.dumps({"results": []}), None
        return json.dumps({"resultList": {"result": []}}), None

    monkeypatch.setattr(net, "_fetch", fake)
    monkeypatch.setattr(sources, "_LAST_ARXIV_AT", None)
    result = search.search("q")
    assert result["ok"] and result["errors"] == []
    assert len(seen) == 5
    assert result["channel_health"]["openalex"]["status"] == "empty"


def test_channel_health_three_states(monkeypatch):
    def fake(url, params, timeout):
        if "openalex" in url:
            return json.dumps({"results": [{"title": "T", "doi": "https://doi.org/10.1/x"}]}), None
        if "crossref" in url:
            return None, {"source": "crossref", "category": "network", "message": "down"}
        return None, {"source": "europepmc", "category": "network", "message": "boom"}

    monkeypatch.setattr(net, "_fetch", fake)
    monkeypatch.setattr(sources, "_LAST_ARXIV_AT", None)
    result = search.search("q", backends=["openalex", "crossref", "europepmc"])
    health = result["channel_health"]
    assert health["openalex"]["status"] == "ok" and health["openalex"]["found"] == 1
    assert health["crossref"]["status"] == "error" and health["crossref"]["errors"] == 1
    assert health["europepmc"]["status"] == "error"


def test_search_tags_sources(monkeypatch):
    body = json.dumps({"results": [{"title": "T", "doi": "https://doi.org/10.1/x"}]})
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: (body, None))
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

    monkeypatch.setattr(net, "_fetch", fake)
    out = search.search_multi(["first", "second"], backends=["openalex"])
    assert out["ok"] and out["queries"] == ["first", "second"]
    shared = next(c for c in out["results"] if c["paper_key"] == "doi:10.1/s")
    assert [s["query"] for s in shared["sources"]] == ["first", "second"]
    assert search.search_multi([], backends=["openalex"])["ok"] is False
    assert search.search_multi(["q"], backends=["nope"])["ok"] is False


def test_expand_cites_and_references(monkeypatch):
    def fake(url, params, timeout):
        if "/10.1/seed" in url:
            return json.dumps({"id": "https://openalex.org/W100",
                               "referenced_works": ["https://openalex.org/W201",
                                                    "https://openalex.org/W202"]}), None
        if params.get("filter", "").startswith("cites:"):
            return json.dumps({"results": [
                {"title": "Forward", "doi": "https://doi.org/10.1/fwd"}]}), None
        return json.dumps({"results": [
            {"title": "Backward", "doi": "https://doi.org/10.1/bwd"}]}), None

    monkeypatch.setattr(net, "_fetch", fake)
    out = search.expand("doi:10.1/seed")
    assert out["ok"] and out["directions"] == ["cites", "references"]
    keys = {c["paper_key"] for c in out["results"]}
    assert keys == {"doi:10.1/fwd", "doi:10.1/bwd"}
    assert all(c["sources"][0]["backend"] == "openalex" for c in out["results"])
    assert search.expand("")["ok"] is False
    assert search.expand("10.1/x", direction="sideways")["ok"] is False


def test_search_expand_logs_all_queries(monkeypatch, frozen_clock, capsys):
    from cli import main
    from pipelines import runs

    monkeypatch.setattr(sources, "_respect_arxiv_interval", lambda: None)
    monkeypatch.setattr(net, "_fetch", lambda url, params, timeout: (
        (json.dumps({"results": []}), None) if "openalex" in url else
        (json.dumps({"results": []}), None) if "doaj" in url else
        ("""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>""", None)
        if "arxiv" in url else (json.dumps({"message": {"items": []}}), None)
        if "crossref" in url else (json.dumps({"resultList": {"result": []}}), None)))
    runs.start("weekly", "WEEKLYRUN-20260921-120000")
    rc = main(["search", "base q", "--run", "WEEKLYRUN-20260921-120000", "--expand"])
    assert rc == 0
    run = runs.load("WEEKLYRUN-20260921-120000")
    assert len(run.query_log) == 4
    assert run.trace[-1]["event"] == "SEARCH"
