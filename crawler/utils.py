from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple per-domain rate limiter (1 request per N seconds).

    Note: Celery tasks run in separate worker processes, so this limiter is
    best-effort within a single process.
    """

    def __init__(self, seconds: float = 1.5):
        self.seconds = float(seconds)
        self._last_request: dict[str, float] = {}

    def wait(self, domain: str) -> None:
        """Sleep if needed to respect per-domain delay."""
        last = self._last_request.get(domain, 0.0)
        elapsed = time.time() - last
        if elapsed < self.seconds:
            time.sleep(self.seconds - elapsed)
        self._last_request[domain] = time.time()


def compute_payload_hash(payload: dict[str, Any]) -> str:
    """Compute SHA-256 hash of a JSON-serializable payload."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def clean_text(html: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    soup = BeautifulSoup(html or "", "lxml")
    return " ".join(soup.get_text(" ", strip=True).split())


def normalize_url(url: str) -> str:
    """Normalize URL by stripping fragments and trailing slashes (except root)."""
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    if not parsed.scheme:
        return url
    rebuilt = parsed._replace(fragment="").geturl()
    if rebuilt.endswith("/") and parsed.path not in {"", "/"}:
        rebuilt = rebuilt.rstrip("/")
    return rebuilt


@dataclass(frozen=True)
class DomainParts:
    scheme: str
    netloc: str


def normalize_domain_url(url: str) -> str:
    """
    Extract clean domain from any URL.
    Returns normalized base like https://domain.com or https://www.domain.com.
    Preserves www so that sites which live on www (e.g. www.isanet.org) are
    crawled on the correct host instead of the bare domain.
    """
    url = (url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url.lstrip("/")
    parsed = urlparse(url)
    netloc = (parsed.netloc or "").lower()
    if not netloc:
        return ""
    return f"https://{netloc}"
