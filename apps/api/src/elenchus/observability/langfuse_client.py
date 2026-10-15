"""Minimal Langfuse client wrapper.

A no-op when keys are missing (or the ``langfuse`` package is unavailable), so
local dev and CI never need Langfuse credentials. Real tracing of every LLM and
tool call is wired in later phases (AGENTS.md section 12.9); this is just the
seam.

Content masking honours ``TRACE_CONTENT`` (AGENTS.md section 8.8): default true
in dev, false in prod.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol

from elenchus.config import get_settings


class LangfuseLike(Protocol):
    """The slice of the Langfuse client surface the app relies on."""

    def flush(self) -> None: ...


class _NoopLangfuse:
    """Stand-in used when Langfuse is not configured. Silently absorbs calls."""

    enabled: bool = False

    def flush(self) -> None:  # pragma: no cover - trivial
        return None

    def __getattr__(self, _name: str) -> Any:
        def _noop(*_args: Any, **_kwargs: Any) -> None:
            return None

        return _noop


@lru_cache
def get_langfuse() -> LangfuseLike:
    """Return a configured Langfuse client, or a no-op if keys are missing."""
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return _NoopLangfuse()

    try:
        from langfuse import Langfuse
    except ImportError:  # pragma: no cover - optional dependency path
        return _NoopLangfuse()

    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host or None,
    )
    # Mark enabled so callers can branch on whether real tracing is active.
    client.enabled = True  # type: ignore[attr-defined]
    return client
