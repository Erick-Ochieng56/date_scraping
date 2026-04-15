"""
Shared Gemini (Developer API) client using the ``google-genai`` SDK.

Replaces deprecated ``google.generativeai`` / ``google-generativeai``.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def _cached_client(api_key: str):
    from google import genai

    return genai.Client(api_key=api_key)


def get_genai_client():
    key = (getattr(settings, "GEMINI_API_KEY", None) or "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return _cached_client(key)


def generate_text(
    *,
    model: str,
    prompt: str,
    tools: list[Any] | None = None,
) -> str:
    """
    Run a single-turn generate request; returns concatenated model text.

    ``tools`` should be a list of ``google.genai.types.Tool`` instances, e.g.
    ``[types.Tool(google_search=types.GoogleSearch())]`` for grounded search.
    """
    from google.genai import types

    client = get_genai_client()
    config = types.GenerateContentConfig(tools=tools) if tools else None
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return (resp.text or "").strip()
