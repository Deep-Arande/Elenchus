"""Throwaway vertical-slice prototype (see docs/PROTOTYPE.md).

QUARANTINED on purpose: everything under ``elenchus.proto`` is in-memory,
text-only, and runs on a simple async pipeline with a mock fallback. None of it
touches the database. When the serious build begins, this whole package and its
``/proto`` router are deleted in one commit — the real agent/retrieval/search
modules are built fresh per BUILD_PROMPTS.md.

Do not import ``elenchus.proto`` from non-prototype code.
"""
