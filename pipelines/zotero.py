"""L2 zotero: audited three-stage import (manifest + write + readback) + evidence notes.

Face split borrows 54yyyu (read-wide) / cookjohn (write-narrow, MIT): the
write face accepts manifest-approved items only, and every write closes with
a readback archived as readback-{sha12}.json (no peer MCP repo has this).
M3.3 adds the evidence-notes lane: CONFIRMED claims only (canon policy), one
note per paper, note bodies verified by hash on the write dump — the plugin
ecosystem carries no post-write audit, so this stays our complement.
The live Zotero API call runs in-session via pyzotero (urschrei/pyzotero,
BlueOak-1.0.0; session-side only, never imported here) — GUI lifetime is not
dependable (ENVIRONMENT facts), so offline yields a manifest with the write
stage paused, never a data error.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import canon, claims, contracts, runs, store


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **extra}


def _zotero_dir() -> Path:
    return store.knowledge_root() / "zotero"


def _item_key(item: dict[str, Any]) -> str:
    doi = str(item.get("DOI") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    return f"title:{str(item.get('title') or '').strip().lower()}"


def _creators(authors: list[str]) -> list[dict[str, str]]:
    """Two-field creators for space-separated ASCII names, single-field otherwise.

    Zotero's API accepts either firstName+lastName or a lone name. CJK names carry
    no space-separated parts, so the two-field form would corrupt them; single-field
    is also what Zotero uses for institutional authors, though a name like
    "Endo Group" is indistinguishable from a two-token person name and will be split.
    """
    out: list[dict[str, str]] = []
    for name in authors:
        parts = str(name).strip().split()
        if len(parts) > 1 and all(p.isascii() for p in parts):
            out.append({"creatorType": "author", "firstName": " ".join(parts[:-1]),
                        "lastName": parts[-1]})
        elif parts:
            out.append({"creatorType": "author", "name": " ".join(parts)})
    return out


def _template(cand: contracts.PaperCandidate, topic: str = "") -> dict[str, Any]:
    """pyzotero create_items-compatible dict (list payload, verified signature).

    Tags carry the two anchors of the narrow write face: paper identity
    (idea-os:<paper_key>) and the run topic — nothing else is touched.
    """
    doi = str(cand.identifiers.get("doi") or "").strip()
    arxiv = str(cand.identifiers.get("arxiv_id") or "").strip()
    prefix = str(canon.value("zotero.tag_prefix"))
    tags = [{"tag": f"{prefix}{cand.paper_key}"}]
    if topic:
        tags.append({"tag": f"{prefix}topic:{topic}"})
    item: dict[str, Any] = {"itemType": "journalArticle", "title": cand.title,
                            "creators": _creators(cand.authors), "collections": [],
                            "tags": tags}
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
    items = [_template(c, str(run.topic or "")) for c in run.paper_candidates]
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


def _safe_dirname(paper_key: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", paper_key).strip("_") or "paper"


def _note_md(run_id: str, topic: str, paper_key: str, rows: list[dict[str, Any]]) -> str:
    lines = [f"# idea-os confirmed claims — {paper_key}", "",
             f"- run: {run_id}",
             f"- topic: {topic or 'n/a'}",
             f"- claims: {len(rows)} (CONFIRMED only)", ""]
    for row in rows:
        lines += [f"## {row.get('id')} [{row.get('topic')}]", "",
                  str(row.get("text") or ""), "",
                  f"> {row.get('quote')}",
                  f"> — p.{int(row.get('page_anchor') or 0)}, {row.get('verifier_verdict')}", ""]
    return "\n".join(lines).rstrip() + "\n"


def write_notes(run_id: str) -> dict[str, Any]:
    """Evidence notes lane: CONFIRMED claims -> note.md in library + mirror.

    Half-automatic by design (audit-B): notes never go through the live Zotero
    API — the researcher imports note.md via Better Notes, keeping the manual
    channel boundary explicit. Re-running is idempotent: the generated text is
    deterministic, so library and mirror keep one SHA.
    """
    run = runs.load(run_id)
    if run is None:
        return _fail(f"run not found: {run_id}")
    keys = {c.paper_key for c in run.paper_candidates}
    if not keys:
        return _fail(f"run has no candidates: {run_id}")
    verdicts = {str(v) for v in canon.value("zotero.notes_verdicts")}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in claims.load_claims():
        if str(row.get("verifier_verdict")) not in verdicts:
            continue
        key = str(row.get("paper_key") or "")
        if key in keys:
            grouped.setdefault(key, []).append(row)
    if not grouped:
        return _fail(f"no {'/'.join(sorted(verdicts))} claims for this run's papers")
    topic = str(run.topic or "")
    notes = []
    for key in sorted(grouped):
        body = _note_md(run_id, topic, key, grouped[key])
        leaf = _safe_dirname(key)
        lib = canon.paper_root() / "library" / leaf / "note.md"
        mirror = canon.paper_mirror_root() / "library" / leaf / "note.md"
        store.write_text_atomic(lib, body)
        store.write_text_atomic(mirror, body)
        sha, mirror_sha = store.sha256_file(lib), store.sha256_file(mirror)
        if sha != mirror_sha:
            return _fail(f"note mirror SHA mismatch for {key}: {sha[:12]} != {mirror_sha[:12]}")
        notes.append({"paper_key": key, "library": str(lib), "mirror": str(mirror),
                      "sha256": sha, "bytes": len(body.encode("utf-8")),
                      "claim_ids": [str(r.get("id")) for r in grouped[key]]})
    return {"ok": True, "run_id": run_id, "count": len(notes), "notes": notes,
            "note": "import into Zotero via Better Notes (manual channel boundary)"}
