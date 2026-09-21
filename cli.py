"""L4 cli: pure argparse surface, UTF-8 stdout. Logic lives in pipelines/.

The 21-command table in README.md is the contract (tests/test_docs keeps
parser and README in sync). Commands whose domain module lands in a later
milestone answer with an explicit not-implemented envelope.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipelines import (  # noqa: E402
    claims,
    feedback,
    idea,
    papers,
    report,
    runs,
    search,
    store,
    validate,
)

NOT_IMPLEMENTED = {
    "deepread-brief": "M2c",
    "pdf-extract": "M2c",
    "idea-brief": "M2f",
    "publish": "M2h",
    "zotero-manifest": "M2e",
    "zotero-write": "M2e",
    "zotero-readback": "M2e",
    "backup-verify": "M2h",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="idea-os", description="Idea incubation OS v2 (ends at idea delivery)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run-start", help="start a run, or resume a partial one")
    s.add_argument("kind", choices=["weekly", "idea"])
    s.add_argument("run_id")
    s.add_argument("--resume", action="store_true")

    s = sub.add_parser("run-finish", help="close a run: complete, partial, or absorb")
    s.add_argument("run_id")
    s.add_argument("--partial", metavar="GAP_NOTE")
    s.add_argument("--absorb", metavar="GAP_NOTE")

    sub.add_parser("session-brief", help="first screen: purpose, active runs, knowledge counts")
    s = sub.add_parser("validate", help="structural validation")
    s.add_argument("--strict", action="store_true")

    s = sub.add_parser("search", help="recall pool over ACTIVE backends")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=15)
    s.add_argument("--backend", action="append")
    s.add_argument("--run", help="log the query into this run's query_log")

    s = sub.add_parser("query-brief", help="multi-perspective query pack")
    s.add_argument("query")
    s.add_argument("--run", help="flag repeats against this run's query_log")
    s = sub.add_parser("screen-rank", help="rule-based ranking + stop criterion")
    s.add_argument("run_id")

    s = sub.add_parser("paper-add", help="register a candidate into a run (gated)")
    s.add_argument("run_id")
    s.add_argument("--payload", required=True, help="JSON object")
    s.add_argument("--pdf", help="archive PDF to the paper library + mirror")

    sub.add_parser("deepread-brief", help="writer/verifier blind-separated pack")
    sub.add_parser("pdf-extract", help="PDF text extraction (PyMuPDF first channel)")

    s = sub.add_parser("claims-add", help="append a page-anchored claim (lint-gated)")
    s.add_argument("--payload", required=True, help="JSON object")
    s.add_argument("--run", help="append CLAIM_ADD trace to this run")
    s = sub.add_parser("claims-view", help="render claims (filters optional)")
    s.add_argument("--topic")
    s.add_argument("--paper-key")
    s.add_argument("--verdict", choices=["CONFIRMED", "DEVIATED", "NOT_FOUND"])
    s.add_argument("--pairs-only", action="store_true", help="only pairs and the claims in them")

    sub.add_parser("idea-brief", help="collision + lessons + attacks + novelty plan")
    s = sub.add_parser("idea-add", help="supply-gated idea registration (full brief in M2f)")
    s.add_argument("--payload", required=True, help="JSON object")
    s.add_argument("--run", help="append IDEA_ADD trace to this run")
    sub.add_parser("publish", help="deliver the 4-file pack to the delivery root + mirror")

    s = sub.add_parser("feedback-add", help="record researcher verdict (only validation signal)")
    s.add_argument("slug")
    s.add_argument("--verdict", required=True, choices=["accept", "reject", "uncertain"])
    s.add_argument("--reason", required=True)
    s.add_argument("--run", help="append FEEDBACK trace to this run")
    sub.add_parser("feedback-import-v1", help="backfill legacy verdicts from the delivery root")

    sub.add_parser("zotero-manifest", help="stage manifest+SHA for audited write")
    sub.add_parser("zotero-write", help="narrow write face (manifest-approved only)")
    sub.add_parser("zotero-readback", help="read back and archive the write audit")
    sub.add_parser("backup-verify", help="backup freshness + sampled restore check")

    return p


def _emit(obj: object) -> int:
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    if isinstance(obj, dict):
        return 0 if obj.get("ok", True) else 1
    return 0


def _load_json_arg(raw: str, label: str) -> object | None:
    try:
        return json.loads(raw)
    except ValueError:
        print(json.dumps({"ok": False, "error": f"{label} is not valid JSON"}, ensure_ascii=False))
        return None


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    args = build_parser().parse_args(argv)
    cmd = args.cmd

    if cmd in NOT_IMPLEMENTED:
        return _emit(
            {
                "ok": False,
                "error": f"not implemented yet; scheduled for {NOT_IMPLEMENTED[cmd]}",
                "milestone": NOT_IMPLEMENTED[cmd],
            }
        )

    if cmd == "run-start":
        return _emit(runs.start(args.kind, args.run_id, args.resume))
    if cmd == "run-finish":
        return _emit(runs.finish(args.run_id, args.partial, args.absorb))
    if cmd == "session-brief":
        return _emit(report.session_brief())
    if cmd == "validate":
        return _emit(validate.validate(args.strict))
    if cmd == "search":
        result = search.search(args.query, args.limit, args.backend)
        if result.get("ok") and args.run:
            run = runs.load(args.run)
            if run is None or run.status != "active":
                result["run_log"] = f"run not active, query not logged: {args.run}"
            else:
                run.query_log.append(
                    {"query": args.query, "backend": ",".join(args.backend or ["active"]), "at": store.now()}
                )
                runs.append_trace(run, "SEARCH", args.query)
                runs.save(run)
        return _emit(result)
    if cmd == "screen-rank":
        return _emit(papers.screen_rank(args.run_id))
    if cmd == "query-brief":
        return _emit(report.query_brief(args.query, args.run))
    if cmd == "paper-add":
        payload = _load_json_arg(args.payload, "--payload")
        if payload is None:
            return 1
        return _emit(papers.add_paper(args.run_id, payload, args.pdf))
    if cmd == "claims-add":
        payload = _load_json_arg(args.payload, "--payload")
        if payload is None:
            return 1
        return _emit(claims.add_claim(payload, args.run))
    if cmd == "claims-view":
        return _emit(claims.view(args.topic, args.paper_key, args.verdict, args.pairs_only))
    if cmd == "idea-add":
        payload = _load_json_arg(args.payload, "--payload")
        if payload is None:
            return 1
        if not isinstance(payload, dict):
            return _emit({"ok": False, "error": "--payload must be a JSON object"})
        gate = feedback.check_supply()
        if not gate["open"]:
            return _emit({"ok": False, "error": gate["reason"], "gate": "feedback_coverage"})
        result = idea.add_idea(payload, args.run)
        if result.get("ok"):
            result["supply"] = gate["reason"]
        return _emit(result)
    if cmd == "feedback-add":
        return _emit(feedback.add_feedback(args.slug, args.verdict, args.reason, args.run))
    if cmd == "feedback-import-v1":
        return _emit(feedback.import_v1())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
