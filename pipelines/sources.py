"""L2 sources: the keyless retrieval adapters, one mapper per channel.

Adapter protocol (M3.1): callable ``(query, limit) -> (candidates, errors)``,
registered in ADAPTERS and reachable via canon ``search.active`` /
``search.available``; both adapter tests pin declared==wired. Transport and
the parsing kit live in ``net`` (the single seam tests monkeypatch); every
adapter returns envelopes, nothing raises. New source checklist: adapter +
registry entry + canon slot + parser test + declared==wired test.
"""

from __future__ import annotations

import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

from . import canon, net, store

_LAST_ARXIV_AT: float | None = None
_ARXIV_LOCK = threading.Lock()  # fan-out runs adapters in threads


def _crossref_year(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "created"):
        parts = ((item.get(key) or {}).get("date-parts") or [[]])[0]
        if parts and str(parts[0]).isdigit():
            return int(parts[0])
    return None


def _crossref_retracted(item: dict[str, Any]) -> bool:
    for u in item.get("updated-by") or []:
        if "retract" in str(u.get("type", "")).lower():
            return True
    return bool(item.get("update-to"))


def _openalex_map(w: dict[str, Any]):
    source = (w.get("primary_location") or {}).get("source") or {}
    doi = str(w.get("doi") or "").replace("https://doi.org/", "").strip()
    cand = net._candidate(title=str(w.get("title") or ""),
        identifiers={"doi": doi} if doi else {}, backend="openalex",
        abstract=net.restore_abstract(w.get("abstract_inverted_index")),
        year=w.get("publication_year"), venue=source.get("display_name"),
        cited_by=w.get("cited_by_count"), retracted=bool(w.get("is_retracted")),
        checked_backend="openalex_is_retracted",
        authors=[str((a.get("author") or {}).get("display_name") or "") for a in (w.get("authorships") or [])])
    return cand, f"row dropped (missing identifier or title): {str(w.get('id'))[:60]}"


def openalex_search(query: str, limit: int = 15) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    body, err = net._fetch("https://api.openalex.org/works",
        {"search": query, "per-page": limit, "mailto": str(canon.value("search.polite_pool_mailto"))},
        int(str(canon.value("search.timeout_seconds"))))
    if err or body is None:
        return [], [err or net._envelope("openalex", "network", "no body")]
    doc, perr = net._json_body(body, "openalex")
    if doc is None:
        return [], [perr or net._envelope("openalex", "parse", "no body")]
    return net._rows_to_candidates(doc.get("results") or [], _openalex_map, "openalex")


_ARXIV_NS = {"a": "http://www.w3.org/2005/Atom"}


def _respect_arxiv_interval() -> None:
    global _LAST_ARXIV_AT
    with _ARXIV_LOCK:  # the rate limit is global across threads
        interval = float(str(canon.value("search.arxiv_interval_seconds")))
        now = time.monotonic()
        if _LAST_ARXIV_AT is not None:
            remaining = interval - (now - _LAST_ARXIV_AT)
            if remaining > 0:
                time.sleep(remaining)
        _LAST_ARXIV_AT = time.monotonic()


def arxiv_search(query: str, limit: int = 15) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    _respect_arxiv_interval()
    body, err = net._fetch(
        "https://export.arxiv.org/api/query",
        {"search_query": query, "start": 0, "max_results": limit},
        int(str(canon.value("search.timeout_seconds"))),
    )
    if err or body is None:
        return [], [err or net._envelope("arxiv", "network", "no body")]
    results: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        return [], [net._envelope("arxiv", "parse", f"xml parse: {exc}")]
    for entry in root.findall("a:entry", _ARXIV_NS):
        arxiv_id = (entry.findtext("a:id", default="", namespaces=_ARXIV_NS) or "").rsplit("/abs/", 1)[-1]
        published = entry.findtext("a:published", default="", namespaces=_ARXIV_NS) or ""
        cand = net._candidate(title=(entry.findtext("a:title", default="", namespaces=_ARXIV_NS) or ""),
            identifiers={"arxiv_id": arxiv_id} if arxiv_id else {}, backend="arxiv",
            abstract=(entry.findtext("a:summary", default="", namespaces=_ARXIV_NS) or "").strip(),
            year=int(published[:4]) if published[:4].isdigit() else None, venue="arXiv",
            cited_by=None, retracted=False, checked_backend="arxiv",
            authors=[(n.text or "") for n in entry.findall("a:author/a:name", _ARXIV_NS)])
        if cand is not None:
            results.append(store.to_dict(cand))
    return results, []


