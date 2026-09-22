"""L2 idea: incubation gates + registration (M2f full scope).

Corpus gate 3+1+1 (>=3 corpus-claim refs + >=1 novelty check + the 6-attack
set the contract enforces); failure-ledger pre-read is a warn-block (pass
--lessons-read after running idea-brief); quality dims scoring <=2 mark hold
dims that publish will refuse. idea-pool.json holds in-flight candidates only.
"""

from __future__ import annotations

import re
from typing import Any

from . import canon, contracts, runs, store


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **extra}


_CJK_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_LATIN_RE = re.compile(r"[a-z0-9]{3,}")


def _sig_words(text: str) -> set[str]:
    """V1 core/idea.py:506-524 移植：拉丁 ≥3 字符词 + 中文 2 字 gram，去停用词。"""
    stop = {str(w).casefold() for w in canon.value("ideas.stopwords")}
    toks = _LATIN_RE.findall((text or "").casefold())
    grams: list[str] = []
    for zh in _CJK_RE.findall(text or ""):
        if len(zh) <= 4:
            grams.append(zh)
        else:
            grams.extend(zh[i:i + 2] for i in range(len(zh) - 1))
    return {t for t in [*toks, *grams] if t not in stop and len(t) >= 2}


def _avoidance(title: str, seed: str = "") -> dict[str, Any]:
    """V1 双阈值近似拦截（含 R1C2 停用词修正）：硬命中即拒，弱命中入审计。"""
    cfg = canon.value("ideas.avoidance") or {}
    words = _sig_words(title)
    if len(words) < 3 and seed:
        words |= _sig_words(seed)
    blocked: list[dict[str, Any]] = []
    weak: list[dict[str, Any]] = []
    for row in store.read_jsonl(store.failure_ledger_path()):
        other = _sig_words(f"{row.get('title', '')} {row.get('slug', '')} {row.get('reason', '')}")
        overlap = len(words & other)
        union = len(words | other)
        jacc = overlap / union if union else 0.0
        if not (overlap >= int(cfg.get("report_overlap", 3))
                or jacc >= float(cfg.get("report_jaccard", 0.35))):
            continue
        is_block = (overlap >= int(cfg.get("block_overlap", 4))
                    or (overlap >= 3 and jacc >= float(cfg.get("block_jaccard", 0.4))))
        entry = {"ledger_slug": row.get("slug"), "overlap": overlap, "jaccard": round(jacc, 3),
                 "lesson": row.get("lesson") or row.get("reason"), "blocked": is_block}
        (blocked if is_block else weak).append(entry)
    return {"blocked": blocked, "weak": weak}


def add_idea(payload: dict[str, Any], run_id: str | None = None,
           lessons_read: bool = False) -> dict[str, Any]:
    """Schema + corpus-gate validation, then pool append (CLI gates supply first)."""
    if not lessons_read:
        return _fail("lesson gate: run idea-brief first, then re-add with --lessons-read")
    try:
        idea = contracts.IdeaCandidate(**payload)
    except (ValueError, TypeError) as exc:
        return _fail(f"idea rejected: {exc}")
    avoid = _avoidance(idea.title, str(idea.collision.get("seed") or ""))
    if avoid["blocked"]:
        return _fail(
            "failure-ledger avoidance: title too close to rejected work — revise or point "
            "at the ledger row before re-adding",
            hits=avoid["blocked"],
        )
    if idea.novelty_log and all(str(e.get("result")) == "empty" for e in idea.novelty_log) \
            and not idea.screening_note.strip():
        return _fail(
            "novelty degradation: every check came back empty — record the downgrade in "
            "screening_note (zero hits means reach too low, not novelty)"
        )
    corpus_refs = [r for r in idea.evidence_refs if str(r).startswith("CLM-")]
    if len(corpus_refs) < 3:
        return _fail(f"corpus gate 3+1+1: need >=3 corpus-claim refs, got {len(corpus_refs)}")
    if not idea.novelty_log:
        return _fail("corpus gate 3+1+1: novelty_log needs >=1 executed novelty check")
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
    hold_dims = sorted(d for d, card in idea.quality_card.items()
                       if int(card.get("score", 5)) <= 2)
    out: dict[str, Any] = {"ok": True, "slug": idea.slug}
    if avoid["weak"]:
        out["avoidance_weak"] = avoid["weak"]
    if hold_dims:
        out["hold"] = {"dims": hold_dims,
                       "note": "publish refuses hold dims until revised"}
    return out


def _hold_dims(idea_dict: dict[str, Any]) -> list[str]:
    card = idea_dict.get("quality_card") or {}
    return sorted(d for d, entry in card.items() if int((entry or {}).get("score", 5)) <= 2)


