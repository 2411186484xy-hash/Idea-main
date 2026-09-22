"""L0 contracts: record types + ErrorEnvelope + trace event constants.

Zero project imports, zero IO. Construction validates required fields and
enums; the store-level codec (to_dict/from_dict) rejects any unknown
schema_version (change field = change code + one-off data script, never a
migration machine).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 3

TRACE_EVENTS = (
    "RUN_START", "RUN_RESUME", "PAPER_ADD", "SCREEN", "SEARCH", "RETRACT_HIT", "PDF_EXTRACT",
    "CLAIM_ADD", "IDEA_ADD", "PUBLISH", "ZOTERO_WRITE", "ZOTERO_READBACK", "FEEDBACK",
)

RUN_KINDS = ("weekly", "idea")
RUN_STATUSES = ("active", "partial", "completed")
COVERAGE_ROUTES = ("direct", "counter_boundary", "transfer", "frontier")
SCREEN_STATUSES = ("pending", "ranked", "selected", "rejected")
RETRACTION_STATUSES = ("none", "flagged", "confirmed")
CONFIDENCES = ("high", "medium", "low")
VERIFIER_VERDICTS = ("CONFIRMED", "DEVIATED", "NOT_FOUND")
QUALITY_DIMS = ("novelty", "rigor", "feasibility", "clarity", "data_availability", "venue_fit")
IDEA_STATUSES = ("draft", "published", "accepted", "rejected", "uncertain")
FEEDBACK_VERDICTS = ("accept", "reject", "uncertain")
ERROR_CATEGORIES = ("network", "http", "parse", "config", "gate")
NOVELTY_RESULTS = ("hit", "empty", "error")
NOVELTY_CONFIDENCES = ("strong", "weak")
DISPROOF_FIELDS = ("experiment", "controls", "decision_rule", "failure_interpretation")

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,}$")
TOPIC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,}$")
RUN_ID_RE = re.compile(r"^(WEEKLYRUN|IDEARUN)-\d{8}-\d{6}$")
CLAIM_ID_RE = re.compile(r"^CLM-\d{8}-\d{3,}$")
IDENTIFIER_KEYS = ("doi", "pmid", "arxiv_id", "openreview_id", "pdf_sha256")


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _one_of(value: str, allowed: tuple[str, ...], label: str) -> None:
    _require(value in allowed, f"{label} must be one of {allowed}, got: {value!r}")


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_paper_key(identifiers: dict[str, Any]) -> str:
    """Identifier precedence: doi > arxiv > pmid > openreview > sha12 (pdf_sha256[:12])."""
    for key, prefix in (("doi", "doi"), ("arxiv_id", "arxiv"), ("pmid", "pmid"),
                        ("openreview_id", "openreview")):
        val = str(identifiers.get(key) or "").strip()
        if val:
            return f"{prefix}:{val.lower()}"
    sha = str(identifiers.get("pdf_sha256") or "").strip()
    _require(sha, "paper_key needs at least one identifier (doi/pmid/arxiv_id/pdf_sha256)")
    return f"sha12:{sha[:12].lower()}"


@dataclass
class ErrorEnvelope:
    """Unified adapter error contract (docling ErrorItem/FailureCategory borrow)."""

    source: str
    category: str
    message: str
    detail: str | None = None

    def __post_init__(self) -> None:
        _one_of(self.category, ERROR_CATEGORIES, "error.category")
        _require(bool(self.source), "error.source required")
        _require(bool(self.message), "error.message required")


@dataclass
class Run:
    """Temporary working state; deleted on finish (session-log keeps one line)."""

    run_id: str
    kind: str
    status: str
    attempt: int
    created_at: str
    updated_at: str
    paper_candidates: list[PaperCandidate] = field(default_factory=list)
    coverage: dict[str, int] = field(default_factory=dict)
    idea_seeds: list[dict[str, Any]] = field(default_factory=list)
    query_log: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    uncertainty_disclosure: list[str] = field(default_factory=list)
    completed_at: str | None = None
    gap_note: str | None = None
    topic: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require(bool(RUN_ID_RE.match(self.run_id)), f"bad run_id: {self.run_id!r}")
        expected = "weekly" if self.run_id.startswith("WEEKLYRUN") else "idea"
        _require(self.kind == expected, f"run_id prefix/kind mismatch: {self.kind}")
        _one_of(self.kind, RUN_KINDS, "run.kind")
        _one_of(self.status, RUN_STATUSES, "run.status")
        _require(self.attempt >= 1, "attempt must be >= 1")
        if not self.coverage:
            self.coverage = {route: 0 for route in COVERAGE_ROUTES}
        missing = [r for r in COVERAGE_ROUTES if r not in self.coverage]
        _require(not missing, f"coverage missing routes: {missing}")
        if self.topic is not None:
            _require(bool(TOPIC_ID_RE.match(self.topic)), f"bad run.topic: {self.topic!r}")


@dataclass
class PaperCandidate:
    schema_version: int = SCHEMA_VERSION
    title: str = ""
    authors: list[str] = field(default_factory=list)
    paper_key: str = ""
    identifiers: dict[str, str] = field(default_factory=dict)
    discovery_class: str = "direct"
    source_backend: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    abstract: str = ""
    abstract_sha256: str = ""
    retraction: dict[str, Any] = field(default_factory=dict)
    year: int | None = None
    venue: str | None = None
    cited_by_count: int | None = None
    screen_status: str | None = None
    evidence: dict[str, str] | None = None

    def __post_init__(self) -> None:
        _require(bool(self.title.strip()), "candidate.title required")
        _require(bool(self.source_backend), "candidate.source_backend required")
        _one_of(self.discovery_class, COVERAGE_ROUTES, "candidate.discovery_class")
        present = [k for k in IDENTIFIER_KEYS if str(self.identifiers.get(k) or "").strip()]
        _require(bool(present), f"at least one identifier required {IDENTIFIER_KEYS}")
        computed = make_paper_key(self.identifiers)
        if not self.paper_key:
            self.paper_key = computed
        _require(self.paper_key == computed, f"paper_key drift: {self.paper_key} != {computed}")
        _require(bool(self.abstract_sha256), "candidate.abstract_sha256 required")
        if not self.retraction:
            self.retraction = {"status": "none", "checked_backends": [], "checked_at": ""}
        _one_of(self.retraction.get("status", "none"), RETRACTION_STATUSES, "retraction.status")
        if self.screen_status is not None:
            _one_of(self.screen_status, SCREEN_STATUSES, "candidate.screen_status")
        for key in ("one_line_evidence", "evidence_role"):
            _require(not self.evidence or bool(self.evidence.get(key, "").strip()),
                     f"evidence.{key} required when evidence present")


@dataclass
class Claim:
    """Page-anchored claim: quote must be verbatim from the paper text."""

    schema_version: int = SCHEMA_VERSION
    id: str = ""
    paper_key: str = ""
    topic: str = ""
    text: str = ""
    quote: str = ""
    page_anchor: int = 0
    confidence: str = "medium"
    verifier_verdict: str = "NOT_FOUND"
    verifier_note: str | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        _require(bool(CLAIM_ID_RE.match(self.id)), f"bad claim id: {self.id!r} (CLM-YYYYMMDD-NNN)")
        _require(bool(self.paper_key.strip()), "claim.paper_key required")
        _require(bool(self.topic.strip()), "claim.topic required")
        _require(bool(self.text.strip()), "claim.text required")
        _require(bool(self.quote.strip()), "claim.quote required (verbatim)")
        _require(isinstance(self.page_anchor, int) and self.page_anchor >= 1,
                 f"claim.page_anchor must be a page number >= 1, got: {self.page_anchor!r}")
        _one_of(self.confidence, CONFIDENCES, "claim.confidence")
        _one_of(self.verifier_verdict, VERIFIER_VERDICTS, "claim.verifier_verdict")
        _require(bool(self.created_at), "claim.created_at required")


@dataclass
class IdeaCandidate:
    schema_version: int = SCHEMA_VERSION
    slug: str = ""
    title: str = ""
    hypothesis: str = ""
    collision: dict[str, str] = field(default_factory=dict)
    disproof: dict[str, str] = field(default_factory=dict)
    quality_card: dict[str, dict[str, Any]] = field(default_factory=dict)
    attacks: list[str] = field(default_factory=list)
    novelty_log: list[dict[str, str]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    status: str = "draft"

    def __post_init__(self) -> None:
        _require(bool(SLUG_RE.match(self.slug)), f"bad slug: {self.slug!r}")
        _require(bool(self.title.strip()), "idea.title required")
        _require(bool(self.hypothesis.strip()), "idea.hypothesis required")
        for key in ("seed", "source_domain", "target_domain"):
            _require(bool(self.collision.get(key, "").strip()), f"collision.{key} required")
        missing = [d for d in QUALITY_DIMS if d not in self.quality_card]
        _require(not missing, f"quality_card missing dims: {missing}")
        for dim, card in self.quality_card.items():
            _one_of(dim, QUALITY_DIMS, "quality_card dim")
            score = card.get("score")
            _require(isinstance(score, int) and 1 <= score <= 5,
                     f"quality_card.{dim}.score must be int 1-5")
            _require(bool(str(card.get("rationale", "")).strip()),
                     f"quality_card.{dim}.rationale required")
        _require(isinstance(self.attacks, list) and len(self.attacks) >= 6
                 and all(str(a).strip() for a in self.attacks),
                 "at least 6 non-empty attacks required")
        missing_d = [k for k in DISPROOF_FIELDS if not str(self.disproof.get(k, "")).strip()]
        _require(not missing_d, f"disproof missing fields: {missing_d}")
        for entry in self.novelty_log:
            for key in ("query", "backend", "note"):
                _require(bool(entry.get(key, "").strip()), f"novelty_log.{key} required")
            _one_of(entry.get("result", ""), NOVELTY_RESULTS, "novelty_log.result")
            _one_of(entry.get("confidence", ""), NOVELTY_CONFIDENCES, "novelty_log.confidence")
            if entry.get("result") == "hit":
                _require(bool(entry.get("top_match", "").strip()),
                         "novelty_log.top_match required when result=hit")
        _require(bool(self.evidence_refs) and all(str(r).strip() for r in self.evidence_refs),
                 "evidence_refs (corpus gate 3+1+1) required")
        _one_of(self.status, IDEA_STATUSES, "idea.status")


@dataclass
class Feedback:
    schema_version: int = SCHEMA_VERSION
    slug: str = ""
    verdict: str = ""
    reason: str = ""
    at: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.slug.strip()), "feedback.slug required")
        _one_of(self.verdict, FEEDBACK_VERDICTS, "feedback.verdict")
        _require(bool(self.reason.strip()), "feedback.reason required (the only validation signal)")
        _require(bool(self.at), "feedback.at required")


@dataclass
class FailureEntry:
    schema_version: int = SCHEMA_VERSION
    slug: str = ""
    stage: str = ""
    reason: str = ""
    lesson: str | None = None
    at: str = ""

    def __post_init__(self) -> None:
        for label in ("slug", "stage", "reason", "at"):
            _require(bool(getattr(self, label).strip()), f"failure.{label} required")


@dataclass
class ZoteroManifest:
    schema_version: int = SCHEMA_VERSION
    items: list[dict[str, Any]] = field(default_factory=list)
    sha256: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.items), "manifest.items required")
        body = json.dumps(self.items, ensure_ascii=False, sort_keys=True)
        _require(self.sha256 == sha256_hex(body), "manifest.sha256 must match canonical hash of items")
        _require(bool(self.created_at), "manifest.created_at required")


@dataclass
class ReadbackReport:
    schema_version: int = SCHEMA_VERSION
    manifest_sha256: str = ""
    expected: int = 0
    found: int = 0
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    at: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.manifest_sha256), "readback.manifest_sha256 required")
        _require(self.expected >= 0 and self.found >= 0, "readback counts must be >= 0")
        _require(bool(self.at), "readback.at required")

    @property
    def ok(self) -> bool:
        return not self.missing and not self.extra and self.expected == self.found
