"""L2 idea (M1): the feedback supply gate hard-refuses idea-add when low."""

from __future__ import annotations

import json

from pipelines import feedback, idea


def _payload(**over):
    base = {
        "slug": "fringe-scale-disambiguation",
        "title": "Bidirectional refinement between fringe disparity and monocular depth",
        "hypothesis": "mutual refinement disambiguates scale without bracketing",
        "collision": {
            "seed": "fringe disparity",
            "source_domain": "structured light",
            "target_domain": "monocular depth",
        },
        "quality_card": {
            dim: {"score": 3, "rationale": f"{dim} ok"} for dim in (
                "novelty", "rigor", "feasibility", "clarity", "data_availability", "venue_fit"
            )
        },
        "attacks": [f"attack {i}" for i in range(6)],
        "novelty_log": [
            {
                "query": "fringe monocular scale",
                "backend": "openalex",
                "top_match": "none",
                "note": "no direct prior",
            }
        ],
        "evidence_refs": ["CLM-20260921-001", "CLM-20260921-002", "CLM-20260921-003"],
    }
    base.update(over)
    return base


def test_idea_add_hard_blocked_below_threshold(frozen_clock, capsys):
    """The real command path (cli idea-add) refuses while supply is closed."""
    from cli import main

    feedback.add_feedback("v1-a", "uncertain", "pending researcher")
    rc = main(["idea-add", "--payload", json.dumps(_payload())])
    assert rc == 1
    assert "supply closed" in capsys.readouterr().out


def test_idea_add_passes_gate_then_validates(frozen_clock, capsys):
    from cli import main

    feedback.add_feedback("v1-a", "accept", "confirmed by researcher")
    rc = main(["idea-add", "--lessons-read", "--payload", json.dumps(_payload(slug="BAD SLUG!!"))])
    assert rc == 1 and "idea rejected" in capsys.readouterr().out
    assert main(["idea-add", "--lessons-read", "--payload", json.dumps(_payload())]) == 0
    out = capsys.readouterr().out
    assert "fringe-scale-disambiguation" in out and "1/1" in out
    dup = idea.add_idea(_payload(), lessons_read=True)
    assert not dup["ok"] and "duplicate slug" in dup["error"]


def test_idea_add_warn_blocks_unread_lessons(frozen_clock, capsys):
    from cli import main

    feedback.add_feedback("v1-a", "accept", "confirmed by researcher")
    rc = main(["idea-add", "--payload", json.dumps(_payload())])
    assert rc == 1 and "lesson gate" in capsys.readouterr().out
    assert idea.add_idea(_payload(), lessons_read=False)["ok"] is False


def test_idea_add_corpus_gate(frozen_clock):
    thin_refs = idea.add_idea(_payload(evidence_refs=["CLM-20260921-001"]),
                              lessons_read=True)
    assert not thin_refs["ok"] and "corpus gate" in thin_refs["error"]
    no_novelty = idea.add_idea(_payload(novelty_log=[]), lessons_read=True)
    assert not no_novelty["ok"] and "corpus gate" in no_novelty["error"]
    assert idea.add_idea(_payload(), lessons_read=True)["ok"]


def test_idea_add_marks_hold_dims(frozen_clock):
    card = {dim: {"score": 3, "rationale": f"{dim} ok"} for dim in (
        "novelty", "rigor", "feasibility", "clarity", "data_availability", "venue_fit")}
    card["feasibility"] = {"score": 2, "rationale": "needs rig time"}
    out = idea.add_idea(_payload(slug="hold-demo", quality_card=card), lessons_read=True)
    assert out["ok"] and out["hold"]["dims"] == ["feasibility"]
    clean = idea.add_idea(_payload(slug="clean-demo"), lessons_read=True)
    assert clean["ok"] and "hold" not in clean


def test_idea_brief_four_in_one(frozen_clock):
    from pipelines import report, store

    store.append_jsonl(store.failure_ledger_path(),
                       {"schema_version": 3, "slug": "s", "stage": "screen",
                        "reason": "r", "lesson": "taught", "at": "2026-09-21T12:00:00Z"})
    brief = report.idea_brief("fringe disparity", "structured light", "monocular depth")
    assert brief["ok"] and brief["collision"]["seed"] == "fringe disparity"
    assert brief["lessons"][-1]["lesson"] == "taught"
    assert len(brief["attacks"]) == 6
    assert {q["backend"] for q in brief["novelty_plan"]} == {"openalex", "arxiv", "crossref", "europepmc"}
    assert report.idea_brief("", "s", "t")["ok"] is False


def test_publish_delivers_verifies_and_removes(frozen_clock):
    from pipelines import canon, runs, store

    runs.start("idea", "IDEARUN-20260921-120000")
    assert idea.add_idea(_payload(), run_id="IDEARUN-20260921-120000", lessons_read=True)["ok"]
    out = idea.publish("fringe-scale-disambiguation", run_id="IDEARUN-20260921-120000")
    assert out["ok"] and out["sha_match"] is True
    assert out["files"] == ["evidence.md", "idea.md", "novelty.md", "researcher-decision.json"]
    slug_dir = canon.delivery_root() / "fringe-scale-disambiguation"
    assert (slug_dir / "idea.md").read_text(encoding="utf-8").startswith("# Bidirectional")
    assert store.read_json(store.idea_pool_path()) == []
    assert runs.load("IDEARUN-20260921-120000").trace[-1]["event"] == "PUBLISH"
    assert not idea.publish("fringe-scale-disambiguation")["ok"]
    check = idea.backup_verify()
    assert check["ok"] and check["dirs"] == 1 and check["sampled"] >= 1


def test_publish_refuses_hold_and_unknown(frozen_clock):
    card = {dim: {"score": 3, "rationale": f"{dim} ok"} for dim in (
        "novelty", "rigor", "feasibility", "clarity", "data_availability", "venue_fit")}
    card["rigor"] = {"score": 1, "rationale": "no control"}
    assert idea.add_idea(_payload(slug="risky", quality_card=card), lessons_read=True)["ok"]
    refused = idea.publish("risky")
    assert not refused["ok"] and "hold" in refused["error"]
    assert not idea.publish("ghost-slug")["ok"]


def test_backup_verify_flags_mismatch(frozen_clock, tmp_path):
    from pipelines import canon, store

    assert idea.add_idea(_payload(), lessons_read=True)["ok"]
    assert idea.publish("fringe-scale-disambiguation")["ok"]
    twin = canon.idea_mirror_root() / "fringe-scale-disambiguation" / "idea.md"
    twin.write_text("tampered", encoding="utf-8")
    bad = idea.backup_verify()
    assert not bad["ok"] and any("SHA mismatch" in m for m in bad["mismatches"])
    (canon.idea_mirror_root() / "fringe-scale-disambiguation" / "novelty.md").unlink()
    gone = idea.backup_verify()
    assert not gone["ok"] and store.read_json(store.idea_pool_path()) == []
