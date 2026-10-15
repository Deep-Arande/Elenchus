"""Process-wide in-memory store for the prototype.

Holds checks, their event buses, and session-only preferences. Everything is
lost on restart — by design (docs/PROTOTYPE.md). No DB, no persistence.
"""

from __future__ import annotations

from elenchus.proto.events import EventBus
from elenchus.proto.models import CheckState, Language, SessionPrefs


class ProtoStore:
    def __init__(self) -> None:
        self._checks: dict[str, CheckState] = {}
        self._buses: dict[str, EventBus] = {}
        self._sessions: dict[str, SessionPrefs] = {}

    # --- checks ---
    def put_check(self, check: CheckState) -> None:
        self._checks[check.id] = check

    def get_check(self, check_id: str) -> CheckState | None:
        return self._checks.get(check_id)

    # --- event buses ---
    def bus(self, check_id: str) -> EventBus:
        bus = self._buses.get(check_id)
        if bus is None:
            bus = EventBus()
            self._buses[check_id] = bus
        return bus

    # --- session preferences (session-only, non-persisted) ---
    def get_session(self, session_id: str) -> SessionPrefs:
        prefs = self._sessions.get(session_id)
        if prefs is None:
            prefs = SessionPrefs(session_id=session_id)
            self._sessions[session_id] = prefs
        return prefs

    def update_session(
        self,
        session_id: str,
        *,
        language: Language | None = None,
        strict_sources: bool | None = None,
    ) -> SessionPrefs:
        prefs = self.get_session(session_id)
        if language is not None:
            prefs.language = language
        if strict_sources is not None:
            prefs.strict_sources = strict_sources
        return prefs


_store = ProtoStore()


def get_store() -> ProtoStore:
    return _store
