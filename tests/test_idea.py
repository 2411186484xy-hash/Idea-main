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
    rc = main(["idea-add", "--payload", json.dumps(_payload(slug="BAD SLUG!!"))])
    assert rc == 1 and "idea rejected" in capsys.readouterr().out
    assert main(["idea-add", "--payload", json.dumps(_payload())]) == 0
    out = capsys.readouterr().out
    assert "fringe-scale-disambiguation" in out and "1/1" in out
    dup = idea.add_idea(_payload())
    assert not dup["ok"] and "duplicate slug" in dup["error"]
