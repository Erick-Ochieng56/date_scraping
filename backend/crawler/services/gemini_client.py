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
    maximum_remote_calls: int | None = None,
) -> str:
    """
    Run a single-turn generate request; returns concatenated model text.

    ``tools`` should be a list of ``google.genai.types.Tool`` instances, e.g.
    ``[types.Tool(google_search=types.GoogleSearch())]`` for grounded search.
    """
    from google.genai import types

    client = get_genai_client()
    if tools:
        max_calls = maximum_remote_calls
        if max_calls is None:
            try:
                max_calls = int(getattr(settings, "GEMINI_GROUNDED_MAX_REMOTE_CALLS", 5))
            except (TypeError, ValueError):
                max_calls = 5
        config = types.GenerateContentConfig(
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=max(1, max_calls),
            ),
        )
    else:
        config = types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return (resp.text or "").strip()