def _crossref_map(it: dict[str, Any]):
    doi = str(it.get("DOI") or "").strip()
    cand = net._candidate(title=str((it.get("title") or [""])[0] or ""),
        identifiers={"doi": doi} if doi else {}, backend="crossref",
        abstract=net._strip_tags(it.get("abstract")), year=_crossref_year(it),
        venue=str((it.get("container-title") or [None])[0] or "") or None,
        cited_by=it.get("is-referenced-by-count"), retracted=_crossref_retracted(it),
        checked_backend="crossref_update_to",
        authors=[f"{a.get('given', '')} {a.get('family', '')}".strip() or str(a.get("name") or "") for a in (it.get("author") or [])])
    return cand, f"row dropped (missing DOI or title): {str(it.get('DOI'))[:60]}"


def crossref_search(query: str, limit: int = 15) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Crossref discovery + update-to/updated-by retraction channel (M2a)."""
    select = "DOI,title,abstract,author,container-title,published,created,is-referenced-by-count,updated-by,update-to"
    body, err = net._fetch("https://api.crossref.org/works",
        {"query": query, "rows": limit, "select": select},
        int(str(canon.value("search.timeout_seconds"))))
    if err or body is None:
        return [], [err or net._envelope("crossref", "network", "no body")]
    doc, perr = net._json_body(body, "crossref")
    if doc is None:
        return [], [perr or net._envelope("crossref", "parse", "no body")]
    items = (doc.get("message") or {}).get("items") or []
    return net._rows_to_candidates(items, _crossref_map, "crossref")


def _europepmc_map(r: dict[str, Any]):
    doi = str(r.get("doi") or "").strip()
    pmid = str(r.get("pmid") or "").strip()
    year = str(r.get("pubYear") or "")
    cand = net._candidate(title=str(r.get("title") or ""),
        identifiers={"doi": doi} if doi else ({"pmid": pmid} if pmid else {}),
        backend="europepmc", abstract=str(r.get("abstractText") or "").strip(),
        year=int(year) if year.isdigit() else None, venue=r.get("journalTitle"),
        cited_by=r.get("citedByCount"), retracted=False, checked_backend="europepmc",
        authors=[str(a.get("fullName") or a.get("collectiveName") or "") for a in ((r.get("authorList") or {}).get("author") or [])])
    return cand, f"hit without identifier dropped: {str(r.get('title'))[:60]}"


def europepmc_search(query: str, limit: int = 15) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """EuropePMC discovery (M2a, fourth channel; core resultType carries abstracts)."""
    body, err = net._fetch("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        {"query": query, "format": "json", "pageSize": limit, "resultType": "core"},
        int(str(canon.value("search.timeout_seconds"))))
    if err or body is None:
        return [], [err or net._envelope("europepmc", "network", "no body")]
    doc, perr = net._json_body(body, "europepmc")
    if doc is None:
        return [], [perr or net._envelope("europepmc", "parse", "no body")]
    hits = (doc.get("resultList") or {}).get("result") or []
    return net._rows_to_candidates(hits, _europepmc_map, "europepmc")


def _doaj_map(row: dict[str, Any]):
    bib = row.get("bibjson") or {}
    doi = next((str(i.get("id") or "").strip() for i in (bib.get("identifier") or [])
                if str(i.get("type", "")).lower() == "doi"), "")
    year = str(bib.get("year") or "")
    cand = net._candidate(title=str(bib.get("title") or ""),
        identifiers={"doi": doi} if doi else {}, backend="doaj",
        abstract=net._strip_tags(bib.get("abstract")),  # DOAJ abstracts carry HTML
        year=int(year) if year.isdigit() else None,
        venue=(bib.get("journal") or {}).get("title"),
        cited_by=None, retracted=False, checked_backend="doaj",
        authors=[str(a.get("name") or "") for a in (bib.get("author") or [])])
    return cand, f"row dropped (no DOI/title): {str(bib.get('title'))[:60]}"


def doaj_search(query: str, limit: int = 15) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """DOAJ open-access journals (keyless v2 API; 2026-09-23 probe: 1.3s stable)."""
    body, err = net._fetch(
        f"https://doaj.org/api/v2/search/articles/{urllib.parse.quote(query)}",
        {"pageSize": limit}, int(str(canon.value("search.timeout_seconds"))))
    if err or body is None:
        return [], [err or net._envelope("doaj", "network", "no body")]
    doc, perr = net._json_body(body, "doaj")
    if doc is None:
        return [], [perr or net._envelope("doaj", "parse", "no body")]
    return net._rows_to_candidates(doc.get("results") or [], _doaj_map, "doaj")


def _ov_value(node: Any) -> Any:
    """api2 note contents wrap values as {'value': X}; accept plain values too."""
    return node.get("value") if isinstance(node, dict) and "value" in node else node


def _openreview_identifiers(note: dict[str, Any], content: dict[str, Any]) -> dict[str, str]:
    html = str(_ov_value(content.get("html")) or "")
    doi = html.split("doi.org/", 1)[1].split("?", 1)[0] if "doi.org/" in html else ""
    lowered = doi.lower()
    if lowered.startswith("10.48550/arxiv."):
        return {"arxiv_id": lowered.rsplit("arxiv.", 1)[-1]}
    if doi:
        return {"doi": doi}
    return {"openreview_id": str(note.get("id") or "")}


def _openreview_map(note: dict[str, Any]):
    content = note.get("content") or {}
    authors_raw = _ov_value(content.get("authors")) or []
    when = note.get("pdate") or note.get("cdate")
    year = time.gmtime(int(when) / 1000).tm_year if when else None
    cand = net._candidate(title=str(_ov_value(content.get("title")) or ""),
        identifiers=_openreview_identifiers(note, content), backend="openreview",
        abstract=str(_ov_value(content.get("abstract")) or "").strip(),
        year=year, venue=str(_ov_value(content.get("venue")) or "") or None,
        cited_by=None, retracted=False, checked_backend="openreview",
        authors=[str(a.get("fullname") if isinstance(a, dict) else a or "") for a in authors_raw])
    return cand, f"note dropped (no identifier/title): {str(note.get('id'))[:40]}"


def openreview_search(query: str, limit: int = 15) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """OpenReview api2 note search (available on demand; CS conferences/preprints)."""
    body, err = net._fetch("https://api2.openreview.net/notes/search",
        {"term": query, "limit": limit}, int(str(canon.value("search.timeout_seconds"))))
    if err or body is None:
        return [], [err or net._envelope("openreview", "network", "no body")]
    doc, perr = net._json_body(body, "openreview")
    if doc is None:
        return [], [perr or net._envelope("openreview", "parse", "no body")]
    return net._rows_to_candidates(doc.get("notes") or [], _openreview_map, "openreview")


ADAPTERS: dict[str, Any] = {
    "openalex": openalex_search,
    "arxiv": arxiv_search,
    "crossref": crossref_search,
    "europepmc": europepmc_search,
    "doaj": doaj_search,
    "openreview": openreview_search,
}


def _openalex_short_id(raw: str) -> str:
    return str(raw).rsplit("/", 1)[-1]


def openalex_related(doi: str, direction: str, limit: int = 50) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One-hop citation traversal (M3.1): 'cites' = who cites the seed,
    'references' = what the seed cites. Reuses the openalex row mapper."""
    timeout = int(str(canon.value("search.timeout_seconds")))
    mailto = str(canon.value("search.polite_pool_mailto"))
    body, err = net._fetch(f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi)}", {}, timeout)
    if err or body is None:
        return [], [err or net._envelope("openalex", "network", "no body")]
    doc, perr = net._json_body(body, "openalex")
    if doc is None:
        return [], [perr or net._envelope("openalex", "parse", "no body")]
    seed_id = _openalex_short_id(str(doc.get("id") or ""))
    if not seed_id:
        return [], [net._envelope("openalex", "gate", f"seed not found: doi:{doi}")]
    if direction == "references":
        ids = [_openalex_short_id(w) for w in (doc.get("referenced_works") or [])][:limit]
        if not ids:
            return [], []
        body, err = net._fetch("https://api.openalex.org/works",
            {"filter": "openalex_id:" + "|".join(ids), "per-page": limit, "mailto": mailto}, timeout)
    else:
        body, err = net._fetch("https://api.openalex.org/works",
            {"filter": f"cites:{seed_id}", "per-page": limit, "mailto": mailto}, timeout)
    if err or body is None:
        return [], [err or net._envelope("openalex", "network", "no body")]
    works_doc, perr = net._json_body(body, "openalex")
    if works_doc is None:
        return [], [perr or net._envelope("openalex", "parse", "no body")]
    return net._rows_to_candidates(works_doc.get("results") or [], _openalex_map, "openalex")
