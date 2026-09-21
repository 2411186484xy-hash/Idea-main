"""L1 store: atomic write, fsync append, record codec, injectable clock, env redirection."""

from __future__ import annotations

import json

import pytest

from pipelines import contracts, store


def test_write_json_atomic_lf_and_trailing_newline(tmp_path):
    target = tmp_path / "nested" / "run.json"
    store.write_json_atomic(target, {"b": 1, "a": "值"})
    raw = target.read_bytes()
    assert raw.endswith(b"\n")
    assert b"\r" not in raw
    assert json.loads(raw.decode("utf-8")) == {"a": "值", "b": 1}


def test_atomic_write_leaves_no_tmp(tmp_path):
    target = tmp_path / "x.json"
    store.write_json_atomic(target, {"k": 1})
    leftovers = [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


def test_append_jsonl_roundtrip(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    store.append_jsonl(ledger, {"id": 1})
    store.append_jsonl(ledger, {"id": 2})
    rows = store.read_jsonl(ledger)
    assert [r["id"] for r in rows] == [1, 2]
    raw = ledger.read_bytes()
    assert raw.count(b"\n") == 2 and raw.endswith(b"\n")


def test_read_jsonl_missing_file_is_empty():
    assert store.read_jsonl(store.knowledge_root() / "nope.jsonl") == []


def test_injectable_clock(frozen_clock):
    first = store.now()
    assert store.now() == first  # frozen: no drift between calls
    frozen_clock.advance(hours=25)
    assert store.now() == "2026-09-22T13:00:00Z"  # moves only when told


def test_env_redirection(tmp_path):
    import os

    os.environ["IDEAOS_KNOWLEDGE_ROOT"] = str(tmp_path / "k")
    try:
        assert store.knowledge_root() == tmp_path / "k"
        assert store.claims_path().parent == tmp_path / "k"
    finally:
        os.environ.pop("IDEAOS_KNOWLEDGE_ROOT", None)


def test_run_dir_under_runs_root():
    assert store.run_dir("WEEKLYRUN-20260921-120000").parent == store.runs_root()


def _candidate():
    return contracts.PaperCandidate(
        title="A paper",
        identifiers={"doi": "10.1234/abc"},
        source_backend="openalex",
        abstract="abs",
        abstract_sha256=contracts.sha256_hex("abs"),
    )


def test_from_dict_rejects_unknown_schema_version():
    bad = {**store.to_dict(_candidate()), "schema_version": 99}
    with pytest.raises(ValueError, match="unknown schema_version"):
        store.from_dict("PaperCandidate", bad)


def test_roundtrip_preserves_record():
    cand = _candidate()
    again = store.from_dict("PaperCandidate", store.to_dict(cand))
    assert again == cand


def test_run_roundtrip_with_candidates(frozen_clock):
    from pipelines import runs

    runs.start("weekly", "WEEKLYRUN-20260921-120000")
    from pipelines import papers

    papers.add_paper(
        "WEEKLYRUN-20260921-120000",
        {
            "title": "T",
            "identifiers": {"doi": "10.1/x"},
            "source_backend": "openalex",
            "abstract": "a",
            "abstract_sha256": "0" * 64,
        },
    )
    reloaded = runs.load("WEEKLYRUN-20260921-120000")
    assert reloaded.paper_candidates[0].paper_key == "doi:10.1/x"
    assert reloaded.coverage == {r: 0 for r in contracts.COVERAGE_ROUTES} | {"direct": 1}
