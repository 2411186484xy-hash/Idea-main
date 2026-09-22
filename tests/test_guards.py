"""W0 guards: replay idempotency, repo data-file schemas, ledger duplicate scan."""

from __future__ import annotations

import json

from pipelines import feedback, runs, store, validate


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_feedback_replay_is_rejected(frozen_clock):
    assert feedback.add_feedback("slug-a", "accept", "why not")["ok"]
    dup = feedback.add_feedback("slug-a", "accept", "why not")
    assert not dup["ok"] and "duplicate" in dup["error"]
    # a different reason is a new row, not a replay
    assert feedback.add_feedback("slug-a", "accept", "different reason")["ok"]
    assert len(feedback.load_feedback()) == 2


def test_run_finish_is_single_shot(frozen_clock):
    runs.start("weekly", "WEEKLYRUN-20260921-120000")
    assert runs.finish("WEEKLYRUN-20260921-120000")["ok"]
    # recreate the same id, then finish again -> session-log guard
    runs.start("weekly", "WEEKLYRUN-20260921-120000")
    again = runs.finish("WEEKLYRUN-20260921-120000")
    assert not again["ok"] and "already closed" in again["error"]
    assert len(store.read_jsonl(store.session_log_path())) == 1


def test_validate_flags_duplicate_ledger_rows():
    row = {"schema_version": 3, "slug": "s", "verdict": "accept", "reason": "r", "at": "t"}
    _write(store.feedback_path(), json.dumps(row) + "\n" + json.dumps(row) + "\n")
    result = validate.validate()
    assert any("duplicate verdict row" in e for e in result["errors"])
    log_row = {"at": "t", "run_id": "WEEKLYRUN-20260921-120000", "kind": "weekly",
               "papers": 0, "claims": 0, "ideas": 0}
    _write(store.session_log_path(), json.dumps(log_row) + "\n" + json.dumps(log_row) + "\n")
    assert any("duplicate run_id" in e for e in validate.validate()["errors"])


def test_topics_schema_checked(tmp_path):
    errors: list[str] = []
    doc = {"schema_version": 3, "topics": [{
        "id": "t-1", "name": "n", "status": "active", "problem": "p",
        "key_terms": ["a"], "target_domains": ["b"],
        "frontier_domains": [], "negative_terms": [], "anchor_papers": [], "venues": [],
        "transfer_pairs": [{"from_field": "f", "method_terms": ["m"], "to_problem": "x"}],
    }]}
    path = tmp_path / "topics.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    validate._check_topics(errors, path)
    assert errors == []
    bad = json.loads(json.dumps(doc))
    bad["topics"][0]["status"] = "flying"
    bad["topics"][0]["surprise"] = True
    path.write_text(json.dumps(bad), encoding="utf-8")
    validate._check_topics(errors, path)
    assert any("status" in e for e in errors) and any("unknown fields" in e for e in errors)
    errors.clear()
    validate._check_topics(errors, tmp_path / "missing.json")
    assert any("missing" in e for e in errors)


def test_collision_bank_schema_checked(tmp_path):
    errors: list[str] = []
    doc = {"schema_version": 3, "domains": [
        {"id": f"d-{i}", "domain": "d", "principle": "p", "template": "t"} for i in range(8)
    ]}
    path = tmp_path / "bank.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    validate._check_collision_bank(errors, path)
    assert errors == []
    doc["domains"][7]["template"] = ""
    path.write_text(json.dumps(doc), encoding="utf-8")
    validate._check_collision_bank(errors, path)
    assert any("template" in e for e in errors)


def test_repo_topic_and_bank_files_load():
    """The shipped knowledge files must satisfy their own schema check."""
    errors: list[str] = []
    validate._check_topics(errors)
    validate._check_collision_bank(errors)
    assert errors == []
