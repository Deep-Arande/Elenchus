"""Application configuration.

Every tunable number, limit, threshold and secret lives here as a
pydantic-settings field with an env override and a documented default
(AGENTS.md section 12.8 and the variable list in section 14).

Defaults mirror ``.env.example`` exactly. Nothing here reaches outside the
process; secrets only ever come from the environment.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All backend configuration, loaded from the environment / ``.env``.

    ``extra="ignore"`` lets the shared ``.env`` carry frontend-only
    ``NEXT_PUBLIC_*`` variables without tripping validation here.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM (Gemini via google-genai) ---
    gemini_api_key: str = Field(default="")
    # Model ids come only from env; never hardcode a Gemini version (and never a
    # 2.5 model — those are being shut down). Resolve current ids at first use.
    gemini_model_fast: str = Field(default="")
    gemini_model_main: str = Field(default="")
    gemini_model_pro: str = Field(default="")

    # --- Search & data ---
    search_provider: str = Field(default="firecrawl")  # firecrawl | brave | exa
    firecrawl_api_key: str = Field(default="")
    brave_api_key: str = Field(default="")
    exa_api_key: str = Field(default="")
    google_factcheck_api_key: str = Field(default="")

    # --- Retrieval ---
    # V1 default is the Gemini embedding backend so the api/worker carry no
    # multi-GB local model (AGENTS.md section 3). `bge-m3` is for self-hosting.
    embedding_backend: str = Field(default="gemini")  # gemini | bge-m3
    gemini_embedding_model: str = Field(default="")
    embedding_dim: int = Field(default=1536)
    reranker_backend: str = Field(default="llm")  # llm | local
    match_threshold: float = Field(default=0.75)
    similar_claim_threshold: float = Field(default=0.85)

    # --- Agent budgets (AGENTS.md section 6.1) ---
    agent_max_steps: int = Field(default=6)
    agent_max_searches: int = Field(default=8)
    agent_max_pages: int = Field(default=8)
    agent_timeout_seconds: int = Field(default=90)
    check_max_cost_usd: float = Field(default=0.10)

    # --- Limits ---
    anon_check_limit: int = Field(default=3)
    daily_check_limit: int = Field(default=25)
    admin_emails: str = Field(default="")

    # --- Supabase / DB / Redis ---
    supabase_url: str = Field(default="")
    supabase_anon_key: str = Field(default="")
    supabase_service_role_key: str = Field(default="")
    supabase_jwks_url: str = Field(default="")
    supabase_jwt_secret: str = Field(default="")  # legacy projects only
    database_url: str = Field(default="")
    redis_url: str = Field(default="redis://localhost:6379")

    # --- Observability ---
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="")
    trace_content: bool = Field(default=True)

    # --- App ---
    app_base_url: str = Field(default="http://localhost:3000")
    api_base_url: str = Field(default="http://localhost:8000")

    @property
    def admin_email_list(self) -> list[str]:
        """Parsed, lowercased admin emails from the comma-separated env var."""
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    # --- Prototype (vertical slice) helpers ---
    # The throwaway prototype runs on deterministic mock data whenever the
    # corresponding key is absent, so the whole flow is demoable without any
    # credentials. These are prototype-only conveniences.
    @property
    def llm_mock(self) -> bool:
        """True when Gemini is not configured — the prototype falls back to mocks."""
        return not self.gemini_api_key

    @property
    def search_mock(self) -> bool:
        """True when Firecrawl is not configured — the prototype falls back to mocks."""
        return not self.firecrawl_api_key


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Use this everywhere instead of ``Settings()``."""
    return Settings()
