"""Prototype API router, mounted at ``/proto`` (quarantined, throwaway).

Session is carried by the ``X-Proto-Session`` header (not a cookie) to avoid
cross-origin cookie friction in local dev. The client reads ``session_id`` from
the create response and echoes it back on later requests.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from sse_starlette.sse import EventSourceResponse

from elenchus.config import get_settings
from elenchus.proto import llm
from elenchus.proto.models import (
    CheckState,
    CheckStatus,
    Claim,
    CreateCheckRequest,
    GraphData,
    RunCheckRequest,
    SessionPrefs,
    UpdateSessionRequest,
)
from elenchus.proto.pipeline import build_graph, run_check
from elenchus.proto.store import get_store

router = APIRouter(prefix="/proto", tags=["prototype"])

# Keep strong references to background tasks so they are not garbage-collected.
_tasks: set[asyncio.Task[None]] = set()


def _session_id(x_proto_session: str | None) -> str:
    return x_proto_session or uuid.uuid4().hex


@router.get("/info")
async def info() -> dict[str, bool]:
    """Report whether the prototype is running on mock data."""
    s = get_settings()
    return {"llm_mock": s.llm_mock, "search_mock": s.search_mock}


@router.post("/checks", response_model=CheckState)
async def create_check(
    body: CreateCheckRequest,
    x_proto_session: Annotated[str | None, Header()] = None,
) -> CheckState:
    """Create a check and run claim extraction (fast, synchronous)."""
    store = get_store()
    session_id = _session_id(x_proto_session)
    prefs = store.get_session(session_id)
    language = body.language or prefs.language

    extracted = await llm.extract_claims(body.text, language)
    check = CheckState(
        id=uuid.uuid4().hex[:12],
        session_id=session_id,
        input_text=body.text,
        language=language,
        status=CheckStatus.AWAITING_CONFIRMATION,
        claims=[Claim(**c.model_dump()) for c in extracted],
        mock=get_settings().llm_mock,
    )
    store.put_check(check)
    return check


@router.post("/checks/{check_id}/run", response_model=CheckState)
async def run(check_id: str, body: RunCheckRequest) -> CheckState:
    """Apply the user's claim selection/edits and start the evidence pipeline."""
    store = get_store()
    check = store.get_check(check_id)
    if check is None:
        raise HTTPException(status_code=404, detail="check not found")
    if check.status == CheckStatus.RUNNING:
        raise HTTPException(status_code=409, detail="check already running")

    if body.language:
        check.language = body.language
    if body.claims:
        by_id = {sel.id: sel for sel in body.claims}
        for claim in check.claims:
            sel = by_id.get(claim.id)
            if sel is None:
                continue
            claim.selected = sel.selected
            if sel.text_original:
                claim.text_original = sel.text_original

    check.status = CheckStatus.RUNNING
    task = asyncio.create_task(run_check(check_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return check


@router.get("/checks/{check_id}/events")
async def events(check_id: str) -> EventSourceResponse:
    """SSE stream: replays persisted events then streams live until done."""
    store = get_store()
    if store.get_check(check_id) is None:
        raise HTTPException(status_code=404, detail="check not found")
    bus = store.bus(check_id)

    async def generator():
        async for event in bus.subscribe():
            yield {"data": event.model_dump_json()}

    return EventSourceResponse(generator())


@router.get("/checks/{check_id}", response_model=CheckState)
async def get_check(check_id: str) -> CheckState:
    check = get_store().get_check(check_id)
    if check is None:
        raise HTTPException(status_code=404, detail="check not found")
    return check


@router.get("/checks/{check_id}/graph", response_model=GraphData)
async def get_graph(check_id: str) -> GraphData:
    check = get_store().get_check(check_id)
    if check is None:
        raise HTTPException(status_code=404, detail="check not found")
    return build_graph(check)


@router.get("/session", response_model=SessionPrefs)
async def get_session(x_proto_session: Annotated[str | None, Header()] = None) -> SessionPrefs:
    return get_store().get_session(_session_id(x_proto_session))


@router.put("/session", response_model=SessionPrefs)
async def update_session(
    body: UpdateSessionRequest,
    x_proto_session: Annotated[str | None, Header()] = None,
) -> SessionPrefs:
    return get_store().update_session(
        _session_id(x_proto_session),
        language=body.language,
        strict_sources=body.strict_sources,
    )
