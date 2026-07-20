from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
from urllib.parse import urljoin

import requests

from scraper.services.url_safety import check_public_url

logger = logging.getLogger(__name__)

_MAX_REDIRECTS = 5


def fetch_html(url: str, *, headers: dict[str, str] | None = None, timeout: int = 30) -> str:
    """
    Fetch a page's HTML over plain HTTP(S).

    SSRF guard: every URL actually requested — including each redirect hop —
    is checked against check_public_url() before the request is made. This is
    the real enforcement point (not just target-creation-time validation):
    it also covers pagination URLs discovered mid-scrape (extracted from a
    target site's own HTML via next_page_selector) and closes DNS-rebinding,
    where a hostname resolves to a public IP at validation time but an
    internal one moments later at request time.
    """
    current_url = url
    redirects_followed = 0

    while True:
        ok, reason = check_public_url(current_url)
        if not ok:
            logger.error("Refusing to fetch %s: %s", current_url, reason)
            raise ValueError(f"Refusing to fetch {current_url}: {reason}")

        try:
            resp = requests.get(
                current_url, headers=headers, timeout=timeout, allow_redirects=False
            )
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error fetching {current_url}: {e}")
            raise ConnectionError(
                f"Failed to connect to {current_url}. Check your internet connection and DNS settings."
            ) from e
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout fetching {current_url} after {timeout}s")
            raise TimeoutError(f"Request to {current_url} timed out after {timeout} seconds") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching {current_url}: {e}")
            raise

        if resp.is_redirect or resp.is_permanent_redirect:
            location = resp.headers.get("Location")
            if not location:
                resp.raise_for_status()
                return resp.text
            redirects_followed += 1
            if redirects_followed > _MAX_REDIRECTS:
                raise requests.exceptions.TooManyRedirects(
                    f"Exceeded {_MAX_REDIRECTS} redirects fetching {url}"
                )
            current_url = urljoin(current_url, location)
            continue

        resp.raise_for_status()
        return resp.text


# ---------------------------------------------------------------------------
# Playwright is intentionally run in a child process to avoid event-loop
# conflicts between Playwright's async internals and Celery's solo pool on
# Windows (Python 3.12+). The child process is completely isolated: it has
# its own event loop, its own Playwright instance, and exits when done.
# ---------------------------------------------------------------------------


def _spawn_playwright_subprocess(args: list[str]) -> subprocess.Popen:
    """
    Spawn the subprocess in its own process group/session so the whole tree
    (this process, Playwright's Node driver, and the Chromium process it
    launches) can be killed together on timeout — see _kill_process_tree().
    """
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True  # POSIX: setsid(), own process group
    return subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **kwargs,
    )


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """
    Kill the subprocess AND any children it spawned.

    Plain Popen.kill() (what subprocess.run() calls internally on
    TimeoutExpired) only terminates the immediate `python -c ...` process —
    Playwright's Node driver and the Chromium process it launches are left
    running. Windows has no automatic child-process-tree cleanup, so a timed-
    out scrape used to leave orphaned Node/Chromium processes on the worker
    host indefinitely; repeated timeouts accumulate zombies.
    """
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            logger.warning(
                "taskkill failed for playwright subprocess pid=%s", proc.pid, exc_info=True
            )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            logger.warning(
                "killpg failed for playwright subprocess pid=%s", proc.pid, exc_info=True
            )
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.communicate(timeout=5)  # reap the process, drain any remaining output
    except Exception:
        pass

_PLAYWRIGHT_SCRIPT = """
import ipaddress, socket, sys, json
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, Error as PlaywrightError

# Inlined (not imported) so this subprocess has zero dependency on the parent
# project's PYTHONPATH/Django setup — self-contained SSRF guard, mirrors
# scraper.services.url_safety. Applied to every navigation the page makes
# (not just the initial URL, which the parent process already validated) so a
# malicious/compromised target site can't redirect the browser to an internal
# address mid-navigation.
def _is_unsafe_ip(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )

def _is_unsafe_navigation_url(url):
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if parsed.scheme not in ("http", "https") or not host:
            return True
        infos = socket.getaddrinfo(host, None)
        return any(_is_unsafe_ip(info[4][0]) for info in infos)
    except Exception:
        return True

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
                    if rtype == "document" and _is_unsafe_navigation_url(route.request.url):
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
    ValueError       — URL fails the SSRF guard (non-public host).
    ConnectionError  — DNS / network failure.
    TimeoutError     — Page-load or subprocess wall-clock timeout exceeded.
    RuntimeError     — Playwright not installed, subprocess crash, or other error.
    """
    ok, reason = check_public_url(url)
    if not ok:
        logger.error("Refusing to fetch %s: %s", url, reason)
        raise ValueError(f"Refusing to fetch {url}: {reason}")

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

    proc = _spawn_playwright_subprocess([sys.executable, "-c", _PLAYWRIGHT_SCRIPT, payload])
    try:
        raw_stdout, raw_stderr = proc.communicate(timeout=wall_clock_timeout)
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        raise TimeoutError(
            f"Page load timeout for {url} after {timeout_ms}ms. "
            "The page may be too slow or unresponsive."
        )

    stdout = (raw_stdout or "").strip()

    if not stdout:
        stderr_snippet = (raw_stderr or "").strip()[:500] if raw_stderr else "(no stderr)"
        if "playwright" in stderr_snippet.lower() and "not" in stderr_snippet.lower():
            raise RuntimeError(
                "Playwright is not available. "
                "Ensure dependency is installed and browsers are installed."
            )
        raise RuntimeError(
            f"Playwright subprocess produced no output for {url}. "
            f"Exit code: {proc.returncode}. Stderr: {stderr_snippet}"
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