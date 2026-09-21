"""L2 cards + idea-driven L3 + citation-backfill lint + writer-verifier verdicts."""

from __future__ import annotations

import re
from typing import Any

PAGE_ANCHOR_RE = re.compile(r"\(p\.\d+")
FORMULA_PLACEHOLDER_RE = re.compile(r"(TBD|TODO|XXX|待补|占位)", re.IGNORECASE)
L3_PATHS = ("visual-critical", "numeric")


def classify_l3_path(text_layer_marks_per_page: float, has_text_layer: bool) -> str:
    """Heuristic (overridable): formula-dense -> visual-critical; no text layer -> conservative visual."""
    if not has_text_layer:
        return "visual-critical"
    return "visual-critical" if text_layer_marks_per_page >= 8 else "numeric"


def lint_note(note: dict[str, Any], tier: str = "anchor") -> dict[str, Any]:
    """Hard lint: page anchors on every numeric/claim entry; formula placeholders are violations."""
    violations: list[str] = []
    warnings: list[str] = []
    for claim in note.get("key_claims", []):
        text = str(claim.get("text", ""))
        has_number = bool(re.search(r"\d", text))
        if has_number and not PAGE_ANCHOR_RE.search(text):
            violations.append(f"claim missing page anchor: {text[:60]}")
    ledger = str(note.get("formula_ledger", ""))
    if FORMULA_PLACEHOLDER_RE.search(ledger):
        violations.append("formula ledger contains placeholder")
    required_v3 = (
        ["pre_reading_questions", "two_pass_reading", "assumption_ledger"]
        if tier == "anchor"
        else []
    )
    for section in required_v3:
        if section not in note:
            warnings.append(f"v3 section missing ({tier}): {section}")
    return {"ok": not violations, "violations": violations, "warnings": warnings}


def verifier_verdict(note: dict[str, Any], evidence_hits: dict[str, str]) -> dict[str, Any]:
    """Verifier sees text dump + note only. Three-state verdict per claim."""
    verdicts = []
    for claim in note.get("key_claims", []):
        cid = claim.get("id", "?")
        hit = evidence_hits.get(cid, "")
        if hit == "exact":
            verdicts.append({"id": cid, "verdict": "CONFIRMED"})
        elif hit == "partial":
            verdicts.append({"id": cid, "verdict": "DEVIATED"})
        else:
            verdicts.append({"id": cid, "verdict": "NOT_FOUND"})
    return {"verdicts": verdicts}


def l2_card(candidate: dict[str, Any], gap_distance: str = "") -> dict[str, Any]:
    return {
        "title": candidate.get("title", ""),
        "one_line_evidence": candidate.get("abstract", "")[:200],
        "venue": candidate.get("venue", ""),
        "doi": candidate.get("doi", ""),
        "arxiv_id": candidate.get("arxiv_id", ""),
        "evidence_role": candidate.get("discovery_class", "direct"),
        "gap_distance": gap_distance,
        "level": "L2",
    }
