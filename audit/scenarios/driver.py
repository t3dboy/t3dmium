#!/usr/bin/env python3
"""T3dmium network audit — scenario driver.

Drives a Chromium-family binary through scripted "user" scenarios while
the capture proxy records every request the browser makes.  Before each
scenario the driver announces its name through the shared control file
(see capture.py); the capture addon stamps every flow with whatever
scenario is active at that moment.  Between scenarios the sentinel
``__between__`` is announced — it has no allowlist section, so any
traffic in the gaps is flagged by default deny.

Two driving modes:

* Playwright-over-CDP (optional, guarded import).  Needed for the
  scenarios that interact with pages or WebUI: bookmarks, history,
  downloads, settings.  The browser is launched by *this* module with
  ``--remote-debugging-port`` and Playwright attaches to the running
  process, so all audit launch flags stay under our control.

* Plain subprocess.  Scenarios that need no page interaction (idle,
  navigation, search) just launch the binary with a URL argument and
  wait.  These run on a machine with no third-party packages at all.

Every scenario gets a FRESH temporary profile (``--user-data-dir``) so
no state bleeds between scenarios.
"""

import argparse
import contextlib
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_AUDIT_DIR = Path(__file__).resolve().parent.parent
if str(_AUDIT_DIR) not in sys.path:
    sys.path.insert(0, str(_AUDIT_DIR))

import capture  # noqa: E402  (shared control-file mechanism)

#: Announced between scenarios; has no allowlist section => default deny.
BETWEEN = "__between__"

#: Scripted destinations.  These are the ONLY hosts the allowlist
#: excuses, and only within their own scenarios.
NAVIGATION_URL = "https://example.com/"
SEARCH_URL = "https://duckduckgo.com/?q=t3dmium+privacy+browser"
#: The downloads scenario navigates to example.com and clicks a
#: same-origin download link, so the scripted download host is also
#: example.com (see allowlist.json).
DOWNLOAD_PAGE_URL = "https://example.com/"
DOWNLOAD_HREF = "/index.html"

#: Scenarios that need Playwright to interact with pages/WebUI.
PLAYWRIGHT_SCENARIOS = ("bookmarks", "history", "downloads", "settings")


class ScenarioUnavailable(RuntimeError):
    pass


