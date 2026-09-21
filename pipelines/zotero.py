"""L2 zotero: audited three-stage import (manifest + write + readback).

Face split borrows 54yyyu (read-wide) / cookjohn (write-narrow, MIT): the
write face accepts manifest-approved items only, and every write closes with
a readback archived as readback-{sha12}.json (no peer MCP repo has this).
The live Zotero API call runs in-session via pyzotero (urschrei/pyzotero,
BlueOak-1.0.0; session-side only, never imported here) — GUI lifetime is not
dependable (ENVIRONMENT facts), so offline yields a manifest with the write
stage paused, never a data error.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import contracts, runs, store


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **extra}


def _zotero_dir() -> Path:
    return store.knowledge_root() / "zotero"


def _item_key(item: dict[str, Any]) -> str:
    doi = str(item.get("DOI") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    return f"title:{str(item.get('title') or '').strip().lower()}"


def _template(cand: contracts.PaperCandidate) -> dict[str, Any]:
    """pyzotero create_items-compatible dict (list payload, verified signature)."""
    doi = str(cand.identifiers.get("doi") or "").strip()
    arxiv = str(cand.identifiers.get("arxiv_id") or "").strip()
    item: dict[str, Any] = {"itemType": "journalArticle", "title": cand.title,
                            "creators": [], "collections": [],
                            "tags": [{"tag": f"idea-os:{cand.paper_key}"}]}
    if doi:
        item["DOI"] = doi
        item["url"] = f"https://doi.org/{doi}"
    elif arxiv:
        item["url"] = f"https://arxiv.org/abs/{arxiv}"
    return item


def build_manifest(run_id: str) -> dict[str, Any]:
    """Stage 1: manifest+SHA from a run's candidates (paused write when offline)."""
    run = runs.load(run_id)
    if run is None:
        return _fail(f"run not found: {run_id}")
    if not run.paper_candidates:
        return _fail(f"run has no candidates: {run_id}")
    items = [_template(c) for c in run.paper_candidates]
    body = json.dumps(items, ensure_ascii=False, sort_keys=True)
    manifest = contracts.ZoteroManifest(items=items,
                                        sha256=contracts.sha256_hex(body),
                                        created_at=store.now())
    record = {**store.to_dict(manifest), "run_id": run_id}
    path = _zotero_dir() / f"manifest-{manifest.sha256[:12]}.json"
    store.write_json_atomic(path, record)
    return {"ok": True, "run_id": run_id, "sha256": manifest.sha256,
            "count": len(items), "path": str(path),
            "note": "execute the write in-session (pyzotero), then zotero-write"}


def _load_manifest(sha: str) -> tuple[dict[str, Any] | None, str]:
    prefix = sha.strip().lower()[:12]
    if _zotero_dir().is_dir():
        for path in sorted(_zotero_dir().glob("manifest-*.json")):
            if path.stem.endswith(prefix):
                try:
                    return dict(store.read_json(path)), ""
                except (ValueError, OSError) as exc:
                    return None, f"manifest unreadable: {exc}"
    return None, f"manifest not found: {sha[:12]}"


def verify_write(sha: str, dump_path: str) -> dict[str, Any]:
    """Stage 2: compare the in-session write dump against the manifest."""
    manifest, err = _load_manifest(sha)
    if manifest is None:
        return _fail(err)
    try:
        observed = store.read_json(Path(dump_path))
    except (ValueError, OSError) as exc:
        return _fail(f"dump unreadable: {exc}")
    if not isinstance(observed, list):
        return _fail("dump must be a JSON list of Zotero items")
    expected = {_item_key(i) for i in manifest["items"]}
    seen = {_item_key(i) for i in observed if isinstance(i, dict)}
    missing = sorted(expected - seen)
    extra = sorted(seen - expected)
    report = contracts.ReadbackReport(manifest_sha256=manifest["sha256"],
                                      expected=len(expected), found=len(seen & expected),
                                      missing=missing, extra=extra, at=store.now())
    store.write_json_atomic(_zotero_dir() / f"readback-{manifest['sha256'][:12]}.json",
                            store.to_dict(report))
    run = runs.load(str(manifest.get("run_id") or ""))
    if run is not None and run.status == "active":
        runs.append_trace(run, "ZOTERO_WRITE", manifest["sha256"][:12])
        runs.save(run)
    out: dict[str, Any] = {"ok": report.ok, "matched": len(seen & expected),
                           "missing": missing, "extra": extra}
    if not report.ok:
        out["error"] = f"readback mismatch: {len(missing)} missing, {len(extra)} extra"
    return out


def readback(sha: str) -> dict[str, Any]:
    """Stage 3: load the archived readback audit (contract-checked)."""
    manifest, err = _load_manifest(sha)
    if manifest is None:
        return _fail(err)
    path = _zotero_dir() / f"readback-{manifest['sha256'][:12]}.json"
    if not path.exists():
        return _fail(f"no readback archived yet for {manifest['sha256'][:12]} (run zotero-write first)")
    try:
        data = dict(store.read_json(path))
        report = contracts.ReadbackReport(**data)
    except (ValueError, TypeError, KeyError) as exc:
        return _fail(f"readback corrupt: {exc}")
    run = runs.load(str(manifest.get("run_id") or ""))
    if run is not None and run.status == "active":
        runs.append_trace(run, "ZOTERO_READBACK", manifest["sha256"][:12])
        runs.save(run)
    return {"ok": report.ok, "report": store.to_dict(report)}
