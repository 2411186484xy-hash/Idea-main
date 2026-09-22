"""L2 zotero: manifest staging, narrow write verify, readback audit."""

from __future__ import annotations

import json
from pathlib import Path

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


def test_creators_split_western_and_keep_cjk_single_field():
    assert zotero._creators(["Ada Lovelace", "Alan Turing"]) == [
        {"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"},
        {"creatorType": "author", "firstName": "Alan", "lastName": "Turing"},
    ]
    # CJK names carry no space-separated parts: single-field form, never split
    assert zotero._creators(["霍嘉燚", "  ", ""]) == [{"creatorType": "author", "name": "霍嘉燚"}]
    # known limitation: an all-ASCII institutional name is indistinguishable from a
    # two-token person name, so it is split (documented in _creators)
    assert zotero._creators(["Endo Group"]) == [
        {"creatorType": "author", "firstName": "Endo", "lastName": "Group"}
    ]


def _setup_two(frozen_clock):  # noqa: ARG001 - fixture orders the clock
    runs.start("weekly", RUN)
    assert papers.add_paper(RUN, _payload(authors=["Ada Lovelace", "霍嘉燚"]))["ok"]
    assert papers.add_paper(RUN, _payload(title="Second",
                                         identifiers={"doi": "10.2/other"}))["ok"]


def test_manifest_stages_items_with_sha(frozen_clock):
    _setup_two(frozen_clock)
    out = zotero.build_manifest(RUN)
    assert out["ok"] and out["count"] == 2 and len(out["sha256"]) == 64
    record = store.read_json(store.knowledge_root() / "zotero" / f"manifest-{out['sha256'][:12]}.json")
    assert record["items"][0]["itemType"] == "journalArticle"
    assert record["items"][0]["DOI"] == "10.1/deep"
    assert record["items"][0]["creators"] == [
        {"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"},
        {"creatorType": "author", "name": "霍嘉燚"},
    ]
    assert record["items"][1]["creators"] == []  # candidate without authors stays empty
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


def _claim_row(cid, key, verdict, quote="q"):
    return {"id": cid, "paper_key": key, "topic": "t", "text": "claim text",
            "quote": quote, "page_anchor": 1, "confidence": "medium",
            "verifier_verdict": verdict, "verifier_note": None,
            "created_at": "2026-09-21T12:00:00Z", "schema_version": 3}


def test_manifest_carries_topic_tag(frozen_clock):
    runs.start("weekly", RUN)
    run = runs.load(RUN)
    run.topic = "single-shot-sl"
    runs.save(run)
    assert papers.add_paper(RUN, _payload())["ok"]
    out = zotero.build_manifest(RUN)
    record = store.read_json(store.knowledge_root() / "zotero" / f"manifest-{out['sha256'][:12]}.json")
    tags = [t["tag"] for t in record["items"][0]["tags"]]
    assert tags == ["idea-os:doi:10.1/deep", "idea-os:topic:single-shot-sl"]


def test_notes_written_confirmed_only_with_mirror(frozen_clock):
    _setup_two(frozen_clock)
    store.append_jsonl(store.claims_path(), _claim_row("CLM-20260921-001", "doi:10.1/deep", "CONFIRMED"))
    store.append_jsonl(store.claims_path(), _claim_row("CLM-20260921-002", "doi:10.1/deep", "DEVIATED"))
    store.append_jsonl(store.claims_path(), _claim_row("CLM-20260921-003", "doi:10.1/outside", "CONFIRMED"))
    store.append_jsonl(store.claims_path(), _claim_row("CLM-20260921-004", "doi:10.2/other", "CONFIRMED"))
    out = zotero.write_notes(RUN)
    assert out["ok"] and out["count"] == 2
    deep = next(n for n in out["notes"] if n["paper_key"] == "doi:10.1/deep")
    assert deep["claim_ids"] == ["CLM-20260921-001"]
    lib, mirror = Path(deep["library"]), Path(deep["mirror"])
    assert lib.is_file() and mirror.is_file()
    text = lib.read_text(encoding="utf-8")
    assert text == mirror.read_text(encoding="utf-8")
    assert lib.name == "note.md" and lib.parent.name == "doi_10.1_deep"
    assert "CLM-20260921-001" in text and "p.1, CONFIRMED" in text
    assert "CLM-20260921-002" not in text and "CLM-20260921-003" not in text
    again = zotero.write_notes(RUN)
    assert [n["sha256"] for n in again["notes"]] == [n["sha256"] for n in out["notes"]]


def test_notes_need_confirmed_claims(frozen_clock):
    _setup_two(frozen_clock)
    out = zotero.write_notes(RUN)
    assert not out["ok"] and "CONFIRMED" in out["error"]
    assert not zotero.write_notes("WEEKLYRUN-20260921-999999")["ok"]
