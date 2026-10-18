"""Grounded conversation for the prototype.

After a check completes, the user can ask follow-up questions. Answers are
grounded **strictly** in what was already gathered — the claims, their verified
evidence quotes, the sources, and the original input text. There is **no new web
search** and no new checks (that's the real build's job).

Streams the answer token-by-token. Falls back to a deterministic templated
answer in mock mode or if the model is unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator

from elenchus.config import get_settings
from elenchus.proto.llm import _client
from elenchus.proto.models import CheckState

logger = logging.getLogger("elenchus.proto.converse")

_SYSTEM = (
    "You are Elenchus, an evidence assistant. Answer ONLY from the provided "
    "context (claims, verified evidence quotes, sources, original text). If the "
    "answer is not in the context, say so plainly — do not invent facts or search. "
    "Never give a verdict (no 'true', 'false', 'fake', 'hoax'); describe what the "
    "evidence shows and cite sources by domain in parentheses."
)

_PROMPT = """CONTEXT
=======
{context}

=======
Answer the user's question using only the context above. Write in language code \
'{language}'. Keep it concise (2-5 sentences) and cite source domains.

QUESTION: {question}
"""

MAX_CONTEXT_CLAIMS = 8
MAX_EVIDENCE_PER_CLAIM = 3


def build_context(check: CheckState) -> str:
    """Compact, grounded context string for the answer model."""
    parts: list[str] = [f"ORIGINAL TEXT:\n{check.input_text.strip()[:1500]}"]
    for claim in [c for c in check.claims if c.selected][:MAX_CONTEXT_CLAIMS]:
        block = [f"CLAIM: {claim.text_original}", f"STATUS: {claim.status or 'pending'}"]
        if claim.summary:
            block.append(f"SUMMARY: {claim.summary}")
        for ev in claim.evidence[:MAX_EVIDENCE_PER_CLAIM]:
            src = check.sources.get(ev.source_id)
            domain = (src.domain if src else None) or "source"
            block.append(f'  - [{ev.stance}] "{ev.quote[:220]}" ({domain})')
        parts.append("\n".join(block))
    return "\n\n".join(parts)


async def answer_stream(check: CheckState, question: str) -> AsyncIterator[str]:
    """Yield answer text deltas, grounded in the check's gathered evidence."""
    settings = get_settings()
    if settings.llm_mock:
        async for delta in _mock_stream(check, question):
            yield delta
        return

    from google.genai import types

    prompt = _PROMPT.format(
        context=build_context(check), language=check.language, question=question
    )
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def produce() -> None:
        try:
            stream = _client().models.generate_content_stream(
                model=settings.gemini_model_main,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=_SYSTEM),
            )
            for chunk in stream:
                text = getattr(chunk, "text", "") or ""
                if text:
                    loop.call_soon_threadsafe(queue.put_nowait, text)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user as a soft note
            logger.warning("answer stream failed: %s", exc)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                "The answer model is busy right now — please try again in a moment.",
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=produce, daemon=True).start()

    produced = False
    while True:
        item = await queue.get()
        if item is None:
            break
        produced = True
        yield item
    if not produced:
        yield _mock_answer(check, question)


# --------------------------------------------------------------------------- #
# Deterministic mock
# --------------------------------------------------------------------------- #
def _mock_answer(check: CheckState, question: str) -> str:
    selected = [c for c in check.claims if c.selected]
    n_sources = len({ev.source_id for c in selected for ev in c.evidence})
    statuses = ", ".join(f"“{c.text_original[:40]}…” → {c.status}" for c in selected[:3])
    return (
        f"Based only on what we gathered this session ({len(selected)} claim(s), "
        f"{n_sources} source(s)): {statuses}. "
        "Read the cited sources above for the full picture. "
        "(Prototype mock answer — grounded in the evidence already collected.)"
    )


async def _mock_stream(check: CheckState, question: str) -> AsyncIterator[str]:
    text = _mock_answer(check, question)
    for word in text.split(" "):
        await asyncio.sleep(0.02)
        yield word + " "
