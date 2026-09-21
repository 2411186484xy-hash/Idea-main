"""L2 feedback: researcher verdict ledger + coverage + V1 stock import.

The only validation signal (verdict+reason required, V1-proven). coverage()
is first-screen data (V1-RETROSPECTIVE G3.5) and the supply gate (G3.6):
idea-add hard-refuses while coverage sits below the canon threshold.
feedback-import-v1 scans the delivery root READ-ONLY; it never writes back
to E-drive files (V1 test_dir_writeback_proves the direction: verdicts flow
out of researcher-decision.json, the file itself stays untouched).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import canon, contracts, runs, store


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **extra}


def add_feedback(
    slug: str,
    verdict: str,
    reason: str,
    run_id: str | None = None,
    at: str | None = None,
) -> dict[str, Any]:
    """Append one researcher verdict; rejects bad verdicts and empty reasons."""
    try:
        entry = contracts.Feedback(
            slug=slug.strip(),
            verdict=verdict,
            reason=reason.strip(),
            at=at or store.now(),
        )
    except (ValueError, TypeError) as exc:
        return _fail(f"feedback rejected: {exc}")
    store.append_jsonl(store.feedback_path(), store.to_dict(entry))
    if verdict == "reject":
        lesson = contracts.FailureEntry(slug=entry.slug, stage="verdict",
                                        reason=entry.reason, lesson=entry.reason,
                                        at=entry.at)
        store.append_jsonl(store.failure_ledger_path(), store.to_dict(lesson))
    if run_id:
        run = runs.load(run_id)
        if run is not None and run.status == "active":
            runs.append_trace(run, "FEEDBACK", entry.slug)
            runs.save(run)
    return {"ok": True, "slug": entry.slug, "verdict": entry.verdict}


def load_feedback() -> list[dict[str, Any]]:
    return store.read_jsonl(store.feedback_path())


def stats() -> dict[str, Any]:
    """Coverage: decided (accept+reject) over total; uncertain rows are pending."""
    rows = load_feedback()
    counts = {"accept": 0, "reject": 0, "uncertain": 0}
    for row in rows:
        verdict = row.get("verdict")
        if verdict in counts:
            counts[verdict] += 1
    total = len(rows)
    decided = counts["accept"] + counts["reject"]
    threshold = float(canon.value("quotas.feedback_coverage_min"))
    ratio = decided / total if total else 0.0
    bootstrap = total == 0
    return {
        "total": total,
        "verdict_counts": counts,
        "decided": decided,
        "pending": counts["uncertain"],
        "ratio": round(ratio, 4),
        "threshold": threshold,
        # Fresh-start bootstrap: with no history there is nothing unprocessed,
        # so the gate's purpose is vacuous and supply opens. The first verdict
        # row arms the ratio rule; gaming it needs a git-visible ledger wipe.
        "bootstrap": bootstrap,
        "supply_open": bootstrap or ratio >= threshold,
    }


def check_supply() -> dict[str, Any]:
    """Supply gate for idea-add: closed until researcher backfill arrives."""
    current = stats()
    if current["bootstrap"]:
        return {"open": True, "reason": "fresh ledger, no history to backfill (first-boot)"}
    if current["supply_open"]:
        return {
            "open": True,
            "reason": f"feedback coverage {current['decided']}/{current['total']}",
        }
    return {
        "open": False,
        "reason": (
            f"supply closed: feedback coverage {current['decided']}/{current['total']} "
            f"(ratio {current['ratio']} < {current['threshold']}); "
            "backfill researcher verdicts first"
        ),
    }


def _slugify(raw: object) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", str(raw or "").lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if slug and not contracts.SLUG_RE.match(slug):
        slug = f"v1-{slug}"
    return slug


def import_v1(root: Path | None = None) -> dict[str, Any]:
    """Backfill the 29 stock verdicts (read-only scan, idempotent rerun).

    Maps researcher_confirmed -> accept, everything else -> uncertain with an
    explicit awaiting-backfill note (a machine auto-approval is not a verdict).
    """
    base = Path(root) if root is not None else canon.delivery_root()
    if not base.is_dir():
        return _fail(f"delivery root not found: {base}")
    existing = {str(row.get("slug")) for row in load_feedback()}
    scanned = 0
    imported = 0
    skipped: list[dict[str, Any]] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        decision_file = child / "researcher-decision.json"
        if not decision_file.exists():
            skipped.append({"dir": child.name, "reason": "no researcher-decision.json"})
            continue
        scanned += 1
        try:
            doc = json.loads(decision_file.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            skipped.append({"dir": child.name, "reason": f"unreadable: {exc}"})
            continue
        decision = str(doc.get("decision") or "").strip()
        verdict = "accept" if decision == "researcher_confirmed" else "uncertain"
        slug = _slugify(doc.get("candidate_id") or child.name)
        if not contracts.SLUG_RE.match(slug):
            skipped.append(
                {"dir": child.name, "reason": f"slug not salvageable: {doc.get('candidate_id')!r}"}
            )
            continue
        if slug in existing:
            skipped.append({"dir": child.name, "slug": slug, "reason": "already imported"})
            continue
        parts = [f"V1 import from {child.name}", f"decision={decision or '?'}"]
        if doc.get("approved_by"):
            parts.append(f"approved_by={doc['approved_by']}")
        if doc.get("note"):
            parts.append(f"note={doc['note']}")
        portfolio = doc.get("portfolio") or {}
        if isinstance(portfolio, dict) and portfolio.get("tier"):
            parts.append(f"portfolio_tier={portfolio['tier']}")
        if verdict == "uncertain":
            parts.append("awaiting researcher backfill (machine auto-approval is not a verdict)")
        try:
            entry = contracts.Feedback(
                slug=slug,
                verdict=verdict,
                reason="; ".join(parts),
                at=str(doc.get("decided_at") or store.now()),
            )
        except (ValueError, TypeError) as exc:
            skipped.append({"dir": child.name, "reason": f"contract rejected: {exc}"})
            continue
        store.append_jsonl(store.feedback_path(), store.to_dict(entry))
        existing.add(slug)
        imported += 1
    return {
        "ok": True,
        "root": str(base),
        "scanned": scanned,
        "imported": imported,
        "skipped": skipped,
        "coverage": stats(),
    }
