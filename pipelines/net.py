"""L2 net: the single transport seam + shared parsing kit for source adapters.

Every outbound call in the system goes through ``_fetch`` here (tests
monkeypatch it); failures become ErrorEnvelope dicts and never raise.
Parsing helpers shared by all adapters live here too: HTML tag stripping,
JSON body guard, the 600-char inverted-index restore (V1 LST:1870-1878) and
the identifier-gated candidate factory.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any

from . import canon, contracts, store
from .contracts import ErrorEnvelope

_CERT_ENV_SET = False
_ABSTRACT_MAX_CHARS = 600
_TAG_RE = re.compile(r"<[^>]+>")


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


def _fetch_bytes(url: str, params: dict[str, Any], timeout: int) -> tuple[bytes | None, dict | None]:
    """Binary twin of _fetch (PDF downloads); same seam, same envelopes."""
    _ensure_ssl_cert_env()
    query = ("?" + urllib.parse.urlencode(params)) if params else ""
    req = urllib.request.Request(url + query, headers={"User-Agent": str(canon.value("search.user_agent"))})
    try:
        with _urlopen_noproxy(req, timeout=timeout) as resp:
            return resp.read(), None
    except Exception as exc:  # envelope, never raise
        category = "http" if getattr(exc, "code", None) else "network"
        source = url.split("/")[2] if "://" in url else url
        return None, _envelope(source, category, f"{type(exc).__name__}: {exc}")


def _strip_tags(text: str | None) -> str:
    return _TAG_RE.sub("", text or "").strip()


def _json_body(body: str, source: str) -> tuple[dict[str, Any] | None, dict | None]:
    try:
        parsed = json.loads(body)
    except ValueError as exc:
        return None, _envelope(source, "parse", f"json parse: {exc}")
    if not isinstance(parsed, dict):
        return None, _envelope(source, "parse", "json root is not an object")
    return parsed, None


def restore_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """Rebuild the abstract from the OpenAlex inverted index (V1 :1067, 600-char cap)."""
    if not inverted_index:
        return ""
    pos: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            pos.append((i, word))
    text = " ".join(word for _, word in sorted(pos))
    return text if len(text) <= _ABSTRACT_MAX_CHARS else text[:_ABSTRACT_MAX_CHARS] + "…"


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


def _rows_to_candidates(rows: list[dict[str, Any]], mapper, source: str
                        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results, errors = [], []
    for row in rows:
        cand, drop_reason = mapper(row)
        if cand is None:
            errors.append(_envelope(source, "gate", drop_reason))
            continue
        results.append(store.to_dict(cand))
    return results, errors
