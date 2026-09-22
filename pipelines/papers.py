"""L2 papers: candidate registration gates + rule-based screen-rank.

Gates are plain functions (no registry): identifier presence and retraction
status are hard vetoes at registration. screen-rank orders candidates with a
transparent rule score and an asreview-style stop criterion — ranking is a
hint; selection judgement stays with the session model.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import canon, contracts, pdf, runs, store


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **extra}


def _safe_dirname(paper_key: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", paper_key).strip("_") or "paper"


def archive_pdf(paper_key: str, src: str) -> dict[str, Any]:
    """M2b: library archive + backup mirror with SHA agreement (paper-add owns it).

    Layout (user-ruled): <paper_root>/library/<paper_key>/ + mirror under
    <paper_mirror_root>/library/<paper_key>/. Forbidden source roots are
    refused before any byte moves.
    """
    if canon.is_forbidden(src):
        return _fail(f"pdf source inside a forbidden root: {src}")
    origin = Path(src)
    if not origin.is_file():
        return _fail(f"pdf not found: {src}")
    gate_ok, gate_detail = pdf.verify_file(origin)
    if not gate_ok:
        return _fail(f"pdf integrity gate: {gate_detail}")
    leaf = _safe_dirname(paper_key)
    dst = canon.paper_root() / "library" / leaf / origin.name
    mirror = canon.paper_mirror_root() / "library" / leaf / origin.name
    try:
        store.copy_file(origin, dst)
        store.copy_file(dst, mirror)
    except OSError as exc:
        return _fail(f"pdf archive failed: {exc}")
    sha, mirror_sha = store.sha256_file(dst), store.sha256_file(mirror)
    if sha != mirror_sha:
        return _fail(f"mirror SHA mismatch for {paper_key}: {sha[:12]} != {mirror_sha[:12]}")
    return {"ok": True, "paper_key": paper_key, "library": str(dst),
            "mirror": str(mirror), "sha256": sha, "sha_match": True}


def add_paper(run_id: str, payload: dict[str, Any], pdf: str | None = None) -> dict[str, Any]:
    """The only writer of run.paper_candidates (single-writer rule)."""
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
    archived: dict[str, Any] | None = None
    if pdf:
        archived = archive_pdf(cand.paper_key, pdf)
        if not archived["ok"]:
            return archived
    cand.screen_status = "pending"
    run.paper_candidates.append(cand)
    run.coverage[cand.discovery_class] = run.coverage.get(cand.discovery_class, 0) + 1
    runs.append_trace(run, "PAPER_ADD", cand.paper_key)
    runs.save(run)
    out: dict[str, Any] = {"ok": True, "paper_key": cand.paper_key,
                           "count": len(run.paper_candidates)}
    if archived:
        out["archive"] = archived
    return out


def add_batch(run_id: str, entries: list[Any]) -> dict[str, Any]:
    """M3.5 batch mode: every entry passes the same gates; one summary report.

    Entry = candidate payload (+ optional "pdf" path). Replay is idempotent in
    state: keys already in the run come back as duplicates and change nothing.
    """
    if not isinstance(entries, list) or not entries:
        return _fail("batch must be a non-empty JSON list of candidate payloads")
    run = runs.load(run_id)
    if run is None:
        return _fail(f"run not found: {run_id}")
    if run.status != "active":
        return _fail(f"run is {run.status}; resume it before adding papers")
    results: list[dict[str, Any]] = []
    added, failed = 0, 0
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            results.append({"index": i, "ok": False, "error": "entry must be a JSON object"})
            failed += 1
            continue
        payload = {k: v for k, v in entry.items() if k != "pdf"}
        pdf = str(entry.get("pdf") or "").strip() or None
        out = add_paper(run_id, payload, pdf=pdf)
        if out.get("ok"):
            added += 1
            results.append({"index": i, "ok": True, "paper_key": out.get("paper_key")})
        else:
            failed += 1
            results.append({"index": i, "ok": False, "error": out.get("error"),
                            "paper_key": out.get("paper_key")})
    fresh = runs.load(run_id)
    return {"ok": failed == 0 and added > 0, "run_id": run_id, "added": added,
            "failed": failed, "count": len(fresh.paper_candidates) if fresh else 0,
            "results": results}


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


def stop_consecutive_low(scores: list[int], stop_score: int, stop_n: int) -> dict[str, Any]:
    """asreview NConsecutiveIrrelevant analog: tail run below the low bar."""
    tail_low = 0
    for s in reversed(scores):
        if s < stop_score:
            tail_low += 1
        else:
            break
    return {"name": "consecutive_low", "triggered": tail_low >= stop_n,
            "detail": f"{tail_low} consecutive below {stop_score} (criterion: {stop_n})"}


def stop_all_low(scores: list[int], stop_score: int, stop_n: int) -> dict[str, Any]:
    """Whole-pool stopper: nothing clears the bar and the pool is sizable."""
    low = sum(1 for s in scores if s < stop_score)
    triggered = bool(scores) and low == len(scores) and len(scores) >= stop_n
    return {"name": "all_low", "triggered": triggered,
            "detail": f"{low}/{len(scores)} below {stop_score} (criterion: {stop_n})"}


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
    stoppers = [stop_consecutive_low(scores, stop_score, stop_n),
                stop_all_low(scores, stop_score, stop_n)]
    stop_hint = any(s["triggered"] for s in stoppers)
    balance: dict[str, int] = {}
    for _, cand in scored:
        balance[cand.discovery_class] = balance.get(cand.discovery_class, 0) + 1
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
        "stoppers": stoppers,
        "coverage_balance": balance,
        "stop_hint": stop_hint,
        "stop_note": next((s["detail"] for s in stoppers if s["triggered"]), None),
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
