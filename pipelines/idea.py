"""Idea incubation: corpus gate 3+1+1, 6-dim quality card, 6 attacks, tiers, feedback loop.

Feedback (accept/reject/uncertain + reason) is the ONLY validation signal.
Reject always writes the failure ledger; frequent reasons distill into anti-pattern cards.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Any

from . import common

QUALITY_DIMS = ("novelty", "rigor", "feasibility", "clarity", "data_availability", "venue_fit")
POOL_PATH = common.KNOWLEDGE_ROOT / "candidate-pool.json"
FEEDBACK_PATH = common.KNOWLEDGE_ROOT / "idea-feedback.jsonl"
FAILURE_PATH = common.KNOWLEDGE_ROOT / "idea_failure_ledger.json"


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_corpus_gate(evidence: dict[str, int]) -> dict[str, Any]:
    need = {"direct_fulltext": 3, "recent": 1, "counter_or_boundary": 1}
    missing = {k: v for k, v in need.items() if int(evidence.get(k, 0)) < v}
    return {"ok": not missing, "missing": missing}


def score_card(scores: dict[str, float]) -> dict[str, Any]:
    missing = [d for d in QUALITY_DIMS if d not in scores]
    if missing:
        return {"ok": False, "error": f"missing dims: {missing}"}
    low = [d for d in QUALITY_DIMS if float(scores[d]) < 2.0]
    return {"ok": True, "hold": bool(low), "low_dims": low}


def _load_pool() -> list[dict[str, Any]]:
    if not POOL_PATH.exists():
        return []
    return list(common.read_json(POOL_PATH))  # type: ignore[arg-type]


def add_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    pool = _load_pool()
    slug = str(candidate.get("slug", "")).strip()
    if not slug:
        return {"ok": False, "error": "slug required"}
    if any(c.get("slug") == slug for c in pool):
        return {"ok": False, "error": f"slug collision: {slug}"}
    entry = {
        **candidate,
        "researcher_verdict": None,
        "researcher_verdict_reason": None,
        "researcher_verdict_at": None,
    }
    pool.append(entry)
    common.write_json(POOL_PATH, pool)
    return {"ok": True, "slug": slug}


def record_feedback(slug: str, verdict: str, reason: str) -> dict[str, Any]:
    if verdict not in ("accept", "reject", "uncertain"):
        return {"ok": False, "error": f"bad verdict: {verdict}"}
    if not reason.strip():
        return {"ok": False, "error": "reason required"}
    pool = _load_pool()
    hit = [c for c in pool if c.get("slug") == slug]
    if not hit:
        return {"ok": False, "error": f"slug not in pool: {slug}"}
    hit[0]["researcher_verdict"] = verdict
    hit[0]["researcher_verdict_reason"] = reason.strip()
    hit[0]["researcher_verdict_at"] = _now()
    common.write_json(POOL_PATH, pool)
    with open(FEEDBACK_PATH, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(
            json.dumps(
                {"slug": slug, "verdict": verdict, "reason": reason.strip(), "at": _now()},
                ensure_ascii=False,
            )
            + "\n"
        )
    if verdict == "reject":
        _append_failure(
            {
                "slug": slug,
                "stage": "researcher_rejection",
                "category": "researcher_judgment",
                "reason": reason.strip(),
            }
        )
    return {"ok": True}


def _append_failure(entry: dict[str, Any]) -> None:
    ledger = list(common.read_json(FAILURE_PATH)) if FAILURE_PATH.exists() else []
    ledger.append({**entry, "at": _now()})
    common.write_json(FAILURE_PATH, ledger)


def feedback_stats() -> dict[str, Any]:
    pool = _load_pool()
    total = len(pool)
    voted = [c for c in pool if c.get("researcher_verdict")]
    return {
        "ok": True,
        "total": total,
        "voted": len(voted),
        "coverage": (len(voted) / total) if total else 0.0,
        "accept": sum(1 for c in voted if c["researcher_verdict"] == "accept"),
        "reject": sum(1 for c in voted if c["researcher_verdict"] == "reject"),
        "uncertain": sum(1 for c in voted if c["researcher_verdict"] == "uncertain"),
    }


CORE_FILES = ("decision-pack.md", "candidate-card.md", "evidence-stack.md", "fastest-disproof.md")


def publish(slug: str, tier: str = "core") -> dict[str, Any]:
    """Core 4 files = complete delivery. Enriched/skeleton are optional variants, never blockers."""
    if tier not in ("core", "enriched", "skeleton"):
        return {"ok": False, "error": f"bad tier: {tier}"}
    dest = common.DELIVERY_ROOT / slug
    if dest.exists() and any(dest.iterdir()):
        return {"ok": False, "error": f"delivery collision: {dest} not empty"}
    dest.mkdir(parents=True, exist_ok=True)
    files = list(CORE_FILES)
    if tier == "enriched":
        files += ["related-work.md", "figure-plan.md", "experiment-canvas.md"]
    for name in files:
        (dest / name).write_text(
            f"# {slug}\n\n> tier={tier} · {name}\n", encoding="utf-8", newline="\n"
        )
    return {"ok": True, "dest": str(dest), "files": files}
