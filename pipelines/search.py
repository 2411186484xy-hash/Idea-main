"""L2 search port: OpenAlex + arXiv + Crossref + EuropePMC behind one envelope.

Network discipline (V1-proven): polite-pool mailto, identifiable UA, arXiv 3s
interval, SSL certifi fallback, sandbox proxy bypass, timeouts — failures
return ErrorEnvelope dicts, never raise (inverted-index restore: V1 :1067).
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from . import canon, contracts, store
from .contracts import ErrorEnvelope

_LAST_ARXIV_AT: float | None = None
_CERT_ENV_SET = False


def _ensure_ssl_cert_env() -> None:
    """Certifi fallback: user-level SSL_CERT_FILE dies with the session (V1 fact)."""
    global _CERT_ENV_SET
    if _CERT_ENV_SET:
        return
    _CERT_ENV_SET = True
    import os
    from pathlib import Path

    if os.environ.get("SSL_CERT_FILE") and Path(os.environ["SSL_CERT_FILE"]).exists():
        return
    try:
        import certifi

        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except ImportError:
        pass


def _urlopen_noproxy(req: urllib.request.Request, timeout: int):
    """V1 sandbox fact: env proxies fake 502s; bypass them explicitly."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(req, timeout=timeout)


def _envelope(source: str, category: str, message: str) -> dict[str, Any]:
    return store.to_dict(ErrorEnvelope(source=source, category=category, message=message))


