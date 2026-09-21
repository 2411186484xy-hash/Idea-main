"""Freeze determinism: LF normalization + CRLF variants + refreeze audit."""

from pipelines import runs


def _payload(i, route="direct"):
    return {
        "title": f"T{i}",
        "discovery_class": "direct",
        "coverage_route": route,
        "doi": f"10.1/fz-{i}",
    }


def _fill(run_id, monkeypatch, tmp_path, n=10):
    monkeypatch.setattr(runs, "WEEKLY_ROOT", tmp_path)
    runs.start("weekly", run_id)
    routes = ["direct", "counter_boundary", "transfer", "frontier"]
    for i in range(n):
        runs.add_paper("weekly", run_id, _payload(i, routes[i % 4]))
    d = tmp_path / run_id
    (d / "report.md").write_text("# r\n", encoding="utf-8", newline="\n")
    return d


def test_finish_freeze_and_verify(tmp_path, monkeypatch):
    _fill("WEEKLYRUN-20260920-000003", monkeypatch, tmp_path)
    res = runs.finish("weekly", "WEEKLYRUN-20260920-000003", supply_hold_reason="stock digestion")
    assert res["ok"], res
    v = runs.verify_freeze("weekly", "WEEKLYRUN-20260920-000003")
    assert v == {"ok": True, "drift": {}}


def test_crlf_tolerant_verify(tmp_path, monkeypatch):
    d = _fill("WEEKLYRUN-20260920-000004", monkeypatch, tmp_path)
    assert runs.finish("weekly", "WEEKLYRUN-20260920-000004", supply_hold_reason="x")["ok"]
    raw = (d / "report.md").read_bytes()
    (d / "report.md").write_bytes(raw.replace(b"\n", b"\r\n"))  # simulate Windows write
    assert runs.verify_freeze("weekly", "WEEKLYRUN-20260920-000004")["ok"] is True


def test_refreeze_requires_reason(tmp_path, monkeypatch):
    _fill("WEEKLYRUN-20260920-000005", monkeypatch, tmp_path)
    assert runs.finish("weekly", "WEEKLYRUN-20260920-000005", supply_hold_reason="x")["ok"]
    bad = runs.refreeze("weekly", "WEEKLYRUN-20260920-000005", "")
    assert not bad["ok"]
    ok = runs.refreeze("weekly", "WEEKLYRUN-20260920-000005", "appendix note added")
    assert ok["ok"]
