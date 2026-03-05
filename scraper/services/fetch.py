from __future__ import annotations

import json
import logging
import subprocess
import sys

import requests

logger = logging.getLogger(__name__)


def fetch_html(url: str, *, headers: dict[str, str] | None = None, timeout: int = 30) -> str:
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error fetching {url}: {e}")
        raise ConnectionError(
            f"Failed to connect to {url}. Check your internet connection and DNS settings."
        ) from e
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout fetching {url} after {timeout}s")
        raise TimeoutError(f"Request to {url} timed out after {timeout} seconds") from e
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching {url}: {e}")
        raise


# ---------------------------------------------------------------------------
# Playwright is intentionally run in a child process to avoid event-loop
# conflicts between Playwright's async internals and Celery's solo pool on
# Windows (Python 3.12+). The child process is completely isolated: it has
# its own event loop, its own Playwright instance, and exits when done.
# ---------------------------------------------------------------------------

_PLAYWRIGHT_SCRIPT = """
import sys, json
from playwright.sync_api import sync_playwright, Error as PlaywrightError

def main():
    args              = json.loads(sys.argv[1])
    url               = args["url"]
    timeout_ms        = args["timeout_ms"]
    wait_until        = args["wait_until"]
    wait_for_selector = args.get("wait_for_selector") or ""
    headless          = bool(args.get("headless", True))
    user_agent        = args.get("user_agent") or ""
    extra_headers     = args.get("extra_headers") or {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )

            context_kwargs = {}
            if user_agent:
                context_kwargs["user_agent"] = user_agent
            if extra_headers:
                context_kwargs["extra_http_headers"] = extra_headers

            context = browser.new_context(**context_kwargs)
            page    = context.new_page()

            # Speed up heavy SPAs by blocking large/irrelevant resources.
            # This often prevents timeouts on pages like Meetup.
            def _route_handler(route):
                try:
                    rtype = route.request.resource_type
                    if rtype in ("image", "media", "font"):
                        route.abort()
                        return
                except Exception:
                    pass
                route.continue_()

            try:
                page.route("**/*", _route_handler)
            except Exception:
                # If routing isn't available for some reason, continue without it.
                pass

            page.set_default_timeout(timeout_ms)
            page.set_default_navigation_timeout(timeout_ms)

            try:
                page.goto(url, timeout=timeout_ms, wait_until=wait_until)
            except PlaywrightError as exc:
                # Navigation timeouts are common on SPAs; capture whatever rendered so far.
                msg = str(exc)
                if "Timeout" in msg or "timeout" in msg.lower():
                    print(json.dumps({
                        "ok": True,
                        "html": page.content(),
                        "warning": f"page.goto timed out; captured partial HTML"
                    }))
                    context.close()
                    browser.close()
                    return
                raise

            # For SPAs (e.g. Meetup) that keep firing XHR after domcontentloaded,
            # wait until a key element appears before capturing HTML.
            if wait_for_selector:
                try:
                    page.wait_for_selector(wait_for_selector, timeout=timeout_ms)
                except PlaywrightError:
                    # Log but continue — capture whatever rendered so far.
                    print(json.dumps({
                        "ok": True,
                        "html": page.content(),
                        "warning": f"wait_for_selector timed out; captured partial HTML"
                    }))
                    context.close()
                    browser.close()
                    return

            html = page.content()
            context.close()
            browser.close()
            print(json.dumps({"ok": True, "html": html}))

    except PlaywrightError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(1)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"Unexpected: {exc}"}))
        sys.exit(2)

main()
"""


def fetch_html_playwright(
    url: str,
    *,
    timeout_ms: int = 30_000,
    wait_until: str = "domcontentloaded",
    wait_for_selector: str | None = None,
    headless: bool = True,
    user_agent: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> str:
    """
    Fetch HTML using Playwright for JS-heavy pages.

    Playwright is spawned in an isolated subprocess to avoid event-loop
    conflicts with Celery's solo pool on Windows. The public interface and
    exception types are identical to the original sync implementation.

    Args:
        url:               Page to fetch.
        timeout_ms:        Playwright page.goto() timeout in milliseconds.
        wait_until:        Playwright navigation event to wait for.
                           Use "domcontentloaded" for SPAs (not "networkidle").
        wait_for_selector: Optional CSS selector to wait for after navigation,
                           ensuring dynamic content has rendered before capture.

    Raises
    ------
    ConnectionError  — DNS / network failure.
    TimeoutError     — Page-load or subprocess wall-clock timeout exceeded.
    RuntimeError     — Playwright not installed, subprocess crash, or other error.
    """
    wall_clock_timeout = timeout_ms / 1_000 + 15
    payload = json.dumps({
        "url": url,
        "timeout_ms": timeout_ms,
        "wait_until": wait_until,
        "wait_for_selector": wait_for_selector or "",
        "headless": bool(headless),
        "user_agent": user_agent or "",
        "extra_headers": extra_headers or {},
    })

    logger.debug("fetch_html_playwright: spawning subprocess for %s", url)

    try:
        result = subprocess.run(
            [sys.executable, "-c", _PLAYWRIGHT_SCRIPT, payload],
            capture_output=True,
            text=True,
            timeout=wall_clock_timeout,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"Page load timeout for {url} after {timeout_ms}ms. "
            "The page may be too slow or unresponsive."
        )

    stdout = result.stdout.strip()

    if not stdout:
        stderr_snippet = result.stderr.strip()[:500] if result.stderr else "(no stderr)"
        if "playwright" in stderr_snippet.lower() and "not" in stderr_snippet.lower():
            raise RuntimeError(
                "Playwright is not available. "
                "Ensure dependency is installed and browsers are installed."
            )
        raise RuntimeError(
            f"Playwright subprocess produced no output for {url}. "
            f"Exit code: {result.returncode}. Stderr: {stderr_snippet}"
        )

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"Playwright subprocess returned non-JSON output for {url}: {stdout[:300]}"
        )

    if data.get("warning"):
        logger.warning("fetch_html_playwright [%s]: %s", url, data["warning"])

    if not data.get("ok"):
        error_msg = data.get("error", "unknown")
        if "ERR_NAME_NOT_RESOLVED" in error_msg or "getaddrinfo failed" in error_msg:
            raise ConnectionError(
                f"DNS resolution failed for {url}. "
                "Check your internet connection and DNS settings."
            )
        if "Timeout" in error_msg or "timeout" in error_msg.lower():
            raise TimeoutError(
                f"Page load timeout for {url} after {timeout_ms}ms. "
                "The page may be too slow or unresponsive."
            )
        raise RuntimeError(f"Playwright error for {url}: {error_msg}")

    logger.debug("fetch_html_playwright: received %d chars for %s", len(data["html"]), url)
    return data["html"]