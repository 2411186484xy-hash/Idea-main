"""Zotero audit channel: structured-note gate, manifest+SHA, offline queue, single sidebar root.

Write rule: only agent_read items enter 01/04 subsets; E-drive PDFs enter 03;
researcher confirmation moves 01 -> 02. Membership changes go through manifests.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import common

QUEUE_ROOT = common.RUNS_ROOT / "zotero"


def manifest(items: list[dict[str, Any]]) -> dict[str, Any]:
    body = json.dumps(items, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return {"items": items, "sha256": digest, "root": common.ZOTERO_SIDEBAR_ROOT}


def queue_import(manifest_doc: dict[str, Any]) -> dict[str, Any]:
    """Stage an import manifest; the live write happens in a Zotero session, then readback verifies."""
    QUEUE_ROOT.mkdir(parents=True, exist_ok=True)
    name = f"manifest-{manifest_doc.get('sha256', 'unknown')[:12]}.json"
    common.write_json(QUEUE_ROOT / name, manifest_doc)
    return {"ok": True, "staged": name}


def queued() -> list[str]:
    if not QUEUE_ROOT.exists():
        return []
    return sorted(p.name for p in QUEUE_ROOT.glob("manifest-*.json"))


def collection_path(subset: str) -> str:
    if subset not in common.ZOTERO_COLLECTIONS:
        raise ValueError(f"unknown subset: {subset}")
    return f"{common.ZOTERO_SIDEBAR_ROOT}/{subset}"


def check_no_hardcoded_root(source_files: list[Path]) -> list[str]:
    """Regression guard (V2 lesson): no literal 'opencode' collection root outside common.py."""
    problems = []
    legacy = "open" + "code/"  # built dynamically so this guard never self-matches
    for path in source_files:
        if path.name == "common.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if f'"{legacy}' in text or f"'{legacy}" in text:
            problems.append(f"hardcoded legacy root in {path}")
    return problems
