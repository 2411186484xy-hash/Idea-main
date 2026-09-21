"""Resilient HTTP: timeouts everywhere, error envelopes (never raise across the facade)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from . import common

DEFAULT_TIMEOUT = 12


@dataclass
class Envelope:
    ok: bool
    items: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "items": self.items, "errors": self.errors}


def get_json(
    url: str, params: dict[str, Any] | None = None, timeout: int = DEFAULT_TIMEOUT
) -> Envelope:
    common.ensure_ssl_cert_env()
    common.disable_proxy_for_local()
    try:
        query = ("?" + urllib.parse.urlencode(params)) if params else ""
        req = urllib.request.Request(
            url + query, headers={"User-Agent": "idea-os-v2 (research; mailto:research@localhost)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Envelope(ok=True, items=[json.loads(resp.read().decode("utf-8"))])
    except Exception as exc:  # envelope, never raise
        return Envelope(ok=False, errors=[f"{url}: {type(exc).__name__}: {exc}"])


def arxiv_search(query: str, max_results: int = 15) -> Envelope:
    """Minimal arXiv client over export.arxiv.org (stdlib only, no dep)."""
    common.ensure_ssl_cert_env()
    try:
        params = urllib.parse.urlencode(
            {"search_query": query, "start": 0, "max_results": max_results}
        )
        req = urllib.request.Request(
            "https://export.arxiv.org/api/query?" + params,
            headers={"User-Agent": "idea-os-v2"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
        import xml.etree.ElementTree as ET

        ns = {"a": "http://www.w3.org/2005/Atom"}
        items = []
        for entry in ET.fromstring(raw).findall("a:entry", ns):
            arxiv_id = (entry.findtext("a:id", default="", namespaces=ns) or "").rsplit("/abs/", 1)[
                -1
            ]
            items.append(
                {
                    "source": "arxiv",
                    "arxiv_id": arxiv_id,
                    "title": (entry.findtext("a:title", default="", namespaces=ns) or "").strip(),
                    "summary": (
                        entry.findtext("a:summary", default="", namespaces=ns) or ""
                    ).strip(),
                    "published": entry.findtext("a:published", default="", namespaces=ns),
                }
            )
        return Envelope(ok=True, items=items)
    except Exception as exc:
        return Envelope(ok=False, errors=[f"arxiv: {type(exc).__name__}: {exc}"])


def openalex_search(query: str, limit: int = 15) -> Envelope:
    env = get_json("https://api.openalex.org/works", {"search": query, "per-page": limit})
    if not env.ok:
        return env
    works = env.items[0].get("results", []) if env.items else []
    out = []
    for w in works:
        out.append(
            {
                "source": "openalex",
                "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                "title": w.get("title") or "",
                "abstract": w.get("abstract") or "",
                "is_retracted": bool(w.get("is_retracted")),
                "cited_by_count": w.get("cited_by_count", 0),
                "publication_year": w.get("publication_year"),
            }
        )
    return Envelope(ok=True, items=out)
