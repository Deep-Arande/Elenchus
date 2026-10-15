"""Health check router."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from elenchus.build_info import VERSION, git_sha

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    git_sha: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe. Returns the running version and git sha."""
    return HealthResponse(status="ok", version=VERSION, git_sha=git_sha())
