"""Canon loader: governance/workflow_authority.json is the single source of truth."""

from __future__ import annotations

from functools import lru_cache

from . import common

CANON_PATH = common.GOVERNANCE_ROOT / "workflow_authority.json"


@lru_cache(maxsize=1)
def load() -> dict:
    return dict(common.read_json(CANON_PATH))  # type: ignore[arg-type]


def get(dotted: str) -> object:
    """Resolve a `section.sub.key` anchor; raises KeyError with the full anchor on miss."""
    node: object = load()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"canon anchor not found: {dotted}")
        node = node[part]
    return node


def check_identity_sync() -> list[str]:
    """common.py constants must equal canon#identity (single-source guard)."""
    problems: list[str] = []
    identity = get("identity")
    assert isinstance(identity, dict)
    if identity.get("zotero_sidebar_root") != common.ZOTERO_SIDEBAR_ROOT:
        problems.append("zotero_sidebar_root drift: common.py vs canon#identity")
    if tuple(identity.get("zotero_collections", ())) != common.ZOTERO_COLLECTIONS:
        problems.append("zotero_collections drift: common.py vs canon#identity")
    return problems
