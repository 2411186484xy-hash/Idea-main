"""L3 validate: structural checks over canon, runs and ledgers (pure read).

Never a substitute for real research execution. --strict fails on warnings
too; the cold-start target is zero of both.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import canon, contracts, runs, store

_TOPIC_FIELDS = {"id", "name", "status", "problem", "key_terms", "target_domains",
                 "frontier_domains", "transfer_pairs", "negative_terms", "anchor_papers", "venues"}


def _check_canon(errors: list[str]) -> None:
    try:
        problems = canon.check_identity_sync()
        canon.value("search.active")
        canon.value("coverage.routes")
        canon.value("quotas.l2_per_run")
        canon.value("quotas.feedback_coverage_min")
        canon.value("limits.stale_hours")
        canon.value("knowledge.topics_file")
        canon.value("knowledge.collision_bank_file")
    except canon.CanonError as exc:
        errors.append(f"canon anchor missing: {exc}")
        return
    except Exception as exc:  # unloadable / malformed
        errors.append(f"canon unloadable: {exc}")
        return
    errors.extend(problems)
    canon_lines = len(canon.CANON_PATH.read_text(encoding="utf-8").splitlines())
    max_lines = int(canon.value("limits.canon_max_lines"))
    if canon_lines > max_lines:
        errors.append(f"canon exceeds line budget: {canon_lines} > {max_lines}")


def _check_runs(errors: list[str], warnings: list[str]) -> None:
    for d in store.list_run_dirs():
        try:
            run = runs.load(d.name)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if run is None:
            errors.append(f"run dir without run.json: {d.name}")
            continue
        if run.status == "completed":
            errors.append(f"terminal run file leaked (must be deleted on finish): {d.name}")
    warnings.extend(runs.stale_warnings())


def _check_ledger_jsonl(name: str, path, errors: list[str], require_schema: bool) -> None:
    for lineno, raw in store.read_jsonl_raw(path):
        try:
            row = json.loads(raw)
        except ValueError:
            errors.append(f"{name}: line {lineno} is not valid JSON")
            continue
        if require_schema and not store.is_known_schema(row):
            errors.append(f"{name}: line {lineno} has unknown/missing schema_version")


def _check_claims(errors: list[str]) -> None:
    seen: set[str] = set()
    for lineno, raw in store.read_jsonl_raw(store.claims_path()):
        try:
            row = json.loads(raw)
        except ValueError:
            continue  # already reported by ledger walk
        cid = str(row.get("id", ""))
        if cid in seen:
            errors.append(f"claims: duplicate id {cid} (line {lineno})")
        seen.add(cid)
        if not str(row.get("quote", "")).strip():
            errors.append(f"claims: {cid} missing verbatim quote (line {lineno})")
        try:
            if int(row.get("page_anchor", 0)) < 1:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"claims: {cid} bad page_anchor (line {lineno})")


def _check_pool(errors: list[str]) -> None:
    if not store.idea_pool_path().exists():
        return
    try:
        pool = store.read_json(store.idea_pool_path())
        if not isinstance(pool, list):
            errors.append("idea-pool.json must be a list of in-flight candidates")
    except Exception as exc:
        errors.append(f"idea-pool.json unloadable: {exc}")


def _check_session_log(errors: list[str]) -> None:
    for lineno, raw in store.read_jsonl_raw(store.session_log_path()):
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        missing = [k for k in ("at", "run_id", "kind", "papers", "claims", "ideas") if k not in row]
        if missing:
            errors.append(f"session-log: line {lineno} missing {missing}")


def _check_topics(errors: list[str], path: Path | None = None) -> None:
    """Topic registry: the zero-code extension interface for retrieval topics."""
    path = path or canon.data_path("knowledge.topics_file")
    if not path.exists():
        errors.append("knowledge/topics.json missing (topic registry is the extension interface)")
        return
    try:
        doc = store.read_json(path)
    except Exception as exc:
        errors.append(f"topics.json unloadable: {exc}")
        return
    if not store.is_known_schema(doc):
        errors.append("topics.json: unknown/missing schema_version")
    topics = doc.get("topics") if isinstance(doc, dict) else None
    if not isinstance(topics, list) or not topics:
        errors.append("topics.json: 'topics' must be a non-empty list")
        return
    seen: set[str] = set()
    for i, topic in enumerate(topics):
        where = f"topics[{i}]"
        if not isinstance(topic, dict):
            errors.append(f"{where}: not an object")
            continue
        extra = sorted(set(topic) - _TOPIC_FIELDS)
        if extra:
            errors.append(f"{where}: unknown fields {extra}")
        tid = str(topic.get("id", ""))
        if not contracts.TOPIC_ID_RE.match(tid):
            errors.append(f"{where}: bad id {tid!r}")
        if tid in seen:
            errors.append(f"{where}: duplicate id {tid!r}")
        seen.add(tid)
        for key in ("name", "problem"):
            if not str(topic.get(key, "")).strip():
                errors.append(f"{where}: {key} required")
        if topic.get("status") not in ("active", "paused"):
            errors.append(f"{where}: status must be active|paused")
        for key in ("key_terms", "target_domains"):
            val = topic.get(key)
            if not isinstance(val, list) or not val or not all(str(v).strip() for v in val):
                errors.append(f"{where}: {key} must be a non-empty list of strings")
        for key in ("frontier_domains", "negative_terms", "anchor_papers", "venues"):
            val = topic.get(key)
            if not isinstance(val, list) or not all(str(v).strip() for v in val):
                errors.append(f"{where}: {key} must be a list of strings")
        pairs = topic.get("transfer_pairs")
        if not isinstance(pairs, list) or not pairs:
            errors.append(f"{where}: transfer_pairs required (cross-domain route)")
            continue
        for j, pair in enumerate(pairs):
            pair = pair if isinstance(pair, dict) else {}
            missing = [k for k in ("from_field", "method_terms", "to_problem") if not pair.get(k)]
            if missing:
                errors.append(f"{where}.transfer_pairs[{j}]: missing {missing}")


def _check_collision_bank(errors: list[str], path: Path | None = None) -> None:
    path = path or canon.data_path("knowledge.collision_bank_file")
    if not path.exists():
        errors.append("knowledge/collision-bank.json missing (idea-brief collision source)")
        return
    try:
        doc = store.read_json(path)
    except Exception as exc:
        errors.append(f"collision-bank.json unloadable: {exc}")
        return
    if not store.is_known_schema(doc):
        errors.append("collision-bank.json: unknown/missing schema_version")
    domains = doc.get("domains") if isinstance(doc, dict) else None
    if not isinstance(domains, list) or len(domains) < 8:
        errors.append("collision-bank.json: needs >= 8 domains")
        return
    ids: set[str] = set()
    for i, entry in enumerate(domains):
        entry = entry if isinstance(entry, dict) else {}
        missing = [k for k in ("id", "domain", "principle", "template")
                   if not str(entry.get(k, "")).strip()]
        if missing:
            errors.append(f"collision-bank[{i}]: missing {missing}")
        eid = str(entry.get("id", ""))
        if eid in ids:
            errors.append(f"collision-bank[{i}]: duplicate id {eid!r}")
        ids.add(eid)


def _check_ledger_dups(errors: list[str]) -> None:
    seen_fb: dict[tuple[str, str, str], int] = {}
    for lineno, raw in store.read_jsonl_raw(store.feedback_path()):
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        key = (str(row.get("slug", "")), str(row.get("verdict", "")),
               str(row.get("reason", "")).strip())
        if key in seen_fb:
            errors.append(f"feedback: duplicate verdict row {key[0]} ({key[1]}) at line {lineno}")
        else:
            seen_fb[key] = lineno
    seen_runs: dict[str, int] = {}
    for lineno, raw in store.read_jsonl_raw(store.session_log_path()):
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        rid = str(row.get("run_id", ""))
        if rid in seen_runs:
            errors.append(f"session-log: duplicate run_id {rid} at line {lineno}")
        else:
            seen_runs[rid] = lineno


def run_checks() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    _check_canon(errors)
    _check_runs(errors, warnings)
    _check_ledger_jsonl("claims", store.claims_path(), errors, require_schema=True)
    _check_ledger_jsonl("feedback", store.feedback_path(), errors, require_schema=True)
    _check_ledger_jsonl(
        "failure-ledger", store.failure_ledger_path(), errors, require_schema=True
    )
    _check_ledger_jsonl("session-log", store.session_log_path(), errors, require_schema=False)
    _check_claims(errors)
    _check_pool(errors)
    _check_session_log(errors)
    _check_topics(errors)
    _check_collision_bank(errors)
    _check_ledger_dups(errors)
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate(strict: bool = False) -> dict[str, Any]:
    result = run_checks()
    if strict:
        result["ok"] = not result["errors"] and not result["warnings"]
    return result
