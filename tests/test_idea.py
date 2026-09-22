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
        "disproof": {
            "experiment": "ablate the region mask against the global-point gate on identical captures",
            "controls": "same captures and reader, only the decision rule swapped",
            "decision_rule": "region P95 < 0.4mm while in-region coverage stays > 50%",
            "failure_interpretation": "no lift over the global gate means the mask adds no information",
        },
        "screening_note": "zero hits across backends: downgraded to reach-too-low, not novelty",
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
                "result": "empty",
                "confidence": "weak",
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


def test_idea_add_records_seed_in_run(frozen_clock):
    """run.idea_seeds must count delivered ideas: session-log 'ideas' reads it."""
    from pipelines import runs

    runs.start("idea", "IDEARUN-20260921-120000")
    out = idea.add_idea(_payload(slug="seed-counted"), lessons_read=True,
                        run_id="IDEARUN-20260921-120000")
    assert out["ok"]
    run = runs.load("IDEARUN-20260921-120000")
    assert [s["slug"] for s in run.idea_seeds] == ["seed-counted"]
    assert idea.add_idea(_payload(slug="seed-counted"), lessons_read=True)["ok"] is False
    finished = runs.finish("IDEARUN-20260921-120000")
    assert finished["ok"] and finished["ideas"] == 1
    assert finished["papers"] == 0


def test_idea_brief_four_in_one(frozen_clock):
    from pipelines import report, store

    store.append_jsonl(store.failure_ledger_path(),
                       {"schema_version": 3, "slug": "s", "stage": "screen",
                        "reason": "r", "lesson": "taught", "at": "2026-09-21T12:00:00Z"})
    brief = report.idea_brief("fringe disparity", "structured light", "monocular depth")
    assert brief["ok"] and brief["collision"]["seed"] == "fringe disparity"
    assert brief["lessons"][-1]["lesson"] == "taught"
    assert len(brief["attacks"]) == 6
    assert {q["backend"] for q in brief["novelty_plan"]} == {"openalex", "arxiv", "crossref", "europepmc", "doaj"}
    assert report.idea_brief("", "s", "t")["ok"] is False
    assert brief["quality_pack"]["sees_writer_card"] is False
    assert len(brief["quality_pack"]["dims"]) == 6
    assert set(brief["disproof_pack"]["fields"]) == {
        "experiment", "controls", "decision_rule", "failure_interpretation"}
    assert "collision_sample" not in brief


def test_idea_brief_samples_bank_deterministically(frozen_clock):
    from pipelines import report

    seed = "single-shot fringe projection calibration-free depth"
    brief = report.idea_brief(seed)
    assert brief["ok"] and brief["collision"]["source_domain"]
    sample = brief["collision_sample"]
    assert sample["id"] and sample["domain"]
    assert "{problem}" not in sample["template"] and seed in sample["template"]
    again = report.idea_brief(seed)
    assert again["collision_sample"]["id"] == sample["id"]
    topic_brief = report.idea_brief("", topic="single-shot-sl")
    assert topic_brief["ok"] and topic_brief["topic"]["id"] == "single-shot-sl"
    assert topic_brief["collision"]["seed"] == "单帧结构光/条纹投影三维重建（含内窥镜场景）"
    assert report.idea_brief("", topic="ghost-topic")["ok"] is False


def test_idea_brief_novelty_queries_are_retrievable(frozen_clock):
    """Novelty checks must be searchable text: English key terms, not topic prose."""
    from pipelines import report

    brief = report.idea_brief("", topic="single-shot-sl")
    queries = [q["query"] for q in brief["novelty_plan"]]
    assert all(q.isascii() for q in queries), queries
    assert all("fringe projection profilometry" in q for q in queries)
    assert any("prior work" in q for q in queries)
    assert not any("／" in q or "（" in q for q in queries)
    named = report.idea_brief("explicit prose seed", "src", "tgt")
    assert all("explicit prose seed" in q["query"] for q in named["novelty_plan"])


def test_avoidance_blocks_near_duplicate_titles(frozen_clock):
    from pipelines import idea, store

    store.append_jsonl(store.failure_ledger_path(),
                       {"schema_version": 3, "slug": "old-fringe-idea", "stage": "verdict",
                        "reason": "fringe disparity monocular depth refinement rejected earlier",
                        "lesson": "refinement loop had no measurable lift", "at": "2026-09-21T12:00:00Z"})
    blocked = idea.add_idea(_payload(), lessons_read=True)
    assert not blocked["ok"] and "avoidance" in blocked["error"]
    assert blocked["hits"][0]["ledger_slug"] == "old-fringe-idea"
    assert blocked["hits"][0]["overlap"] >= 3
    far = idea.add_idea(_payload(slug="other-slug",
                                 title="Coded-aperture event-camera triangulation for specular surfaces"),
                         lessons_read=True)
    assert far["ok"]


def test_all_empty_novelty_needs_screening_note(frozen_clock):
    from pipelines import idea

    blocked = idea.add_idea(_payload(screening_note=""), lessons_read=True)
    assert not blocked["ok"] and "screening_note" in blocked["error"]
    assert idea.add_idea(_payload(), lessons_read=True)["ok"]


def test_publish_delivers_verifies_and_removes(frozen_clock):
    from pipelines import canon, runs, store

    runs.start("idea", "IDEARUN-20260921-120000")
    assert idea.add_idea(_payload(), run_id="IDEARUN-20260921-120000", lessons_read=True)["ok"]
    out = idea.publish("fringe-scale-disambiguation", run_id="IDEARUN-20260921-120000")
    assert out["ok"] and out["sha_match"] is True
    assert out["files"] == ["disproof.md", "evidence.md", "idea.md", "novelty.md",
                            "researcher-decision.json"]
    slug_dir = canon.delivery_root() / "fringe-scale-disambiguation"
    assert (slug_dir / "idea.md").read_text(encoding="utf-8").startswith("# Bidirectional")
    disproof_md = (slug_dir / "disproof.md").read_text(encoding="utf-8")
    assert disproof_md.startswith("# Disproof design — fringe-scale-disambiguation")
    assert "region P95 < 0.4mm" in disproof_md and "## Failure interpretation" in disproof_md
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
