"""L1 canon: value unwrapping, anchor errors, identity roots, forbidden guard."""

from __future__ import annotations

import pytest

from pipelines import canon


def test_value_unwraps_value_why():
    active = canon.value("search.active")
    assert isinstance(active, list) and "openalex" in active


def test_purpose_passes_through():
    assert "idea 交付" in str(canon.value("purpose"))


def test_missing_anchor_raises():
    with pytest.raises(canon.CanonError, match="canon anchor not found"):
        canon.value("search.does_not_exist")


def test_identity_roots_absolute():
    assert canon.paper_root().is_absolute()
    assert canon.delivery_root().is_absolute()
    assert canon.paper_mirror_root().is_absolute()
    assert canon.idea_mirror_root().is_absolute()


def test_env_override_of_paper_root(tmp_path):
    import os

    os.environ["IDEAOS_PAPER_ROOT"] = str(tmp_path)
    try:
        assert canon.paper_root() == tmp_path
    finally:
        os.environ.pop("IDEAOS_PAPER_ROOT", None)


def test_forbidden_roots_guard():
    assert canon.is_forbidden("E:\\Project\\whatever\\file.pdf")
    assert canon.is_forbidden("E:/Project/x")
    assert not canon.is_forbidden("E:\\Paper\\library\\doi-1\\x.pdf")


def test_check_identity_sync_clean():
    assert canon.check_identity_sync() == []


def test_l2_quota_dual_channel_pair():
    assert list(canon.value("quotas.l2_per_run")) == [10, 15]


def test_feedback_coverage_threshold():
    assert float(canon.value("quotas.feedback_coverage_min")) == 0.5
