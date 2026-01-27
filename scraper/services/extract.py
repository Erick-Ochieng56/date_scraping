from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup


def _text(el) -> str:
    if el is None:
        return ""
    return " ".join(el.get_text(" ", strip=True).split())


def extract_items(html: str, *, item_selector: str, fields: dict[str, Any]) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items = []
    for row in soup.select(item_selector):
        out: dict[str, Any] = {}
        for field_name, spec in (fields or {}).items():
            if isinstance(spec, str):
                out[field_name] = _text(row.select_one(spec))
                continue

            if isinstance(spec, dict):
                selector = spec.get("selector") or ""
                attr = spec.get("attr")
                regex = spec.get("regex")
                default = spec.get("default", "")

                el = row.select_one(selector) if selector else None
                if el is None:
                    out[field_name] = default
                    continue

                if attr:
                    value = el.get(attr, default) or default
                else:
                    value = _text(el) or default

                if regex:
                    m = re.search(regex, value)
                    value = m.group(1) if m and m.groups() else (m.group(0) if m else "")

                out[field_name] = value
                continue

            out[field_name] = str(spec)

        items.append(out)
    return items


def extract_next_page_url(html: str, *, next_page_selector: str) -> str | None:
    if not next_page_selector:
        return None
    soup = BeautifulSoup(html, "lxml")
    el = soup.select_one(next_page_selector)
    if not el:
        return None
    href = el.get("href")
    if not href:
        return None
    return str(href)

