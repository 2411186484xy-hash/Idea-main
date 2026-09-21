"""L2 claims: the append-only machine knowledge layer (corpus-claims.jsonl).

Hard lint at the gate (V1 signature asset): every claim carries a verbatim
quote and a page anchor — missing either is rejected. Views render on the
fly and never land on disk.
"""

from __future__ import annotations

from typing import Any

from . import contracts, runs, store


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


def view(
    topic: str | None = None,
    paper_key: str | None = None,
    verdict: str | None = None,
) -> dict[str, Any]:
    """On-the-fly rendering; filters are optional; nothing is written."""
    rows = load_claims()
    if topic:
        rows = [r for r in rows if str(r.get("topic")) == topic]
    if paper_key:
        rows = [r for r in rows if str(r.get("paper_key")) == paper_key]
    if verdict:
        rows = [r for r in rows if str(r.get("verifier_verdict")) == verdict]
    by_topic: dict[str, int] = {}
    for r in rows:
        by_topic[str(r.get("topic", "general"))] = by_topic.get(str(r.get("topic", "general")), 0) + 1
    return {"ok": True, "count": len(rows), "topics": by_topic, "claims": rows}
