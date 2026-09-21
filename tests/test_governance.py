"""Zotero single-root + permissions no-orphan + canon identity sync."""

from pipelines import canon, common, permissions, validate, zotero


def test_sidebar_root_single_sourced():
    assert common.ZOTERO_SIDEBAR_ROOT == "paper"
    assert canon.get("identity.zotero_sidebar_root") == "paper"
    assert zotero.collection_path("01_recent-week") == "paper/01_recent-week"


def test_no_legacy_root_literals():
    py_files = list((common.REPO_ROOT / "pipelines").glob("*.py"))
    assert zotero.check_no_hardcoded_root(py_files) == []


def test_permissions_enforced():
    assert not permissions.check("nonexistent-action").allowed
    assert not permissions.check("refreeze_run").allowed
    assert permissions.check("refreeze_run", reason="fix").allowed
    assert permissions.audit_no_orphans(set(validate.REFERENCED_ACTIONS)) == []
