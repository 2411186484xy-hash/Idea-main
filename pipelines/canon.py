"""L1 canon: governance/workflow_authority.json is the single source of values.

Every numeric/string value lives here with a `why`; code never restates
numbers. The four E-drive roots are read from canon#identity with IDEAOS_*
env overrides (test redirection, zero hardcoding).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANON_PATH = REPO_ROOT / "governance" / "workflow_authority.json"


class CanonError(KeyError):
    pass


@lru_cache(maxsize=1)
def load() -> dict:
    return dict(_load_raw())


def _load_raw() -> dict:
    import json

    return json.loads(CANON_PATH.read_text(encoding="utf-8"))


def entry(dotted: str) -> object:
    """Resolve `section.key`; raises CanonError with the anchor on miss."""
    node: object = load()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise CanonError(f"canon anchor not found: {dotted}")
        node = node[part]
    return node


def value(dotted: str) -> object:
    """Entry value: {value, why} wrappers are unwrapped, prose passes through."""
    node = entry(dotted)
    if isinstance(node, dict) and "value" in node and "why" in node:
        return node["value"]
    return node


def _root(name: str, env_var: str) -> Path:
    override = os.environ.get(env_var)
    if override:
        return Path(override)
    return Path(str(value(f"identity.{name}")))


def paper_root() -> Path:
    return _root("paper_root", "IDEAOS_PAPER_ROOT")


def delivery_root() -> Path:
    return _root("delivery_root", "IDEAOS_DELIVERY_ROOT")


def paper_mirror_root() -> Path:
    return _root("paper_mirror_root", "IDEAOS_PAPER_MIRROR_ROOT")


def idea_mirror_root() -> Path:
    return _root("idea_mirror_root", "IDEAOS_IDEA_MIRROR_ROOT")


def forbidden_roots() -> list[str]:
    return [str(r) for r in value("identity.forbidden_input_roots")]


def is_forbidden(path_str: str) -> bool:
    lowered = str(path_str).replace("\\", "/").lower().rstrip("/")
    return any(
        lowered.startswith(root.replace("\\", "/").lower().rstrip("/"))
        for root in forbidden_roots()
    )


def check_identity_sync() -> list[str]:
    """Four roots must be absolute; mirrors must sit under a distinct backup root."""
    problems: list[str] = []
    for name in ("delivery_root", "paper_root", "paper_mirror_root", "idea_mirror_root"):
        raw = value(f"identity.{name}")
        p = Path(str(raw))
        if not p.is_absolute():
            problems.append(f"identity.{name} not absolute: {raw}")
    if str(value("identity.paper_mirror_root")).rstrip("\\") == str(
        value("identity.paper_root")
    ).rstrip("\\"):
        problems.append("paper mirror root must differ from paper root")
    if not forbidden_roots():
        problems.append("identity.forbidden_input_roots empty")
    return problems
