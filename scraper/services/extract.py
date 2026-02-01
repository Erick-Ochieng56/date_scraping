from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup


def _text(el) -> str:
    if el is None:
        return ""
    return " ".join(el.get_text(" ", strip=True).split())


def _parse_selector_with_attr(selector_str: str) -> tuple[str, str] | None:
    """
    Parse a selector string that may contain @attr syntax.
    Returns (css_selector, attr_name) or None if invalid.
    Handles: "selector@attr", "selector1, selector2@attr"
    """
    if "@" not in selector_str:
        return None
    
    # Find the last @ that's not inside quotes or brackets
    # This handles cases like: "a[href='test@value']@href"
    last_at = selector_str.rfind("@")
    if last_at == -1:
        return None
    
    css_part = selector_str[:last_at].strip()
    attr_part = selector_str[last_at + 1:].strip()
    
    if not css_part or not attr_part:
        return None
    
    return (css_part, attr_part)


def _split_selector_list(selector_str: str) -> list[str]:
    """
    Split a comma-separated list of CSS selectors, handling commas inside brackets/quotes.
    Returns list of individual selector strings.
    """
    if "," not in selector_str:
        return [selector_str.strip()]
    
    parts = []
    current = ""
    depth = 0
    in_quotes = False
    quote_char = None
    
    for char in selector_str:
        if char in ("'", '"') and (depth == 0 or not in_quotes):
            if not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char:
                in_quotes = False
                quote_char = None
            current += char
        elif char in "([{" and not in_quotes:
            depth += 1
            current += char
        elif char in ")]}" and not in_quotes:
            depth -= 1
            current += char
        elif char == "," and depth == 0 and not in_quotes:
            if current.strip():
                parts.append(current.strip())
            current = ""
        else:
            current += char
    
    if current.strip():
        parts.append(current.strip())
    
    return parts if parts else [selector_str.strip()]


def extract_items(html: str, *, item_selector: str, fields: dict[str, Any]) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items = []
    for row in soup.select(item_selector):
        out: dict[str, Any] = {}
        for field_name, spec in (fields or {}).items():
            if isinstance(spec, str):
                # Handle @attr syntax: "selector@attr" or "selector1, selector2@attr"
                if "@" in spec:
                    value = ""
                    # Split by comma first (handling commas in brackets/quotes)
                    selector_parts = _split_selector_list(spec)
                    
                    # Try each selector part
                    for part in selector_parts:
                        parsed = _parse_selector_with_attr(part)
                        if parsed:
                            css_sel, attr_name = parsed
                            el = row.select_one(css_sel)
                            if el:
                                value = el.get(attr_name, "") or ""
                                if value:
                                    break
                    
                    out[field_name] = value
                else:
                    # Plain CSS selector, get text
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