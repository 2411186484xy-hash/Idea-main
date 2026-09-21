"""Strict validator: structure + governance, never a substitute for real research execution."""

from __future__ import annotations

from . import canon, common, permissions, runs

REPO = common.REPO_ROOT
REFERENCED_ACTIONS = {
    "retrieval_run",
    "zotero_read",
    "zotero_write",
    "modify_project",
    "publish_idea",
    "refreeze_run",
}


def _validate_impl(strict: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    # 1. canon loads + identity sync
    try:
        canon.load()
    except Exception as exc:
        errors.append(f"canon unloadable: {exc}")
        return errors, warnings
    errors.extend(canon.check_identity_sync())
    # 2. rule anchors resolvable (spot-check core anchors)
    for anchor in (
        "retrieval.trigger",
        "idea.corpus_gate",
        "runs.single_writer",
        "deep_read.l3",
        "identity.zotero_sidebar_root",
    ):
        try:
            canon.get(anchor)
        except KeyError:
            errors.append(f"dangling rule anchor: {anchor}")
    # 3. permissions: no orphans either direction
    errors.extend(permissions.audit_no_orphans(set(REFERENCED_ACTIONS)))
    # 4. work-root cleanliness (V2 lesson)
    work = REPO / "work"
    if work.exists():
        loose = [p.name for p in work.iterdir() if p.is_file()]
        if loose:
            errors.append(f"work/ root has loose files: {loose[:5]}")
    # 5. runs: terminal runs must verify freeze
    for kind in ("weekly", "idea"):
        root = common.RUNS_ROOT / kind
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if not d.is_dir() or not (d / "run.json").exists():
                continue
            run = dict(common.read_json(d / "run.json"))  # type: ignore[arg-type]
            if run.get("status") == "completed":
                res = runs.verify_freeze(kind, d.name)
                if not res["ok"]:
                    errors.append(f"frozen drift in {d.name}: {sorted(res['drift'])}")
    # 6. zotero hardcoded-root regression (source scan)
    py_files = list((REPO / "pipelines").glob("*.py"))
    errors.extend(
        __import__(
            "pipelines.zotero", fromlist=["check_no_hardcoded_root"]
        ).check_no_hardcoded_root(py_files)
    )
    if strict and warnings:
        pass
    return errors, warnings


def validate_strict() -> list[str]:
    errors, _ = _validate_impl(strict=True)
    return errors
