"""
SSRF guard: reject URLs that don't point at the public internet.

Used both at ScrapeTarget create/update time (fast, user-facing rejection) and
again at actual fetch time in scraper/services/fetch.py (the real enforcement
boundary — closes DNS-rebinding TOCTOU and covers pagination hrefs discovered
mid-scrape, which never go through target creation at all).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}


def _resolved_ip_is_unsafe(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True

    # IPv4-mapped IPv6 addresses (e.g. "::ffff:127.0.0.1") aren't flagged by
    # is_loopback/is_private on the IPv6Address itself — unwrap and check the
    # underlying IPv4 address, otherwise this is a known SSRF filter bypass.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    return (
        ip.is_private  # includes RFC1918 + IPv6 unique-local (fc00::/7)
        or ip.is_loopback
        or ip.is_link_local  # includes 169.254.0.0/16 — cloud metadata (169.254.169.254)
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def check_public_url(url: str) -> tuple[bool, str]:
    """
    Return (ok, reason). Rejects non-http(s) schemes, missing hosts, unresolvable
    hosts, and hosts that resolve to any private/loopback/link-local/reserved/
    multicast address on any of their DNS answers.
    """
    url = (url or "").strip()
    if not url:
        return False, "URL is empty."

    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "URL could not be parsed."

    if parsed.scheme not in ALLOWED_SCHEMES:
        return False, f"URL scheme {parsed.scheme!r} is not allowed (only http/https)."

    try:
        host = parsed.hostname
    except ValueError:
        return False, "URL host could not be parsed."
    if not host:
        return False, "URL has no host."

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return False, f"Could not resolve host {host!r}: {exc}"

    resolved_ips = {info[4][0] for info in infos}
    if not resolved_ips:
        return False, f"Host {host!r} did not resolve to any address."

    for ip_str in resolved_ips:
        if _resolved_ip_is_unsafe(ip_str):
            return False, f"Host {host!r} resolves to a non-public address ({ip_str})."

    return True, ""


def assert_public_url(url: str) -> None:
    """Raise ValueError with a human-readable reason if the URL isn't safe to fetch."""
    ok, reason = check_public_url(url)
    if not ok:
        raise ValueError(reason)
