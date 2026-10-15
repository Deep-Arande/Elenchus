"""The prototype check pipeline (simple async; no LangGraph).

Per selected claim: plan a query or two -> search -> fetch top pages -> extract
evidence -> verify quotes against the fetched text -> compose a cited summary ->
assign a status. Every step emits a live event. Finally builds the claim/source
graph. Bounded by small caps (the real build has full budgets in agent/budget.py).
"""

from __future__ import annotations

import difflib
import re
import unicodedata
import uuid

from elenchus.proto import llm, search
from elenchus.proto.events import EventBus
from elenchus.proto.models import (
    CheckState,
    CheckStatus,
    Claim,
    EvidenceItem,
    EvidenceStatus,
    GraphData,
    GraphEdge,
    GraphNode,
    SourceRef,
)
from elenchus.proto.store import get_store

MAX_CLAIMS = 4
MAX_QUERIES = 2
MAX_PAGES_PER_CLAIM = 3
VERIFY_RATIO = 0.9


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_quote(quote: str, page_text: str) -> bool:
    """Deterministic citation check: quote must exist in the page text.

    Normalises whitespace/Unicode; accepts an exact substring, otherwise a close
    fuzzy match (ratio >= VERIFY_RATIO) against the best-aligned window.
    """
    q = _normalise(quote)
    p = _normalise(page_text)
    if not q:
        return False
    if q in p:
        return True
    matcher = difflib.SequenceMatcher(None, q, p)
    return matcher.find_longest_match(0, len(q), 0, len(p)).size / len(q) >= VERIFY_RATIO


def _plan_queries(claim: Claim) -> list[str]:
    queries: list[str] = []
    primary = claim.text_en or claim.text_original
    queries.append(primary)
    if claim.language != "en" and claim.text_original not in queries:
        queries.append(claim.text_original)
    return queries[:MAX_QUERIES]


async def run_check(check_id: str) -> None:
    store = get_store()
    check = store.get_check(check_id)
    bus = store.bus(check_id)
    if check is None:
        await bus.emit("error", {"message": "check not found"})
        await bus.close()
        return

    try:
        check.status = CheckStatus.RUNNING
        selected = [c for c in check.claims if c.selected][:MAX_CLAIMS]
        if not selected:
            await bus.emit("warning", {"message": "No claims selected to check."})

        for claim in selected:
            await _run_claim(check, claim, bus)

        check.status = CheckStatus.DONE
        await bus.emit("done", {"check_id": check_id})
    except Exception as exc:  # pragma: no cover - defensive; surfaced to UI
        check.status = CheckStatus.FAILED
        check.error = str(exc)
        await bus.emit("error", {"message": str(exc)})
    finally:
        await bus.close()


async def _run_claim(check: CheckState, claim: Claim, bus: EventBus) -> None:
    await bus.emit(
        "step_started", {"claim_id": claim.id, "step": "search", "claim": claim.text_original}
    )

    seen_urls: set[str] = set()
    for query in _plan_queries(claim):
        await bus.emit("query", {"claim_id": claim.id, "query": query})
        hits = await search.search(query, limit=MAX_PAGES_PER_CLAIM)
        await bus.emit(
            "search_results",
            {"claim_id": claim.id, "hits": [h.model_dump() for h in hits]},
        )
        for hit in hits:
            if hit.url in seen_urls or len(seen_urls) >= MAX_PAGES_PER_CLAIM:
                continue
            seen_urls.add(hit.url)
            await _read_source(check, claim, hit, bus)

    # Compose + status.
    if claim.evidence:
        lines = [
            f"{e.stance}: {e.quote} ({check.sources[e.source_id].domain or ''})"
            for e in claim.evidence
        ]
        claim.summary = await llm.compose_summary(claim.text_original, lines, check.language)
        claim.status = EvidenceStatus.EVIDENCE_FOUND
        claim.confidence = min(0.95, 0.5 + 0.1 * len(claim.evidence))
    else:
        claim.summary = await llm.compose_summary(claim.text_original, [], check.language)
        claim.status = EvidenceStatus.INSUFFICIENT_EVIDENCE
        claim.confidence = 0.3

    await bus.emit(
        "status",
        {
            "claim_id": claim.id,
            "status": claim.status.value,
            "summary": claim.summary,
            "confidence": claim.confidence,
            "evidence_count": len(claim.evidence),
        },
    )
    await bus.emit("step_finished", {"claim_id": claim.id, "step": "search"})


async def _read_source(
    check: CheckState, claim: Claim, hit: search.SearchHit, bus: EventBus
) -> None:
    source_id = uuid.uuid4().hex[:12]
    check.sources[source_id] = SourceRef(
        id=source_id, url=hit.url, domain=hit.domain, title=hit.title
    )
    await bus.emit(
        "page_fetched",
        {"claim_id": claim.id, "source_id": source_id, "url": hit.url, "title": hit.title},
    )
    page_text = await search.fetch(hit.url)
    for stance, quote, relevance in await llm.extract_evidence(
        claim.text_original, source_id, page_text
    ):
        verified = verify_quote(quote, page_text)
        if not verified:
            continue
        claim.evidence.append(
            EvidenceItem(
                source_id=source_id, stance=stance, quote=quote, relevance=relevance, verified=True
            )
        )
        await bus.emit(
            "evidence",
            {
                "claim_id": claim.id,
                "source_id": source_id,
                "stance": stance,
                "quote": quote,
                "relevance": relevance,
                "verified": verified,
            },
        )


def build_graph(check: CheckState) -> GraphData:
    """Build a claim/source graph from a finished check's evidence."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    used_sources: set[str] = set()

    for claim in check.claims:
        if not claim.selected:
            continue
        nodes.append(
            GraphNode(
                id=f"claim:{claim.id}",
                type="claim",
                label=claim.text_original[:80],
                status=claim.status,
            )
        )
        for ev in claim.evidence:
            if ev.source_id not in used_sources:
                used_sources.add(ev.source_id)
                src = check.sources[ev.source_id]
                nodes.append(
                    GraphNode(
                        id=f"source:{ev.source_id}",
                        type="source",
                        label=src.domain or src.title or src.url,
                    )
                )
            edges.append(
                GraphEdge(
                    id=uuid.uuid4().hex[:12],
                    source=f"claim:{claim.id}",
                    target=f"source:{ev.source_id}",
                    type=ev.stance,
                )
            )
    return GraphData(nodes=nodes, edges=edges)