def _fetch(url: str, params: dict[str, Any], timeout: int) -> tuple[str | None, dict | None]:
    """Single transport seam (tests monkeypatch this). Returns (body, error)."""
    _ensure_ssl_cert_env()
    query = ("?" + urllib.parse.urlencode(params)) if params else ""
    req = urllib.request.Request(url + query, headers={"User-Agent": str(canon.value("search.user_agent"))})
    try:
        with _urlopen_noproxy(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8"), None
    except Exception as exc:  # envelope, never raise
        category = "http" if getattr(exc, "code", None) else "network"
        source = url.split("/")[2] if "://" in url else url
        return None, _envelope(source, category, f"{type(exc).__name__}: {exc}")


_TAG_RE = re.compile(r"<[^>]+>")

def _strip_tags(text: str | None) -> str:
    return _TAG_RE.sub("", text or "").strip()

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

def restore_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """Rebuild the abstract from OpenAlex inverted index (V1 :1067, verbatim port)."""
    if not inverted_index:
        return ""
    pos: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            pos.append((i, word))
    return " ".join(word for _, word in sorted(pos))


def _candidate(*, title: str, identifiers: dict[str, str], backend: str, abstract: str,
               year: int | None, venue: str | None, cited_by: int | None,
               retracted: bool, checked_backend: str,
               authors: list[str]) -> contracts.PaperCandidate | None:
    if not any(identifiers.values()) or not title.strip():  # blank title fails contract
        return None
    return contracts.PaperCandidate(
        title=title.strip(),
        authors=[a for a in (s.strip() for s in authors) if a],
        identifiers=identifiers,
        discovery_class="direct",
        source_backend=backend,
        abstract=abstract,
        abstract_sha256=contracts.sha256_hex(abstract),
        year=year,
        venue=venue,
        cited_by_count=cited_by,
        retraction={"status": "flagged" if retracted else "none",
                    "checked_backends": [checked_backend] if retracted else [],
                    "checked_at": store.now() if retracted else ""},
    )


def openalex_search(query: str, limit: int = 15) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    body, err = _fetch("https://api.openalex.org/works",
        {"search": query, "per-page": limit, "mailto": str(canon.value("search.polite_pool_mailto"))},
        int(canon.value("search.timeout_seconds")))
    if err or body is None:
        return [], [err or {"source": "openalex", "category": "network", "message": "no body"}]
    works = json.loads(body).get("results", [])
    results, errors = [], []
    for w in works:
        source = (w.get("primary_location") or {}).get("source") or {}
        doi = str(w.get("doi") or "").replace("https://doi.org/", "").strip()
        cand = _candidate(title=str(w.get("title") or ""),
            identifiers={"doi": doi} if doi else {}, backend="openalex",
            abstract=restore_abstract(w.get("abstract_inverted_index")),
            year=w.get("publication_year"), venue=source.get("display_name"),
            cited_by=w.get("cited_by_count"), retracted=bool(w.get("is_retracted")),
            checked_backend="openalex_is_retracted",
            authors=[str((a.get("author") or {}).get("display_name") or "") for a in (w.get("authorships") or [])])
        if cand is None:
            errors.append(_envelope("openalex", "gate", f"row dropped (missing identifier or title): {str(w.get('id'))[:60]}"))
            continue
        results.append(store.to_dict(cand))
    return results, errors


_ARXIV_NS = {"a": "http://www.w3.org/2005/Atom"}


def _respect_arxiv_interval() -> None:
    global _LAST_ARXIV_AT
    interval = float(canon.value("search.arxiv_interval_seconds"))
    now = time.monotonic()
    if _LAST_ARXIV_AT is not None:
        remaining = interval - (now - _LAST_ARXIV_AT)
        if remaining > 0:
            time.sleep(remaining)
    _LAST_ARXIV_AT = time.monotonic()


def arxiv_search(query: str, limit: int = 15) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    _respect_arxiv_interval()
    body, err = _fetch(
        "https://export.arxiv.org/api/query",
        {"search_query": query, "start": 0, "max_results": limit},
        int(canon.value("search.timeout_seconds")),
    )
    if err or body is None:
        return [], [err or {"source": "arxiv", "category": "network", "message": "no body"}]
    results: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        return [], [_envelope("arxiv", "parse", f"xml parse: {exc}")]
    for entry in root.findall("a:entry", _ARXIV_NS):
        arxiv_id = (entry.findtext("a:id", default="", namespaces=_ARXIV_NS) or "").rsplit("/abs/", 1)[-1]
        published = entry.findtext("a:published", default="", namespaces=_ARXIV_NS) or ""
        cand = _candidate(title=(entry.findtext("a:title", default="", namespaces=_ARXIV_NS) or ""),
            identifiers={"arxiv_id": arxiv_id} if arxiv_id else {}, backend="arxiv",
            abstract=(entry.findtext("a:summary", default="", namespaces=_ARXIV_NS) or "").strip(),
            year=int(published[:4]) if published[:4].isdigit() else None, venue="arXiv",
            cited_by=None, retracted=False, checked_backend="arxiv",
            authors=[(n.text or "") for n in entry.findall("a:author/a:name", _ARXIV_NS)])
        if cand is not None:
            results.append(store.to_dict(cand))
    return results, []

def crossref_search(query: str, limit: int = 15) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Crossref discovery + update-to/updated-by retraction channel (M2a)."""
    select = "DOI,title,abstract,author,container-title,published,created,is-referenced-by-count,updated-by,update-to"
    body, err = _fetch("https://api.crossref.org/works", {"query": query, "rows": limit, "select": select}, int(canon.value("search.timeout_seconds")))
    if err or body is None:
        return [], [err or {"source": "crossref", "category": "network", "message": "no body"}]
    try:
        items = json.loads(body).get("message", {}).get("items", [])
    except ValueError as exc:
        return [], [_envelope("crossref", "parse", f"json parse: {exc}")]
    results, errors = [], []
    for it in items:
        doi = str(it.get("DOI") or "").strip()
        cand = _candidate(title=str((it.get("title") or [""])[0] or ""),
            identifiers={"doi": doi} if doi else {}, backend="crossref",
            abstract=_strip_tags(it.get("abstract")), year=_crossref_year(it),
            venue=str((it.get("container-title") or [None])[0] or "") or None,
            cited_by=it.get("is-referenced-by-count"), retracted=_crossref_retracted(it),
            checked_backend="crossref_update_to",
            authors=[f"{a.get('given', '')} {a.get('family', '')}".strip() or str(a.get("name") or "") for a in (it.get("author") or [])])
        if cand is None:
            errors.append(_envelope("crossref", "gate", f"row dropped (missing DOI or title): {str(it.get('DOI'))[:60]}"))
            continue
        results.append(store.to_dict(cand))
    return results, errors

def europepmc_search(query: str, limit: int = 15) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """EuropePMC discovery (M2a, fourth channel; core resultType carries abstracts)."""
    body, err = _fetch("https://www.ebi.ac.uk/europepmc/webservices/rest/search", {"query": query, "format": "json", "pageSize": limit, "resultType": "core"}, int(canon.value("search.timeout_seconds")))
    if err or body is None:
        return [], [err or {"source": "europepmc", "category": "network", "message": "no body"}]
    try:
        hits = json.loads(body).get("resultList", {}).get("result", [])
    except ValueError as exc:
        return [], [_envelope("europepmc", "parse", f"json parse: {exc}")]
    results, errors = [], []
    for r in hits:
        doi = str(r.get("doi") or "").strip()
        pmid = str(r.get("pmid") or "").strip()
        year = str(r.get("pubYear") or "")
        cand = _candidate(title=str(r.get("title") or ""),
            identifiers={"doi": doi} if doi else ({"pmid": pmid} if pmid else {}),
            backend="europepmc", abstract=str(r.get("abstractText") or "").strip(),
            year=int(year) if year.isdigit() else None, venue=r.get("journalTitle"),
            cited_by=r.get("citedByCount"), retracted=False, checked_backend="europepmc",
            authors=[str(a.get("fullName") or a.get("collectiveName") or "") for a in ((r.get("authorList") or {}).get("author") or [])])
        if cand is None:
            errors.append(_envelope("europepmc", "gate", f"hit without identifier dropped: {str(r.get('title'))[:60]}"))
            continue
        results.append(store.to_dict(cand))
    return results, errors

_ADAPTERS = {"openalex": openalex_search, "arxiv": arxiv_search, "crossref": crossref_search, "europepmc": europepmc_search}

def _dedup(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """First-seen wins; repeat hits extend the source trail (source-tracking)."""
    seen: dict[str, dict[str, Any]] = {}
    out: list[dict[str, Any]] = []
    for cand in pool:
        key = cand.get("paper_key", "")
        if key and key in seen:
            seen[key].setdefault("sources", []).extend(cand.get("sources", []))
        elif key:
            seen[key] = cand
            out.append(cand)
    return out


def _resolve_backends(backends: list[str] | None) -> tuple[list[str], dict[str, Any] | None]:
    active = list(canon.value("search.active"))
    chosen = backends or active
    unknown = [b for b in chosen if b not in active]
    if unknown:
        return [], {"ok": False, "error": f"unknown backends {unknown}; active: {active}"}
    return chosen, None


def _run_one(query: str, backend: str, limit: int, pool: list[dict[str, Any]], errors: list[dict[str, Any]]) -> None:
    found, errs = _ADAPTERS[backend](query, limit)
    for cand in found:
        cand.setdefault("sources", []).append({"backend": backend, "query": query})
    pool.extend(found)
    errors.extend(errs)


def search(query: str, limit: int = 15, backends: list[str] | None = None) -> dict[str, Any]:
    """ACTIVE-driven multi-backend recall pool; selection stays with the session model."""
    chosen, err = _resolve_backends(backends)
    if err:
        return err
    pool, errors = [], []
    for backend in chosen:
        _run_one(query, backend, limit, pool, errors)
    return {"ok": True, "query": query, "results": _dedup(pool), "errors": errors}


def search_multi(queries: list[str], limit: int = 15, backends: list[str] | None = None) -> dict[str, Any]:
    """Executor fan-out (gpt-researcher executor borrow, mechanical only).

    Runs each planner-supplied query over ACTIVE backends with per-hit source
    trails, deduped across the whole pool. Planning stays in-session:
    query-brief output feeds `queries`. Envelopes never raise."""
    chosen, err = _resolve_backends(backends)
    if err:
        return err
    clean = [str(q).strip() for q in queries or [] if str(q or "").strip()]
    if not clean:
        return {"ok": False, "error": "at least one query required"}
    pool, errors = [], []
    for query in clean:
        for backend in chosen:
            _run_one(query, backend, limit, pool, errors)
    return {"ok": True, "queries": clean, "results": _dedup(pool), "errors": errors}
