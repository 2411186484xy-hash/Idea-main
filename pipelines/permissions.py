"""Permissions actually enforced from governance/permissions.json (V2 lesson: no orphan actions)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from . import common

PERMISSIONS_PATH = common.GOVERNANCE_ROOT / "permissions.json"


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


@lru_cache(maxsize=1)
def _policy() -> dict:
    return dict(common.read_json(PERMISSIONS_PATH))  # type: ignore[arg-type]


def check(action: str, reason: str = "") -> Decision:
    policy = _policy()
    actions = policy.get("actions", {})
    if action not in actions:
        return Decision(False, f"unknown action '{action}': default DENY")
    rule = actions[action]
    kind = rule.get("policy")
    if kind == "allow":
        return Decision(True, "allow")
    if kind == "allow_with_reason":
        if reason.strip():
            return Decision(True, "reason recorded")
        return Decision(False, f"action '{action}' requires --reason")
    if kind == "allow_with_recent_backup":
        return Decision(True, "backup freshness must be verified by caller")
    return Decision(False, f"unknown policy '{kind}': default DENY")


def known_actions() -> list[str]:
    return sorted(_policy().get("actions", {}).keys())


def audit_no_orphans(referenced: set[str]) -> list[str]:
    """Every permissions.json action must be referenced by code and vice versa."""
    defined = set(known_actions())
    problems = [f"orphan permission (unreferenced): {a}" for a in sorted(defined - referenced)]
    problems += [f"action without policy: {a}" for a in sorted(referenced - defined)]
    return problems
