"""Per-test root isolation + session-level git-pollution guard.

Every test gets fresh IDEAOS_* roots under its own tmp dir, so no test can
see another's knowledge layer or run dirs. The guard snapshots the REAL
repo knowledge/ and runs/ before/after the whole session: tests must never
touch them. A settable frozen clock makes time explicit.
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

ENV_VARS = (
    "IDEAOS_KNOWLEDGE_ROOT",
    "IDEAOS_RUNS_ROOT",
    "IDEAOS_PAPER_ROOT",
    "IDEAOS_DELIVERY_ROOT",
    "IDEAOS_PAPER_MIRROR_ROOT",
    "IDEAOS_IDEA_MIRROR_ROOT",
)


def _snapshot(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {str(p.relative_to(root)) for p in root.rglob("*")}


@pytest.fixture(scope="session", autouse=True)
def pollution_guard():
    real_knowledge = _snapshot(REPO / "knowledge")
    real_runs = _snapshot(REPO / "runs")
    yield
    leaked_k = _snapshot(REPO / "knowledge") - real_knowledge
    leaked_r = _snapshot(REPO / "runs") - real_runs
    assert not leaked_k, f"tests polluted real knowledge/: {sorted(leaked_k)}"
    assert not leaked_r, f"tests polluted real runs/: {sorted(leaked_r)}"


@pytest.fixture(autouse=True)
def redirect_roots(tmp_path):
    saved = {var: os.environ.get(var) for var in ENV_VARS}
    for var in ENV_VARS:
        os.environ[var] = str(tmp_path / var.removeprefix("IDEAOS_").lower())
    yield
    for var, val in saved.items():
        if val is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = val


class FrozenClock:
    """Settable clock: tests advance time explicitly."""

    def __init__(self) -> None:
        self.current = _dt.datetime(2026, 9, 21, 12, 0, 0, tzinfo=_dt.UTC)

    def advance(self, hours: float = 0) -> None:
        self.current += _dt.timedelta(hours=hours)

    def __call__(self) -> _dt.datetime:
        return self.current


@pytest.fixture()
def frozen_clock():
    from pipelines import store

    clock = FrozenClock()
    store.set_clock(clock)
    yield clock
    store.set_clock(None)
