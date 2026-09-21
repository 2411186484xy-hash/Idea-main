"""Single CLI entry: `python cli.py <command> [args]`. Parser is a pure surface; logic lives in pipelines/."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipelines import canon, claims, common, idea, literature, runs, validate, zotero  # noqa: E402


def _dump(obj: object) -> int:
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    return 0 if not (isinstance(obj, dict) and obj.get("error")) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="idea-os", description="Idea incubation OS v2 (ends at idea delivery)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("session-brief", help="canon summary + run status + feedback triage")
    sub.add_parser("status", help="runs overview")
    sub.add_parser("validate", help="strict structural validation").add_argument(
        "--strict", action="store_true"
    )

    s = sub.add_parser("run-start", help="start or resume a run")
    s.add_argument("kind", choices=["weekly", "idea"])
    s.add_argument("run_id")
    s.add_argument("--mode", default="")
    s.add_argument("--force", action="store_true")

    s = sub.add_parser("run-add-paper", help="single-writer paper registration")
    s.add_argument("kind", choices=["weekly", "idea"])
    s.add_argument("run_id")
    s.add_argument("--payload", required=True, help="JSON object")

    s = sub.add_parser("run-prescreen", help="mechanized prescreen to SIDE ledger only")
    s.add_argument("kind", choices=["weekly", "idea"])
    s.add_argument("run_id")
    s.add_argument("--items", required=True, help="JSON array")

    s = sub.add_parser("run-reconcile", help="import side ledger via single writer")
    s.add_argument("kind", choices=["weekly", "idea"])
    s.add_argument("run_id")

    s = sub.add_parser("run-finish", help="terminal close with hard gates")
    s.add_argument("kind", choices=["weekly", "idea"])
    s.add_argument("run_id")
    s.add_argument("--supply-hold-reason", default="")

    s = sub.add_parser("run-refreeze", help="audited reseal of a completed run")
    s.add_argument("kind", choices=["weekly", "idea"])
    s.add_argument("run_id")
    s.add_argument("--reason", required=True)

    s = sub.add_parser("search", help="full-recall pool search (selection upstream)")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=15)

    s = sub.add_parser("claim-add", help="append a claim to the hub")
    s.add_argument("--claim", required=True, help="JSON object")

    s = sub.add_parser("idea-add", help="add a candidate to the pool")
    s.add_argument("--candidate", required=True, help="JSON object")

    s = sub.add_parser(
        "idea-feedback", help="record researcher verdict (the only validation signal)"
    )
    s.add_argument("--slug", required=True)
    s.add_argument("--verdict", required=True, choices=["accept", "reject", "uncertain"])
    s.add_argument("--reason", required=True)

    sub.add_parser("idea-feedback-stats", help="feedback coverage stats")
    sub.add_parser("zotero-queue", help="list staged import manifests")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cmd = args.cmd
    if cmd == "session-brief":
        canon_doc = canon.load()
        return _dump(
            {
                "purpose": canon_doc.get("purpose"),
                "weekly": runs.status("weekly"),
                "ideas": runs.status("idea"),
                "feedback": idea.feedback_stats(),
                "zotero_queue": zotero.queued(),
            }
        )
    if cmd == "status":
        return _dump({"weekly": runs.status("weekly"), "ideas": runs.status("idea")})
    if cmd == "validate":
        errors = validate.validate_strict()
        return _dump({"ok": not errors, "errors": errors})
    if cmd == "run-start":
        return _dump(runs.start(args.kind, args.run_id, args.mode, args.force))
    if cmd == "run-add-paper":
        return _dump(runs.add_paper(args.kind, args.run_id, json.loads(args.payload)))
    if cmd == "run-prescreen":
        return _dump(runs.prescreen_append(args.kind, args.run_id, json.loads(args.items)))
    if cmd == "run-reconcile":
        return _dump(runs.reconcile(args.kind, args.run_id))
    if cmd == "run-finish":
        return _dump(runs.finish(args.kind, args.run_id, args.supply_hold_reason))
    if cmd == "run-refreeze":
        return _dump(runs.refreeze(args.kind, args.run_id, args.reason))
    if cmd == "search":
        common.ensure_ssl_cert_env()
        return _dump(literature.search(args.query, args.limit))
    if cmd == "claim-add":
        return _dump(claims.append_claim(json.loads(args.claim)))
    if cmd == "idea-add":
        return _dump(idea.add_candidate(json.loads(args.candidate)))
    if cmd == "idea-feedback":
        return _dump(idea.record_feedback(args.slug, args.verdict, args.reason))
    if cmd == "idea-feedback-stats":
        return _dump(idea.feedback_stats())
    if cmd == "zotero-queue":
        return _dump({"queued": zotero.queued()})
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
