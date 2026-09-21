"""L3 validate: structural checks over canon, runs and ledgers (pure read).

Never a substitute for real research execution. --strict fails on warnings
too; the cold-start target is zero of both.
"""

from __future__ import annotations

import json
from typing import Any

from . import canon, runs, store


def _check_canon(errors: list[str]) -> None:
    try:
        problems = canon.check_identity_sync()
        canon.value("search.active")
        canon.value("coverage.routes")
        canon.value("quotas.l2_per_run")
        canon.value("quotas.feedback_coverage_min")
        canon.value("limits.stale_hours")
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
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate(strict: bool = False) -> dict[str, Any]:
    result = run_checks()
    if strict:
        result["ok"] = not result["errors"] and not result["warnings"]
    return result
