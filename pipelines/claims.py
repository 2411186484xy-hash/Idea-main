"""Claims hub: knowledge/corpus-claims.jsonl is the only machine knowledge layer."""

from __future__ import annotations

import json
from typing import Any

from . import common

CLAIMS_PATH = common.KNOWLEDGE_ROOT / "corpus-claims.jsonl"
REQUIRED_FIELDS = ("id", "paper_key", "text", "confidence", "verifier_verdict", "page_anchors")


def append_claim(claim: dict[str, Any]) -> dict[str, Any]:
    missing = [f for f in REQUIRED_FIELDS if f not in claim]
    if missing:
        return {"ok": False, "error": f"missing fields: {missing}"}
    CLAIMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CLAIMS_PATH, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(claim, ensure_ascii=False, sort_keys=True) + "\n")
    return {"ok": True, "id": claim["id"]}


def load_claims() -> list[dict[str, Any]]:
    if not CLAIMS_PATH.exists():
        return []
    out = []
    for line in CLAIMS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def contradiction_matrix() -> dict[str, Any]:
    """Render view: group claims by topic tag, surface CONFIRMED vs contested."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for claim in load_claims():
        groups.setdefault(str(claim.get("topic", "general")), []).append(claim)
    matrix = {}
    for topic, claims in groups.items():
        confirmed = sum(
            1
            for c in claims
            if c.get("verdict") == "CONFIRMED" or c.get("verifier_verdict") == "CONFIRMED"
        )
        matrix[topic] = {
            "n": len(claims),
            "confirmed": confirmed,
            "contested": len(claims) - confirmed,
        }
    return {"ok": True, "matrix": matrix}


def record_verdict(claim_id: str, verdict: str) -> dict[str, Any]:
    if verdict not in ("CONFIRMED", "DEVIATED", "NOT_FOUND"):
        return {"ok": False, "error": f"bad verdict: {verdict}"}
    claims = load_claims()
    hit = [c for c in claims if c.get("id") == claim_id]
    if not hit:
        return {"ok": False, "error": "claim not found"}
    hit[0]["verifier_verdict"] = verdict
    CLAIMS_PATH.write_text(
        "\n".join(json.dumps(c, ensure_ascii=False, sort_keys=True) for c in claims) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {"ok": True}
