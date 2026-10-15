"""Build/version metadata for the ``/health`` endpoint.

The git sha is resolved once, preferring an injected ``GIT_SHA`` env var (set in
Docker/CI where the ``.git`` dir may be absent) and falling back to a local
``git rev-parse``. Never raises — returns ``"unknown"`` if it cannot tell.
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache

from elenchus import __version__

VERSION = __version__


@lru_cache
def git_sha() -> str:
    env_sha = os.environ.get("GIT_SHA")
    if env_sha:
        return env_sha.strip()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"
