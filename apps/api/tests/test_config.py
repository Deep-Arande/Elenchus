"""Tests for configuration defaults.

Guards the V1 retrieval decision: Gemini embeddings + LLM reranker are the
defaults so the api/worker carry no multi-GB local model (AGENTS.md section 3).
"""

from __future__ import annotations

from elenchus.config import Settings


def test_retrieval_defaults_are_gemini() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.embedding_backend == "gemini"
    assert s.reranker_backend == "llm"


def test_budget_and_threshold_defaults() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.match_threshold == 0.75
    assert s.similar_claim_threshold == 0.85
    assert s.agent_max_steps == 6
    assert s.agent_timeout_seconds == 90
    assert s.anon_check_limit == 3
    assert s.daily_check_limit == 25


def test_admin_email_list_parsing() -> None:
    s = Settings(_env_file=None, admin_emails="A@x.com, b@y.com ,")  # type: ignore[call-arg]
    assert s.admin_email_list == ["a@x.com", "b@y.com"]
