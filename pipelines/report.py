"""L3 report: structured task packs for the in-session model (pure read).

The CLI never does cognition; it renders briefs. session-brief is the first
screen with four blocks (M1.6): feedback coverage first, active run states,
lesson digest from the failure ledger, and pending todos. Legacy keys
(purpose/knowledge/stale_warnings) stay for compatibility.
"""

from __future__ import annotations

import hashlib
from typing import Any

from . import canon, contracts, feedback, runs, store

_LESSON_DISPLAY_CAP = 5  # display truncation only, not a governance gate

_QUERY_ROUTES = (
    ("direct", ""),
    ("counter_boundary", " limitations OR counter-evidence OR boundary conditions"),
    ("transfer", " transfer OR analogy OR cross-domain application"),
    ("frontier", " frontier OR emerging OR review"),
)

_ATTACKS = (
    "rename-swap: draw the difference table against the nearest three priors; no delta row holds the idea",
    "shallow-combo: write the coupling mechanism plus an ablation control, or hold",
    "no-disproof: name the fastest falsifying experiment with controls and thresholds",
    "lineage-gap: cite the key prior work or drop the novelty claim",
    "open-prescription: ship data sources, controls, and decision numbers, not directions",
    "venue-fit: name the venue and its bar, or hold",
)


def query_brief(base: str, run_id: str | None = None, topic: str = "") -> dict[str, Any]:
    """M2a + M3.5: mechanical multi-perspective pack + query_log dedup flags.

    --topic derives the base query from the topic pack (key_terms) and appends
    one explicit transfer-family query per transfer_pair, so cross-domain
    retrieval is a first-class perspective, not a manual afterthought."""
    entry = _topic_entry(topic)
    query = (base or "").strip()
    if not query and entry:
        terms = [str(t) for t in (entry.get("key_terms") or [])]
        query = " ".join(terms[:3])
    if not query:
        return {"ok": False, "error": "query (or a known --topic) required"}
    logged: list[dict[str, Any]] = []
    if run_id:
        run = runs.load(run_id)
        if run is None:
            return {"ok": False, "error": f"run not found: {run_id}"}
        logged = list(run.query_log)
    seen: dict[str, list[dict[str, Any]]] = {}
    for entry_row in logged:
        seen.setdefault(str(entry_row.get("query", "")).casefold().strip(), []).append(entry_row)
    perspectives = []
    for route, suffix in _QUERY_ROUTES:
        text = query + suffix
        hits = seen.get(text.casefold().strip(), [])
        perspectives.append({"route": route, "query": text, "duplicate": bool(hits), "hits": hits})
    if entry:
        anchor = str((entry.get("key_terms") or [entry.get("name", "")])[0])
        for pair in entry.get("transfer_pairs") or []:
            if not isinstance(pair, dict):
                continue
            terms = [str(t) for t in (pair.get("method_terms") or [])][:2]
            if not terms:
                continue
            text = f"{' '.join(terms)} {anchor}"
            hits = seen.get(text.casefold().strip(), [])
            perspectives.append({"route": f"transfer:{pair.get('from_field', '')}",
                                 "query": text, "duplicate": bool(hits), "hits": hits})
    out: dict[str, Any] = {"ok": True, "base": query, "run_id": run_id,
                           "perspectives": perspectives, "logged_queries": len(logged)}
    if entry:
        out["topic"] = {"id": entry.get("id"), "name": entry.get("name")}
    return out


def _count_jsonl(path) -> int:
    return len(store.read_jsonl(path))


def _lessons() -> list[dict[str, Any]]:
    rows = store.read_jsonl(store.failure_ledger_path())
    digest: list[dict[str, Any]] = []
    for row in rows[-_LESSON_DISPLAY_CAP:]:
        digest.append(
            {
                "slug": row.get("slug"),
                "stage": row.get("stage"),
                "lesson": row.get("lesson") or row.get("reason"),
                "at": row.get("at"),
            }
        )
    return digest


def _todos(coverage: dict[str, Any], knowledge: dict[str, int]) -> list[str]:
    pending: list[str] = []
    if coverage.get("bootstrap"):
        pending.append("fresh ledger: first researcher verdicts will arm the supply gate")
    if coverage["pending"]:
        pending.append(
            f"backfill {coverage['pending']} researcher verdicts "
            f"(coverage {coverage['decided']}/{coverage['total']})"
        )
    if not coverage["supply_open"]:
        pending.append(
            f"supply closed (ratio {coverage['ratio']} < {coverage['threshold']}): "
            "no new ideas until coverage recovers"
        )
    for warning in runs.stale_warnings():
        pending.append(f"stale run: {warning}")
    if not knowledge["claims"]:
        pending.append("knowledge empty: run search to seed L2 candidates")
    return pending


def _topic_lines() -> list[dict[str, Any]]:
    """Topic pack overview for the first screen (加主题=加数据)."""
    try:
        bank = store.read_json(canon.data_path("knowledge.topics_file"))
    except (ValueError, OSError):
        return []
    out: list[dict[str, Any]] = []
    for entry in bank.get("topics") or []:
        if isinstance(entry, dict):
            out.append({"id": entry.get("id"), "name": entry.get("name"),
                        "status": entry.get("status") or "active"})
    return out


def session_brief() -> dict[str, Any]:
    coverage = feedback.stats()
    knowledge = {
        "claims": _count_jsonl(store.claims_path()),
        "feedback": _count_jsonl(store.feedback_path()),
        "failure_ledger": _count_jsonl(store.failure_ledger_path()),
        "idea_pool": (
            len(store.read_json(store.idea_pool_path())) if store.idea_pool_path().exists() else 0
        ),
        "session_log": _count_jsonl(store.session_log_path()),
    }
    return {
        "ok": True,
        "coverage": coverage,
        "active_runs": runs.active_runs(),
        "topics": _topic_lines(),
        "lessons": _lessons(),
        "todos": _todos(coverage, knowledge),
        "knowledge": knowledge,
        "purpose": str(canon.value("purpose")),
        "stale_warnings": runs.stale_warnings(),
    }


