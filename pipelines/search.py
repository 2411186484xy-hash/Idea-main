"""L2 search: concurrent fan-out over the sources adapters + citation expansion.

The pool is recall-only: which papers matter stays a session-model judgement.
Concurrency is mechanical (canon search.max_concurrency) with deterministic
folding in submission order; envelopes never raise. `expand` walks OpenAlex
citations one hop from a seed DOI (V1 citation_track reduced to ~a page).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import canon, sources


def _resolve_backends(backends: list[str] | None) -> tuple[list[str], dict[str, Any] | None]:
    active = [str(b) for b in canon.value("search.active")]
    available = [str(b) for b in canon.value("search.available")]
    chosen = list(dict.fromkeys(backends or active))
    unknown = [b for b in chosen if b not in active and b not in available]
    if unknown:
        return [], {"ok": False,
                    "error": f"unknown backends {unknown}; active: {active}; available: {available}"}
    return chosen, None


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


def _fold(queries: list[str], limit: int, chosen: list[str]) -> tuple[
        list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, int]]]:
    """Fan (query, backend) tasks out concurrently; fold results in submission order."""
    workers = max(1, int(str(canon.value("search.max_concurrency"))))
    pairs = [(q, b) for q in queries for b in chosen]
    stats = {b: {"found": 0, "errors": 0} for b in chosen}
    pool: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(sources.ADAPTERS[b], q, limit) for q, b in pairs]
        for future, (query, backend) in zip(futures, pairs, strict=True):
            found, errs = future.result()
            for cand in found:
                cand.setdefault("sources", []).append({"backend": backend, "query": query})
            stats[backend]["found"] += len(found)
            stats[backend]["errors"] += len(errs)
            pool.extend(found)
            errors.extend(errs)
    return pool, errors, stats


def _health(stats: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
    """Three-state per channel (V1 zero-recall semantics): ok | empty | error."""
    return {
        backend: {
            "status": "ok" if row["found"] else ("error" if row["errors"] else "empty"),
            "found": row["found"],
            "errors": row["errors"],
        }
        for backend, row in stats.items()
    }


def search(query: str, limit: int = 15, backends: list[str] | None = None) -> dict[str, Any]:
    """ACTIVE-driven multi-backend recall pool; selection stays with the session model."""
    chosen, err = _resolve_backends(backends)
    if err:
        return err
    pool, errors, stats = _fold([query], limit, chosen)
    return {"ok": True, "query": query, "results": _dedup(pool),
            "errors": errors, "channel_health": _health(stats)}


def search_multi(queries: list[str], limit: int = 15, backends: list[str] | None = None) -> dict[str, Any]:
    """Executor fan-out (gpt-researcher executor borrow, mechanical only).

    Runs each planner-supplied query over the chosen backends with per-hit
    source trails, deduped across the whole pool. Planning stays in-session:
    query-brief output feeds `queries`. Envelopes never raise."""
    chosen, err = _resolve_backends(backends)
    if err:
        return err
    clean = [str(q).strip() for q in queries or [] if str(q or "").strip()]
    if not clean:
        return {"ok": False, "error": "at least one query required"}
    pool, errors, stats = _fold(clean, limit, chosen)
    return {"ok": True, "queries": clean, "results": _dedup(pool),
            "errors": errors, "channel_health": _health(stats)}


def expand(seed: str, direction: str = "both", limit: int = 50) -> dict[str, Any]:
    """Citation expansion around a seed DOI: cites (forward) / references (backward)."""
    if direction not in ("cites", "references", "both"):
        return {"ok": False, "error": "direction must be cites|references|both"}
    doi = str(seed or "").strip().removeprefix("doi:").lower()
    if not doi:
        return {"ok": False, "error": "expand needs a seed DOI (doi:10.…) or a bare DOI"}
    steps = ["cites", "references"] if direction == "both" else [direction]
    pool: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for step in steps:
        found, errs = sources.openalex_related(doi, step, limit)
        for cand in found:
            cand.setdefault("sources", []).append(
                {"backend": "openalex", "query": f"{step}:{doi}"})
        pool.extend(found)
        errors.extend(errs)
    return {"ok": True, "seed": f"doi:{doi}", "directions": steps,
            "results": _dedup(pool), "errors": errors}
