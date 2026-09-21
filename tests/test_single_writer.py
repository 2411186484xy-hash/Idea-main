"""Single-writer regression: prescreen never touches run.json; reconcile promotes via add_paper."""

from pipelines import runs


def _payload(i, route="direct"):
    return {
        "title": f"T{i}",
        "discovery_class": "direct",
        "coverage_route": route,
        "doi": f"10.1/v2-{i}",
    }


def test_prescreen_side_ledger_only(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "WEEKLY_ROOT", tmp_path)
    assert runs.start("weekly", "WEEKLYRUN-20260920-000001")["ok"]
    r = runs.prescreen_append("weekly", "WEEKLYRUN-20260920-000001", [_payload(1), _payload(2)])
    assert r == {"ok": True, "prescreened": 2}
    run = runs._read_run(tmp_path / "WEEKLYRUN-20260920-000001")
    assert run["paper_candidates"] == []
    side = tmp_path / "WEEKLYRUN-20260920-000001" / "mechanized-prescreen.jsonl"
    assert len(side.read_text(encoding="utf-8").strip().splitlines()) == 2
    rec = runs.reconcile("weekly", "WEEKLYRUN-20260920-000001")
    assert rec == {"ok": True, "imported": 2, "skipped_duplicates": 0}
    run = runs._read_run(tmp_path / "WEEKLYRUN-20260920-000001")
    assert len(run["paper_candidates"]) == 2
    assert side.read_text(encoding="utf-8") == ""


def test_add_paper_dedup(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "WEEKLY_ROOT", tmp_path)
    runs.start("weekly", "WEEKLYRUN-20260920-000002")
    assert runs.add_paper("weekly", "WEEKLYRUN-20260920-000002", _payload(1))["ok"]
    dup = runs.add_paper("weekly", "WEEKLYRUN-20260920-000002", _payload(1))
    assert not dup["ok"] and "duplicate" in dup["error"]
