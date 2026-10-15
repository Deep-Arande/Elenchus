"""In-memory event bus for the prototype's live trace.

Each check has an ``EventBus`` that keeps an ordered list of events (for replay
on a late/refreshed subscriber) and fans new events out to live subscribers.
Backed by ``asyncio.Queue``; no Redis (the real build uses Redis pub/sub).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

# Typed event names emitted by the pipeline (AGENTS.md 6.1 "Live events" subset).
EventType = str  # one of: step_started, step_finished, query, search_results,
#                            page_fetched, evidence, status, warning, error, done


class CheckEvent(BaseModel):
    seq: int
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EventBus:
    """Replayable, multi-subscriber event stream for a single check."""

    def __init__(self) -> None:
        self._events: list[CheckEvent] = []
        self._subscribers: set[asyncio.Queue[CheckEvent | None]] = set()
        self._lock = asyncio.Lock()
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    async def emit(self, type: EventType, payload: dict[str, Any] | None = None) -> CheckEvent:
        async with self._lock:
            event = CheckEvent(seq=len(self._events), type=type, payload=payload or {})
            self._events.append(event)
            for queue in self._subscribers:
                queue.put_nowait(event)
            return event

    async def close(self) -> None:
        """Mark the stream finished and release all live subscribers."""
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            for queue in self._subscribers:
                queue.put_nowait(None)  # sentinel
            self._subscribers.clear()

    async def subscribe(self) -> AsyncIterator[CheckEvent]:
        """Yield all past events, then stream live ones until the bus closes."""
        queue: asyncio.Queue[CheckEvent | None] = asyncio.Queue()
        async with self._lock:
            snapshot = list(self._events)
            already_closed = self._closed
            if not already_closed:
                self._subscribers.add(queue)

        for event in snapshot:
            yield event
        if already_closed:
            return

        last_seq = snapshot[-1].seq if snapshot else -1
        try:
            while True:
                item = await queue.get()
                if item is None:  # sentinel: bus closed
                    return
                # Avoid re-emitting anything already in the replayed snapshot.
                if item.seq <= last_seq:
                    continue
                yield item
        finally:
            async with self._lock:
                self._subscribers.discard(queue)
