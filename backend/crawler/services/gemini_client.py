"""
Shared Gemini (Developer API) client using the ``google-genai`` SDK.

Replaces deprecated ``google.generativeai`` / ``google-generativeai``.
"""

from __future__ import annotations

import logging
import threading
import time
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


_throttle_lock = threading.Lock()
_last_call_at = 0.0


def _min_seconds_between_calls() -> float:
    try:
        return max(0.0, float(getattr(settings, "GEMINI_MIN_SECONDS_BETWEEN_CALLS", 6.5)))
    except (TypeError, ValueError):
        return 6.5


def _throttle_gemini_call() -> None:
    """
    Enforce a minimum interval between successive Gemini calls, process-wide.

    Gemini's per-minute request quota applies whether the API key is free-tier or
    billed — a billed key just has a higher (still finite) limit. Without pacing,
    a job fires one call per candidate as fast as pages are fetched (query
    generation, grounded search, page extraction, competitor-signal derivation all
    share this one chokepoint), blowing through that quota within the first few
    candidates and forcing everything after onto the weaker rules-only fallback.
    """
    global _last_call_at
    interval = _min_seconds_between_calls()
    if interval <= 0:
        return
    with _throttle_lock:
        now = time.monotonic()
        wait = _last_call_at + interval - now
        if wait > 0:
            time.sleep(wait)
        _last_call_at = time.monotonic()


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
    _throttle_gemini_call()
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
