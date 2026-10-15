# Backend image (FastAPI api + arq worker share this image).
FROM python:3.12-slim

# uv for dependency management (AGENTS.md section 3).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies first (cached layer), then the project.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# git sha is injected at build time since the .git dir is not copied in.
ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

EXPOSE 8000

# Overridden by the worker service in docker-compose.
CMD ["uvicorn", "elenchus.main:app", "--host", "0.0.0.0", "--port", "8000"]
