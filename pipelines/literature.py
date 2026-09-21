"""Literature discovery: multi-backend envelope retrieval + soft JCR + dual retraction gate.

Best-in-class notes: relevance selection stays with the conversation model over the
FULL recall pool (local rerank is a sort hint only); mechanized prescreen never writes
the formal ledger (see runs.prescreen_append); JCR Q1/Q2 is soft reference only.
"""

from __future__ import annotations

from typing import Any

from . import net

DISCOVERY_CLASSES = ("direct", "counter", "boundary", "transfer")
RETRACTED_MARKERS = ("retract",)


def normalize_openalex(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for w in items:
        out.append(
            {
                "title": w.get("title", ""),
                "doi": w.get("doi", ""),
                "abstract": w.get("abstract", ""),
                "is_retracted": bool(w.get("is_retracted")),
                "cited_by_count": w.get("cited_by_count", 0),
                "backend": "openalex",
            }
        )
    return out


def normalize_arxiv(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "title": it.get("title", ""),
            "arxiv_id": it.get("arxiv_id", ""),
            "abstract": it.get("summary", ""),
            "backend": "arxiv",
        }
        for it in items
    ]


def is_retracted(candidate: dict[str, Any]) -> bool:
    """Dual channel: OpenAlex flag OR Crossref update-to(type=retraction) marker in payload."""
    if candidate.get("is_retracted"):
        return True
    update_to = str(candidate.get("update_to", "")).lower()
    return any(m in update_to for m in RETRACTED_MARKERS) and "retraction" in update_to


def second_pass_verify(candidate: dict[str, Any]) -> dict[str, Any]:
    """Per-candidate hard gate: identifier + retraction check. Returns status envelope."""
    if not any(candidate.get(k) for k in ("doi", "pmid", "arxiv_id", "pdf_sha256")):
        return {"status": "fail", "reason": "no_identifier"}
    if is_retracted(candidate):
        return {"status": "fail_retracted", "reason": "retraction signal"}
    return {"status": "ok"}


def jcr_soft_gate(candidate: dict[str, Any], registry: dict[str, str]) -> str:
    """Soft only: ok / conflict / watchlist. Machine never writes the verified registry."""
    issn = str(candidate.get("issn", "")).strip()
    if not issn:
        return "watchlist"
    quartile = registry.get(issn, "")
    if quartile in ("Q1", "Q2"):
        return "ok"
    if quartile == "conflict":
        return "conflict"
    return "watchlist"


def search(query: str, limit: int = 15) -> dict[str, Any]:
    """Full-recall pool across backends; ranking is a hint, selection happens upstream."""
    pool: list[dict[str, Any]] = []
    errors: list[str] = []
    oa = net.openalex_search(query, limit)
    if oa.ok:
        pool.extend(normalize_openalex(oa.items))
    else:
        errors.extend(oa.errors)
    ax = net.arxiv_search(query, limit)
    if ax.ok:
        pool.extend(normalize_arxiv(ax.items))
    else:
        errors.extend(ax.errors)
    seen: set[str] = set()
    deduped = []
    for cand in pool:
        key = (cand.get("doi") or cand.get("arxiv_id") or cand.get("title", "")).lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(cand)
    return {
        "ok": True,
        "pool": deduped,
        "errors": errors,
        "note": "selection_over_full_pool_by_conversation_model",
    }
