"""FastAPI application factory.

Keep this thin: it wires configuration, middleware and routers together.
Business logic lives in the feature packages (AGENTS.md section 4).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from elenchus.build_info import VERSION
from elenchus.config import Settings, get_settings
from elenchus.proto.router import router as proto_router
from elenchus.routers import health


def _configure_logging() -> None:
    """Make ``elenchus.*`` logs visible on stderr regardless of uvicorn config."""
    lg = logging.getLogger("elenchus")
    lg.setLevel(logging.INFO)
    if not lg.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        lg.addHandler(handler)
        lg.propagate = False


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the FastAPI app.

    Accepts an optional ``settings`` override so tests can inject config without
    touching the environment.
    """
    settings = settings or get_settings()
    _configure_logging()

    app = FastAPI(
        title="Elenchus API",
        version=VERSION,
        summary="Evidence, not verdicts — a personal fact-checking workspace.",
    )

    # CORS: in Phase 0 we allow the local web app; Phase 9 locks this to the
    # deployed app domain.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.app_base_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    # Prototype (vertical slice) — throwaway, quarantined under /proto.
    # Delete this line and the elenchus.proto package to remove the prototype.
    app.include_router(proto_router)

    return app


app = create_app()
