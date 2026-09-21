"""L2 zotero: manifest staging, narrow write verify, readback audit."""

from __future__ import annotations

import json

from pipelines import papers, runs, store, zotero

RUN = "WEEKLYRUN-20260921-120000"


def _payload(**over):
    base = {
        "title": "Deep read",
        "identifiers": {"doi": "10.1/deep"},
        "source_backend": "openalex",
        "abstract": "a",
        "abstract_sha256": "0" * 64,
    }
    base.update(over)
    return base


def _setup_two(frozen_clock):  # noqa: ARG001 - fixture orders the clock
    runs.start("weekly", RUN)
    assert papers.add_paper(RUN, _payload())["ok"]
    assert papers.add_paper(RUN, _payload(title="Second",
                                         identifiers={"doi": "10.2/other"}))["ok"]


def test_manifest_stages_items_with_sha(frozen_clock):
    _setup_two(frozen_clock)
    out = zotero.build_manifest(RUN)
    assert out["ok"] and out["count"] == 2 and len(out["sha256"]) == 64
    record = store.read_json(store.knowledge_root() / "zotero" / f"manifest-{out['sha256'][:12]}.json")
    assert record["items"][0]["itemType"] == "journalArticle"
    assert record["items"][0]["DOI"] == "10.1/deep"
    assert record["run_id"] == RUN


def test_write_exact_dump_passes(frozen_clock, tmp_path):
    _setup_two(frozen_clock)
    sha = zotero.build_manifest(RUN)["sha256"]
    dump = tmp_path / "dump.json"
    dump.write_text(json.dumps([{"DOI": "10.1/deep", "title": "Deep read"},
                                {"DOI": "10.2/other", "title": "Second"}]), encoding="utf-8")
    out = zotero.verify_write(sha, str(dump))
    assert out["ok"] and out["matched"] == 2
    assert runs.load(RUN).trace[-1]["event"] == "ZOTERO_WRITE"
    back = zotero.readback(sha)
    assert back["ok"] and back["report"]["found"] == 2
    assert runs.load(RUN).trace[-1]["event"] == "ZOTERO_READBACK"


def test_write_lists_missing_and_extra(frozen_clock, tmp_path):
    _setup_two(frozen_clock)
    sha = zotero.build_manifest(RUN)["sha256"]
    dump = tmp_path / "dump.json"
    dump.write_text(json.dumps([{"DOI": "10.1/deep", "title": "Deep read"},
                                {"title": "Stranger"}]), encoding="utf-8")
    out = zotero.verify_write(sha, str(dump))
    assert not out["ok"]
    assert out["missing"] == ["doi:10.2/other"] and out["extra"] == ["title:stranger"]


def test_manifest_unknown_run_and_readback_before_write(frozen_clock):
    assert not zotero.build_manifest("WEEKLYRUN-20260921-999999")["ok"]
    assert not zotero.readback("deadbeefcafe")["ok"]
    runs.start("weekly", RUN)
    assert papers.add_paper(RUN, _payload())["ok"]
    sha = zotero.build_manifest(RUN)["sha256"]
    assert not zotero.readback(sha)["ok"]
