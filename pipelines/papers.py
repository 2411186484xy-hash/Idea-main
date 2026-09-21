"""L2 papers: candidate registration gates + rule-based screen-rank.

Gates are plain functions (no registry): identifier presence and retraction
status are hard vetoes at registration. screen-rank orders candidates with a
transparent rule score and an asreview-style stop criterion — ranking is a
hint; selection judgement stays with the session model.
"""

from __future__ import annotations

from typing import Any

from . import canon, contracts, runs, store


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **extra}


def add_paper(run_id: str, payload: dict[str, Any], pdf: str | None = None) -> dict[str, Any]:
    """The only writer of run.paper_candidates (single-writer rule)."""
    if pdf:
        return _fail("paper-add --pdf archiving lands in M2b (library + mirror)")
    run = runs.load(run_id)
    if run is None:
        return _fail(f"run not found: {run_id}")
    if run.status != "active":
        return _fail(f"run is {run.status}; resume it before adding papers")
    try:
        cand = contracts.PaperCandidate(**payload)
    except (ValueError, TypeError) as exc:
        return _fail(f"candidate rejected: {exc}")
    if cand.retraction.get("status") != "none":
        runs.append_trace(run, "RETRACT_HIT", cand.paper_key)
        runs.save(run)
        return _fail(
            f"retraction veto ({cand.retraction.get('status')}): {cand.paper_key}",
            paper_key=cand.paper_key,
        )
    if any(c.paper_key == cand.paper_key for c in run.paper_candidates):
        return _fail(f"duplicate paper_key in run: {cand.paper_key}", paper_key=cand.paper_key)
    cand.screen_status = "pending"
    run.paper_candidates.append(cand)
    run.coverage[cand.discovery_class] = run.coverage.get(cand.discovery_class, 0) + 1
    runs.append_trace(run, "PAPER_ADD", cand.paper_key)
    runs.save(run)
    return {"ok": True, "paper_key": cand.paper_key, "count": len(run.paper_candidates)}


def _score(cand: contracts.PaperCandidate, current_year: int) -> int:
    score = 0
    if cand.evidence:
        score += 2
    score += max(0, len([v for v in cand.identifiers.values() if v]) - 1)
    if (cand.cited_by_count or 0) >= 100:
        score += 3
    elif (cand.cited_by_count or 0) >= 10:
        score += 2
    elif (cand.cited_by_count or 0) >= 1:
        score += 1
    if cand.year and current_year - cand.year <= 3:
        score += 2
    elif cand.year and current_year - cand.year <= 6:
        score += 1
    return score


def screen_rank(run_id: str) -> dict[str, Any]:
    """Rule-based ordering + stop criterion; sets screen_status=ranked."""
    run = runs.load(run_id)
    if run is None:
        return _fail(f"run not found: {run_id}")
    if run.status != "active":
        return _fail(f"run is {run.status}; resume it before screening")
    current_year = int(store.now()[:4])
    vetoed: list[dict[str, Any]] = []
    scored: list[tuple[int, contracts.PaperCandidate]] = []
    for cand in run.paper_candidates:
        if cand.retraction.get("status") != "none":
            vetoed.append({"paper_key": cand.paper_key, "reason": "retraction signal"})
            continue
        scored.append((_score(cand, current_year), cand))
    scored.sort(key=lambda pair: (-pair[0], pair[1].paper_key))
    stop_n = int(canon.value("quotas.screen_stop_n"))
    stop_score = int(canon.value("quotas.screen_stop_score"))
    scores = [s for s, _ in scored]
    tail_low = 0
    for s in reversed(scores):
        if s < stop_score:
            tail_low += 1
        else:
            break
    stop_hint = tail_low >= stop_n
    for _, cand in scored:
        cand.screen_status = "ranked"
    runs.append_trace(run, "SCREEN", f"{len(scored)} ranked, {len(vetoed)} vetoed")
    runs.save(run)
    return {
        "ok": True,
        "run_id": run_id,
        "ranked": [
            {"score": s, "paper_key": c.paper_key, "title": c.title,
             "discovery_class": c.discovery_class, "screen_status": c.screen_status}
            for s, c in scored
        ],
        "vetoed": vetoed,
        "stop_hint": stop_hint,
        "stop_note": (
            f"{tail_low} consecutive candidates below score {stop_score} (criterion: {stop_n})"
            if stop_hint
            else None
        ),
    }


def set_screen_status(run_id: str, paper_key: str, status: str) -> dict[str, Any]:
    """Session model records its selection judgement (selected/rejected)."""
    if status not in ("selected", "rejected"):
        return _fail(f"status must be selected/rejected, got: {status}")
    run = runs.load(run_id)
    if run is None:
        return _fail(f"run not found: {run_id}")
    for cand in run.paper_candidates:
        if cand.paper_key == paper_key:
            cand.screen_status = status
            runs.save(run)
            return {"ok": True, "paper_key": paper_key, "screen_status": status}
    return _fail(f"paper_key not in run: {paper_key}")
