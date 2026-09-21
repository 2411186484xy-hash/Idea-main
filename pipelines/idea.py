"""L2 idea: incubation gates + registration (M2f full scope).

Corpus gate 3+1+1 (>=3 corpus-claim refs + >=1 novelty check + the 6-attack
set the contract enforces); failure-ledger pre-read is a warn-block (pass
--lessons-read after running idea-brief); quality dims scoring <=2 mark hold
dims that publish will refuse. idea-pool.json holds in-flight candidates only.
"""

from __future__ import annotations

from typing import Any

from . import contracts, runs, store


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **extra}


def add_idea(payload: dict[str, Any], run_id: str | None = None,
           lessons_read: bool = False) -> dict[str, Any]:
    """Schema + corpus-gate validation, then pool append (CLI gates supply first)."""
    if not lessons_read:
        return _fail("lesson gate: run idea-brief first, then re-add with --lessons-read")
    try:
        idea = contracts.IdeaCandidate(**payload)
    except (ValueError, TypeError) as exc:
        return _fail(f"idea rejected: {exc}")
    corpus_refs = [r for r in idea.evidence_refs if str(r).startswith("CLM-")]
    if len(corpus_refs) < 3:
        return _fail(f"corpus gate 3+1+1: need >=3 corpus-claim refs, got {len(corpus_refs)}")
    if not idea.novelty_log:
        return _fail("corpus gate 3+1+1: novelty_log needs >=1 executed novelty check")
    pool_path = store.idea_pool_path()
    pool: list[Any] = store.read_json(pool_path) if pool_path.exists() else []
    if not isinstance(pool, list):
        return _fail("idea-pool.json must be a list of in-flight candidates")
    if any(row.get("slug") == idea.slug for row in pool if isinstance(row, dict)):
        return _fail(f"duplicate slug in pool: {idea.slug}")
    pool.append(store.to_dict(idea))
    store.write_json_atomic(pool_path, pool)
    if run_id:
        run = runs.load(run_id)
        if run is not None and run.status == "active":
            runs.append_trace(run, "IDEA_ADD", idea.slug)
            runs.save(run)
    hold_dims = sorted(d for d, card in idea.quality_card.items()
                       if int(card.get("score", 5)) <= 2)
    out: dict[str, Any] = {"ok": True, "slug": idea.slug}
    if hold_dims:
        out["hold"] = {"dims": hold_dims,
                       "note": "publish refuses hold dims until revised"}
    return out
