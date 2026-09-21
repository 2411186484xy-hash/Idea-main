"""L2 claims: the append-only machine knowledge layer (corpus-claims.jsonl).

Hard lint at the gate (V1 signature asset): every claim carries a verbatim
quote and a page anchor — missing either is rejected. Views render on the
fly and never land on disk.
"""

from __future__ import annotations

import re
from typing import Any

from . import contracts, runs, store

_QUANTITY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([a-zA-Z%°µ]+)?")
_MEASURE_UNITS = frozenset(
    "% ° °c µ µm um nm mm cm m km ms s min h hz khz mhz ghz px db ev kev mev gev "
    "pa kpa mpa n j w v a mol lx k c".split()
)


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **extra}


def _next_claim_id() -> str:
    today = store.now()[:10].replace("-", "")
    prefix = f"CLM-{today}-"
    max_n = 0
    for row in store.read_jsonl(store.claims_path()):
        cid = str(row.get("id", ""))
        if cid.startswith(prefix):
            try:
                max_n = max(max_n, int(cid.rsplit("-", 1)[1]))
            except ValueError:
                continue
    return f"{prefix}{max_n + 1:03d}"


def _existing_ids() -> set[str]:
    return {str(row.get("id")) for row in store.read_jsonl(store.claims_path())}


def add_claim(payload: dict[str, Any], run_id: str | None = None) -> dict[str, Any]:
    """Append one page-anchored claim; duplicate ids are rejected."""
    data = dict(payload)
    if not data.get("id"):
        data["id"] = _next_claim_id()
    if "page_anchor" in data and not isinstance(data["page_anchor"], int):
        try:
            data["page_anchor"] = int(str(data["page_anchor"]).strip())
        except ValueError:
            return _fail(f"page_anchor must be a page number: {data['page_anchor']!r}")
    if not data.get("created_at"):
        data["created_at"] = store.now()
    if str(data.get("id")) in _existing_ids():
        return _fail(f"duplicate claim id: {data['id']}")
    try:
        claim = contracts.Claim(**data)
    except (ValueError, TypeError) as exc:
        return _fail(f"claim rejected: {exc}")
    store.append_jsonl(store.claims_path(), store.to_dict(claim))
    if run_id:
        run = runs.load(run_id)
        if run is not None and run.status == "active":
            runs.append_trace(run, "CLAIM_ADD", claim.id)
            runs.save(run)
    return {"ok": True, "id": claim.id, "paper_key": claim.paper_key}


def load_claims() -> list[dict[str, Any]]:
    return store.read_jsonl(store.claims_path())


def _quantities(row: dict[str, Any]) -> set[tuple[float, str]]:
    """M2d unit-aware numbers: bare year-like integers are not measurements,
    and a conflict needs the same unit on both sides (mm vs % never clashes)."""
    text = f"{row.get('text', '')} {row.get('quote', '')}"
    out: set[tuple[float, str]] = set()
    for match in _QUANTITY_RE.finditer(text):
        value = float(match.group(1))
        raw = (match.group(2) or "").lower()
        unit = raw if raw in _MEASURE_UNITS else ""
        if not unit and value.is_integer() and 1900 <= value <= 2100:
            continue
        out.add((value, unit))
    return out


def _numeric_clash(left: set[tuple[float, str]], right: set[tuple[float, str]]) -> bool:
    shared = {u for _, u in left} & {u for _, u in right}
    return any({v for v, u in left if u == unit}.isdisjoint({v for v, u in right if u == unit})
               for unit in shared)


def _contradiction_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lightweight rules over the filtered set: opposite verdicts on one
    topic (CONFIRMED vs DEVIATED/NOT_FOUND across papers), or disjoint
    numeric mentions on one topic. Pure derivation, never written to disk."""
    pairs: list[dict[str, Any]] = []
    by_topic: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_topic.setdefault(str(row.get("topic", "")), []).append(row)
    for topic, group in by_topic.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                left, right = group[i], group[j]
                if left.get("paper_key") == right.get("paper_key"):
                    continue
                verdicts = (left.get("verifier_verdict"), right.get("verifier_verdict"))
                ends = (
                    {"id": left.get("id"), "paper_key": left.get("paper_key")},
                    {"id": right.get("id"), "paper_key": right.get("paper_key")},
                )
                if ("CONFIRMED" in verdicts) and not all(v == "CONFIRMED" for v in verdicts):
                    pairs.append(
                        {
                            "kind": "verdict_opposite",
                            "severity": "high",
                            "topic": topic,
                            "a": {**ends[0], "verifier_verdict": verdicts[0]},
                            "b": {**ends[1], "verifier_verdict": verdicts[1]},
                        }
                    )
                nums_left, nums_right = _quantities(left), _quantities(right)
                if nums_left and nums_right and _numeric_clash(nums_left, nums_right):
                    pairs.append(
                        {
                            "kind": "numeric_conflict",
                            "severity": "medium",
                            "topic": topic,
                            "a": ends[0],
                            "b": ends[1],
                            "quantities_a": sorted(nums_left),
                            "quantities_b": sorted(nums_right),
                        }
                    )
    return pairs


def view(
    topic: str | None = None,
    paper_key: str | None = None,
    verdict: str | None = None,
    pairs_only: bool = False,
) -> dict[str, Any]:
    """On-the-fly rendering; filters are optional; nothing is written."""
    rows = load_claims()
    if topic:
        rows = [r for r in rows if str(r.get("topic")) == topic]
    if paper_key:
        rows = [r for r in rows if str(r.get("paper_key")) == paper_key]
    if verdict:
        rows = [r for r in rows if str(r.get("verifier_verdict")) == verdict]
    pairs = _contradiction_pairs(rows)
    if pairs_only:
        involved = {p["a"]["id"] for p in pairs} | {p["b"]["id"] for p in pairs}
        rows = [r for r in rows if r.get("id") in involved]
    by_topic: dict[str, int] = {}
    for r in rows:
        by_topic[str(r.get("topic", "general"))] = by_topic.get(str(r.get("topic", "general")), 0) + 1
    return {"ok": True, "count": len(rows), "topics": by_topic, "claims": rows, "pairs": pairs}
