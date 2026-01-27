from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PerfexConfig:
    base_url: str
    token: str
    timeout_seconds: int = 20


class PerfexClient:
    """
    Minimal Perfex REST API client.

    Assumes the REST API module is installed in Perfex and supports:
      - POST /api/leads
      - PUT  /api/leads/{id}
      - GET  /api/leads/{id} (optional)
    """

    def __init__(self, cfg: PerfexConfig, session: requests.Session | None = None):
        self.cfg = cfg
        self.session = session or requests.Session()

        base = (cfg.base_url or "").strip()
        if not base:
            raise ValueError("Perfex base_url is required")
        self.base_url = base.rstrip("/")

        if not (cfg.token or "").strip():
            raise ValueError("Perfex token is required")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.cfg.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def request(self, method: str, path: str, *, json_body: Any | None = None) -> Any:
        url = f"{self.base_url}{path}"
        resp = self.session.request(
            method=method.upper(),
            url=url,
            headers=self._headers(),
            json=json_body,
            timeout=self.cfg.timeout_seconds,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Perfex API error {resp.status_code}: {resp.text[:500]}"
            )
        # Some Perfex modules return plain text; prefer JSON when possible.
        try:
            return resp.json()
        except Exception:
            return resp.text

    def create_lead(self, payload: dict[str, Any]) -> Any:
        return self.request("POST", "/api/leads", json_body=payload)

    def update_lead(self, perfex_lead_id: str, payload: dict[str, Any]) -> Any:
        return self.request("PUT", f"/api/leads/{perfex_lead_id}", json_body=payload)

