"""Runtime Pydantic models for the prototype (in-memory only; no DB).

These mirror a slice of AGENTS.md section 5 but as plain runtime objects. They
are intentionally lighter than the real schema. The prototype never persists
them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["en", "hi", "mr", "hi-Latn", "other"]
ClaimType = Literal["factual", "opinion", "prediction", "other"]
Stance = Literal["supports", "contradicts", "context"]


class EvidenceStatus(StrEnum):
    """Prototype statuses. The ALREADY_FACT_CHECKED path is out of scope here."""

    EVIDENCE_FOUND = "EVIDENCE_FOUND"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class CheckStatus(StrEnum):
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Claims
# --------------------------------------------------------------------------- #
class ExtractedClaim(BaseModel):
    """A claim as returned by extraction, before evidence gathering."""

    id: str
    text_original: str
    text_en: str | None = None
    language: Language = "en"
    claim_type: ClaimType = "factual"
    checkworthy: bool = True
    entities: list[str] = Field(default_factory=list)
    time_reference: str | None = None
    selected: bool = True


class SourceRef(BaseModel):
    """A web source a piece of evidence came from."""

    id: str
    url: str
    domain: str | None = None
    title: str | None = None


class EvidenceItem(BaseModel):
    """One verified piece of evidence for a claim."""

    source_id: str
    stance: Stance
    quote: str
    relevance: float = 0.0
    verified: bool = False


class Claim(ExtractedClaim):
    """A claim enriched with the result of the evidence run."""

    status: EvidenceStatus | None = None
    confidence: float | None = None
    summary: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Graph
# --------------------------------------------------------------------------- #
class GraphNode(BaseModel):
    id: str
    type: Literal["claim", "source"]
    label: str
    status: EvidenceStatus | None = None


class GraphEdge(BaseModel):
    id: str
    source: str  # from node id
    target: str  # to node id
    type: Stance


class GraphData(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Check + session
# --------------------------------------------------------------------------- #
class ConversationTurn(BaseModel):
    """One message in the session conversation (grounded Q&A after the check)."""

    id: str
    role: Literal["user", "assistant"]
    text: str
    created_at: datetime = Field(default_factory=_now)


class CheckState(BaseModel):
    """The full in-memory state of one check (and its grounded conversation)."""

    id: str
    session_id: str
    input_text: str
    language: Language = "en"
    status: CheckStatus = CheckStatus.AWAITING_CONFIRMATION
    claims: list[Claim] = Field(default_factory=list)
    sources: dict[str, SourceRef] = Field(default_factory=dict)
    turns: list[ConversationTurn] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)
    mock: bool = False


class SessionPrefs(BaseModel):
    """Session-only, non-persisted preferences (lost when the session ends)."""

    session_id: str
    language: Language = "en"
    strict_sources: bool = True


# --------------------------------------------------------------------------- #
# API request/response payloads
# --------------------------------------------------------------------------- #
class CreateCheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    language: Language | None = None


class ClaimSelection(BaseModel):
    id: str
    selected: bool = True
    text_original: str | None = None  # allow light edits before running


class RunCheckRequest(BaseModel):
    claims: list[ClaimSelection] = Field(default_factory=list)
    language: Language | None = None


class UpdateSessionRequest(BaseModel):
    language: Language | None = None
    strict_sources: bool | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