def deepread_brief(paper_key: str, text_md: str) -> dict[str, Any]:
    """M2c: writer/verifier blind-separated pack (paper-qa borrow, design only).

    The verifier book carries the text and nothing else: no writer notes, no
    draft claims. Judgement stays in-session; both books are pure data."""
    key = (paper_key or "").strip()
    text = (text_md or "").strip()
    if not key or not text:
        return {"ok": False, "error": "paper_key and text_md are both required"}
    writer = {"paper_key": key, "text_md": text,
              "task": "extract page-anchored claims (verbatim quote + page_anchor each)"}
    verifier = {"paper_key": key, "text_md": text,
                "task": "verify each claim quote against the text only; "
                        "verdict CONFIRMED|DEVIATED|NOT_FOUND",
                "claims_to_check": [], "sees_writer_notes": False}
    return {"ok": True, "paper_key": key, "chars": len(text),
            "writer": writer, "verifier": verifier, "blind": True}


def _topic_entry(topic_id: str) -> dict[str, Any] | None:
    """Topic pack lookup (加主题=加数据：knowledge/topics.json)."""
    if not topic_id:
        return None
    try:
        bank = store.read_json(canon.data_path("knowledge.topics_file"))
    except (ValueError, OSError):
        return None
    for entry in bank.get("topics") or []:
        if isinstance(entry, dict) and str(entry.get("id")) == topic_id:
            return dict(entry)
    return None


def _collision_sample(seed: str) -> dict[str, Any] | None:
    """Deterministic bank sample (seed hash → index): same seed, same domain."""
    try:
        bank = store.read_json(canon.data_path("knowledge.collision_bank_file"))
    except (ValueError, OSError):
        return None
    domains = [d for d in (bank.get("domains") or []) if isinstance(d, dict)]
    if not domains:
        return None
    digest = hashlib.sha256(seed.casefold().encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(domains)
    return dict(domains[idx])


def idea_brief(seed: str, source_domain: str = "", target_domain: str = "",
               topic: str = "") -> dict[str, Any]:
    """M2f four-in-one (open-collider orchestration borrow, design only).

    Collision triple + failure-lesson injection + 6-attack checklist + novelty
    multi-query plan across ACTIVE backends. Pure read; judgement in-session.
    M3.4 additions: default source/target sampled deterministically from the
    collision bank, the disproof design pack, and the blind quality-card book.
    """
    topic_entry = _topic_entry(topic)
    seed_text = (seed or "").strip() or str((topic_entry or {}).get("name") or "")
    if not seed_text:
        return {"ok": False, "error": "seed (or a known --topic) required"}
    source = (source_domain or "").strip()
    target = (target_domain or "").strip()
    sample = None
    if not source or not target:
        sample = _collision_sample(seed_text)
    if not source and sample:
        source = str(sample.get("domain") or "")
    if not target:
        target = str((topic_entry or {}).get("name") or "") or seed_text
    parts = {"seed": seed_text, "source_domain": source or seed_text, "target_domain": target}
    backends = [str(b) for b in canon.value("search.active")]
    # Novelty checks must be retrievable: build them from the topic's English key
    # terms + the collision bank's slug, never from the Chinese prose triple.
    key_terms = [str(t).strip() for t in ((topic_entry or {}).get("key_terms") or []) if str(t).strip()]
    anchor = key_terms[0] if key_terms else ""
    method = str((sample or {}).get("id") or "").replace("-", " ")
    query_base = " ".join(x for x in (anchor, method) if x).strip() or seed_text
    review_query = f"{anchor or seed_text} review"
    out: dict[str, Any] = {
        "ok": True,
        "collision": parts,
        "lessons": _lessons(),
        "attacks": list(_ATTACKS),
        "novelty_plan": [{"query": f"{query_base} prior work", "backend": b} for b in backends]
        + [{"query": review_query, "backend": b} for b in backends],
        "disproof_pack": {
            "fields": list(contracts.DISPROOF_FIELDS),
            "prompts": {
                "experiment": "fastest falsifying experiment (one concrete run)",
                "controls": "what is held fixed / what is swapped",
                "decision_rule": "numeric pass/fail threshold fixed before running",
                "failure_interpretation": "what a failure would teach (no rescue story)",
            },
            "note": "pure design text; no executable scaffold ships",
        },
        "quality_pack": {
            "dims": list(contracts.QUALITY_DIMS),
            "task": "rescore each dim blind (int 1-5) with a one-line evidence rationale",
            "divergence_rule": 2,
            "revision_hint": "any dim diverging by >=2 from the writer card triggers revision",
            "sees_writer_card": False,
        },
    }
    if topic_entry is not None:
        out["topic"] = {"id": topic_entry.get("id"), "name": topic_entry.get("name"),
                        "frontier_domains": topic_entry.get("frontier_domains") or [],
                        "transfer_pairs": topic_entry.get("transfer_pairs") or []}
    if sample:
        template = str(sample.get("template") or "")
        out["collision_sample"] = {
            "id": sample.get("id"), "domain": sample.get("domain"),
            "principle": sample.get("principle"),
            "template": template.replace("{problem}", parts["seed"]).replace("{anchor}", target),
            "rule": "seed hash → deterministic index over the collision bank",
        }
    return out
