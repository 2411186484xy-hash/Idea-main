"""L2 idea: candidate registration behind the feedback supply gate (M1).

M1 scope is the gate: coverage below the canon threshold hard-refuses
idea-add (V1-RETROSPECTIVE G3.6). The gate function lives in feedback.py
(check_supply) and the L4 CLI calls it before touching the pool, so this
module keeps its single-writer shape with no horizontal imports. Full
incubation (corpus gate 3+1+1, failure-lesson pre-read warn, novelty plan)
lands in M2f; idea-pool.json holds in-flight candidates only.
"""

from __future__ import annotations

from typing import Any

from . import contracts, runs, store


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **extra}


def add_idea(payload: dict[str, Any], run_id: str | None = None) -> dict[str, Any]:
    """Schema validation, then pool append (the CLI enforces the supply gate)."""
    try:
        idea = contracts.IdeaCandidate(**payload)
    except (ValueError, TypeError) as exc:
        return _fail(f"idea rejected: {exc}")
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
    return {"ok": True, "slug": idea.slug}