def _render_pack(idea_dict: dict[str, Any]) -> dict[str, str]:
    """M3.4 delivery pack: idea/evidence/novelty/disproof (V1 DEC-0032/0035 + 设计件)."""
    slug = idea_dict["slug"]
    collision = idea_dict.get("collision", {})
    quality = "\n".join(f"- {d}: { (c or {}).get('score') } — {(c or {}).get('rationale', '')}"
                        for d, c in (idea_dict.get("quality_card") or {}).items())
    attacks = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(idea_dict.get("attacks", [])))
    refs = "\n".join(f"- {r}" for r in idea_dict.get("evidence_refs", []))
    novelty = "\n".join(f"- {n.get('query')} [{n.get('backend')}] → {n.get('top_match')}: "
                        f"{n.get('note')}" for n in idea_dict.get("novelty_log", []))
    idea_md = (f"# {idea_dict.get('title', slug)}\n\nslug: `{slug}`\n\n"
               f"## Hypothesis\n\n{idea_dict.get('hypothesis', '')}\n\n"
               f"## Collision\n\nseed: {collision.get('seed', '')}\n"
               f"source: {collision.get('source_domain', '')}\n"
               f"target: {collision.get('target_domain', '')}\n\n"
               f"## Quality card\n\n{quality}\n\n## Attacks\n\n{attacks}\n")
    evidence_md = f"# Evidence — {slug}\n\n## Corpus refs (gate 3+1+1)\n\n{refs}\n"
    novelty_md = f"# Novelty — {slug}\n\n## Checks\n\n{novelty}\n\n## Attacks\n\n{attacks}\n"
    disproof = idea_dict.get("disproof") or {}
    disproof_md = (f"# Disproof design — {slug}\n\n"
                   f"## Falsifying experiment\n\n{disproof.get('experiment', '')}\n\n"
                   f"## Controls\n\n{disproof.get('controls', '')}\n\n"
                   f"## Decision rule\n\n{disproof.get('decision_rule', '')}\n\n"
                   f"## Failure interpretation\n\n{disproof.get('failure_interpretation', '')}\n")
    return {"idea.md": idea_md, "evidence.md": evidence_md, "novelty.md": novelty_md,
            "disproof.md": disproof_md}


def publish(slug: str, run_id: str | None = None) -> dict[str, Any]:
    """M2h: 5-file delivery (incl. disproof.md) + mirror + builtin check + pool removal.

    Delivery root is the source of truth; the pool only holds in-flight work.
    researcher-decision.json ships pending_backfill so feedback-import-v1 can
    later close the loop without touching delivered files."""
    pool_path = store.idea_pool_path()
    pool: list[Any] = store.read_json(pool_path) if pool_path.exists() else []
    if not isinstance(pool, list):
        return _fail("idea-pool.json must be a list of in-flight candidates")
    target = next((r for r in pool if isinstance(r, dict) and r.get("slug") == slug), None)
    if target is None:
        return _fail(f"slug not in pool (in-flight only): {slug}")
    hold = _hold_dims(target)
    if hold:
        return _fail(f"publish refused: hold dims {hold} until revised", slug=slug)
    pack = _render_pack(target)
    decision = {"candidate_id": slug, "decision": "pending_backfill",
                "decided_at": store.now(),
                "note": "published by idea-os v2; awaiting researcher verdict"}
    dst_dir = canon.delivery_root() / slug
    mirror_dir = canon.idea_mirror_root() / slug
    try:
        for name, body in pack.items():
            store.write_text_atomic(dst_dir / name, body)
        store.write_json_atomic(dst_dir / "researcher-decision.json", decision)
        for name in pack:
            store.copy_file(dst_dir / name, mirror_dir / name)
        store.copy_file(dst_dir / "researcher-decision.json",
                        mirror_dir / "researcher-decision.json")
    except OSError as exc:
        return _fail(f"publish failed: {exc}", slug=slug)
    names = sorted([*pack, "researcher-decision.json"])
    got = sorted(p.name for p in dst_dir.iterdir() if p.is_file())
    mirrored = sorted(p.name for p in mirror_dir.iterdir() if p.is_file())
    bad_sha = [n for n in names
               if store.sha256_file(dst_dir / n) != store.sha256_file(mirror_dir / n)]
    if got != names or mirrored != names or bad_sha:
        return _fail(f"delivery check failed: files={got} mirror={mirrored} sha_bad={bad_sha}",
                     slug=slug)
    store.write_json_atomic(pool_path, [r for r in pool if r is not target])
    if run_id:
        run = runs.load(run_id)
        if run is not None and run.status == "active":
            runs.append_trace(run, "PUBLISH", slug)
            runs.save(run)
    return {"ok": True, "slug": slug, "files": names, "dir": str(dst_dir),
            "mirror": str(mirror_dir), "sha_match": True}


def backup_verify() -> dict[str, Any]:
    """M2h: backup freshness (name parity) + SHA restore check.

    Delivery artifacts are small text files, so every file's SHA is verified
    (no proportional sampling — the extra file from M3.4 made sampling miss
    tampering in unsampled names)."""
    delivery, mirror = canon.delivery_root(), canon.idea_mirror_root()
    if not delivery.is_dir():
        return _fail(f"delivery root not found: {delivery}")
    mismatches: list[str] = []
    dirs, sampled = 0, 0
    for child in sorted(delivery.iterdir()):
        if not child.is_dir():
            continue
        dirs += 1
        twin = mirror / child.name
        want = sorted(p.name for p in child.iterdir() if p.is_file())
        have = sorted(p.name for p in twin.iterdir() if p.is_file()) if twin.is_dir() else []
        if want != have:
            mismatches.append(f"{child.name}: delivery={want} mirror={have}")
            continue
        for name in want:
            sampled += 1
            if store.sha256_file(child / name) != store.sha256_file(twin / name):
                mismatches.append(f"{child.name}/{name}: SHA mismatch")
    if mismatches:
        return {"ok": False, "error": f"backup mismatch: {mismatches}",
                "dirs": dirs, "sampled": sampled, "mismatches": mismatches}
    return {"ok": True, "dirs": dirs, "sampled": sampled, "mismatches": []}