def _require_playwright():
    """Import Playwright, or explain exactly what is missing."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ScenarioUnavailable(
            "Playwright is not installed, but it is required for the "
            "page-interaction scenarios ({}). Install it with: "
            "python3 -m pip install playwright  "
            "(no 'playwright install' needed — the audit attaches to "
            "the audited binary over CDP, it does not download its own "
            "browsers). The checker self-test does NOT need Playwright."
            .format(", ".join(PLAYWRIGHT_SCENARIOS)))
    return sync_playwright


def _pick_free_port():
    import socket
    with contextlib.closing(socket.socket()) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ---------------------------------------------------------------------------
# browser process management
# ---------------------------------------------------------------------------

def browser_command(browser, proxy_port, profile_dir, cdp_port=None,
                    url=None):
    """Audit launch flags for a Chromium-family binary.

    --user-data-dir             fresh throwaway profile per scenario
    --proxy-server              route all HTTP(S) through the capture proxy
    --disable-quic              QUIC is raw UDP and would bypass an HTTP
                                proxy entirely; force TCP so we see it
    --ignore-certificate-errors the capture proxy terminates TLS with its
                                own CA; acceptable here because the audit
                                verifies WHICH requests happen, not their
                                authenticity, and the profile is throwaway
                                (see README: Limitations)
    --no-first-run              suppress first-run UI so scenarios are
                                deterministic

    Deliberately NOT passed: --disable-background-networking or any other
    flag that suppresses phone-home traffic.  The audit must observe the
    binary's real default behaviour, not a muzzled version of it.
    """
    cmd = [
        str(browser),
        "--user-data-dir={}".format(profile_dir),
        "--proxy-server=http://127.0.0.1:{}".format(proxy_port),
        "--disable-quic",
        "--ignore-certificate-errors",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if cdp_port is not None:
        cmd.append("--remote-debugging-port={}".format(cdp_port))
    if url is not None:
        cmd.append(url)
    return cmd


@contextlib.contextmanager
def browser_process(ctx, url=None, cdp=False):
    """Launch the audited binary with a fresh profile; clean up after."""
    profile_dir = tempfile.mkdtemp(prefix="t3dmium-profile-",
                                   dir=str(ctx.workdir))
    cdp_port = _pick_free_port() if cdp else None
    cmd = browser_command(ctx.browser, ctx.proxy_port, profile_dir,
                          cdp_port=cdp_port, url=url)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    try:
        if cdp_port is not None:
            capture.wait_for_port(cdp_port, proc=proc)
        yield proc, cdp_port
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        shutil.rmtree(profile_dir, ignore_errors=True)


@contextlib.contextmanager
def cdp_page(ctx, url="about:blank"):
    """Launch the audited binary and attach Playwright over CDP."""
    sync_playwright = _require_playwright()
    with browser_process(ctx, cdp=True) as (_, cdp_port):
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(
                "http://127.0.0.1:{}".format(cdp_port))
            context = (browser.contexts[0] if browser.contexts
                       else browser.new_context())
            page = context.pages[0] if context.pages else context.new_page()
            if url != "about:blank":
                page.goto(url, wait_until="load")
            try:
                yield page
            finally:
                browser.close()  # detach; process teardown is ours


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------

def scenario_idle(ctx):
    """Fresh profile, blank page, no interaction.  The core guarantee:
    an idle browser must be completely silent (allowlist: nothing)."""
    with browser_process(ctx, url="about:blank"):
        time.sleep(ctx.idle_seconds)


def scenario_navigation(ctx):
    """User opens example.com."""
    with browser_process(ctx, url=NAVIGATION_URL):
        time.sleep(ctx.settle_seconds)


def scenario_search(ctx):
    """User submits a query to the chosen search engine (DuckDuckGo)."""
    with browser_process(ctx, url=SEARCH_URL):
        time.sleep(ctx.settle_seconds)


def scenario_bookmarks(ctx):
    """Bookmark CRUD via keyboard shortcut + the chrome://bookmarks
    WebUI.  Must produce ZERO network traffic.

    WebUI selectors are best-effort against current Chromium; Playwright
    pierces open shadow roots with plain CSS selectors.  A selector miss
    aborts the scenario loudly rather than passing silently.
    """
    accel = "Meta" if sys.platform == "darwin" else "Control"
    with cdp_page(ctx) as page:
        # Create: bookmark a chrome:// page (no network involved).
        page.goto("chrome://version/", wait_until="load")
        page.keyboard.press("{}+D".format(accel))
        page.wait_for_timeout(500)
        page.keyboard.press("Enter")  # confirm the star dialog
        page.wait_for_timeout(500)
        # Read + Update + Delete via the bookmarks manager WebUI.
        page.goto("chrome://bookmarks/", wait_until="load")
        page.wait_for_timeout(1000)
        item_menu = page.locator("bookmarks-item cr-icon-button").first
        item_menu.click()
        page.locator("cr-action-menu button", has_text="Edit").click()
        name_input = page.locator("bookmarks-edit-dialog cr-input").first
        name_input.fill("t3dmium audit bookmark (renamed)")
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)
        item_menu.click()
        page.locator("cr-action-menu button", has_text="Delete").click()
        page.wait_for_timeout(ctx.settle_seconds * 1000)


def scenario_history(ctx):
    """User opens chrome://history and scrolls through it.  Must be
    silent (history is local data)."""
    with cdp_page(ctx) as page:
        page.goto("chrome://history/", wait_until="load")
        page.wait_for_timeout(1000)
        for _ in range(5):
            page.mouse.wheel(0, 600)
            page.wait_for_timeout(300)
        page.wait_for_timeout(ctx.settle_seconds * 1000)


def scenario_downloads(ctx):
    """User downloads a small file from the scripted host by clicking a
    same-origin download link on example.com."""
    with cdp_page(ctx, url=DOWNLOAD_PAGE_URL) as page:
        with page.expect_download(timeout=30000) as download_info:
            page.evaluate(
                "href => {"
                "  const a = document.createElement('a');"
                "  a.href = href;"
                "  a.download = 't3dmium-audit-sample.html';"
                "  document.body.appendChild(a);"
                "  a.click();"
                "}",
                DOWNLOAD_HREF)
        download = download_info.value
        download.save_as(str(Path(ctx.workdir) /
                             "t3dmium-audit-sample.html"))
        page.wait_for_timeout(ctx.settle_seconds * 1000)


def scenario_settings(ctx):
    """User opens chrome://settings and flips a few privacy toggles
    back and forth.  Must be silent (settings are local)."""
    with cdp_page(ctx) as page:
        for section in ("chrome://settings/", "chrome://settings/privacy"):
            page.goto(section, wait_until="load")
            page.wait_for_timeout(1000)
        toggles = page.locator("settings-toggle-button")
        count = min(toggles.count(), 4)
        for i in range(count):
            toggle = toggles.nth(i)
            if not toggle.is_visible():
                continue
            toggle.click()           # flip ...
            page.wait_for_timeout(300)
            toggle.click()           # ... and restore
            page.wait_for_timeout(300)
        page.wait_for_timeout(ctx.settle_seconds * 1000)


#: Registry, in canonical execution order.
SCENARIOS = {
    "idle": scenario_idle,
    "navigation": scenario_navigation,
    "bookmarks": scenario_bookmarks,
    "history": scenario_history,
    "downloads": scenario_downloads,
    "settings": scenario_settings,
    "search": scenario_search,
}


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

class ScenarioContext:
    def __init__(self, browser, proxy_port, control_file, workdir,
                 idle_seconds=120, settle_seconds=5):
        self.browser = browser
        self.proxy_port = proxy_port
        self.control_file = control_file
        self.workdir = workdir
        self.idle_seconds = idle_seconds
        self.settle_seconds = settle_seconds


def run_scenarios(ctx, names):
    """Run the named scenarios in order, announcing each one to the
    capture layer through the control file."""
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        raise ScenarioUnavailable("unknown scenario(s): {} (available: {})"
                                  .format(", ".join(unknown),
                                          ", ".join(SCENARIOS)))
    needs_playwright = [n for n in names if n in PLAYWRIGHT_SCENARIOS]
    if needs_playwright:
        _require_playwright()  # fail fast, before any browser launches
    if not Path(ctx.browser).exists():
        raise ScenarioUnavailable(
            "browser binary not found: {}".format(ctx.browser))

    capture.announce_scenario(ctx.control_file, BETWEEN)
    for name in names:
        print("[driver] scenario '{}' starting".format(name), flush=True)
        capture.announce_scenario(ctx.control_file, name)
        try:
            SCENARIOS[name](ctx)
        finally:
            capture.announce_scenario(ctx.control_file, BETWEEN)
        print("[driver] scenario '{}' done".format(name), flush=True)
        time.sleep(1.0)  # let straggler requests land in the gap


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Drive a Chromium-family binary through the audit "
                    "scenarios (normally invoked by audit.py).")
    parser.add_argument("--browser", required=True,
                        help="path to the Chromium-family binary under audit")
    parser.add_argument("--proxy-port", type=int, required=True,
                        help="port of the running capture proxy")
    parser.add_argument("--control-file", required=True,
                        help="scenario control file shared with capture.py")
    parser.add_argument("--scenarios",
                        default=",".join(SCENARIOS),
                        help="comma-separated list (default: all)")
    parser.add_argument("--idle-seconds", type=float, default=120)
    parser.add_argument("--settle-seconds", type=float, default=5)
    parser.add_argument("--workdir", default=None,
                        help="scratch dir for profiles/downloads "
                             "(default: a new temp dir)")
    args = parser.parse_args(argv)

    workdir = args.workdir or tempfile.mkdtemp(prefix="t3dmium-driver-")
    ctx = ScenarioContext(browser=args.browser, proxy_port=args.proxy_port,
                          control_file=args.control_file, workdir=workdir,
                          idle_seconds=args.idle_seconds,
                          settle_seconds=args.settle_seconds)
    names = [n.strip() for n in args.scenarios.split(",") if n.strip()]
    try:
        run_scenarios(ctx, names)
    except (ScenarioUnavailable, capture.CaptureUnavailable) as exc:
        print("driver error: {}".format(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
