#!/usr/bin/env python3
"""T3dmium network audit — top-level orchestrator.

Usage:

    python3 audit/audit.py --browser /path/to/T3dmium.app/Contents/MacOS/T3dmium
    python3 audit/audit.py --browser ./chrome --scenarios idle,navigation
    python3 audit/audit.py --browser ./chrome --idle-seconds 30 --keep-output

Pipeline:

  1. start mitmdump with the capture addon (audit/capture.py) on a free
     local port
  2. run the scenario driver (audit/scenarios/driver.py), which launches
     the browser behind the proxy — fresh temp profile, --disable-quic,
     --ignore-certificate-errors (see capture/driver docstrings and the
     README for why each flag is there)
  3. stop the proxy, load the captured flows, and hand them to the
     detection engine (audit/checker.py)

Exit code IS the verdict: 0 = every request explained by a scripted
user action, 1 = at least one unexplained request (report printed),
2 = the audit itself could not run (missing tools, malformed input).

Only steps 1-2 need third-party tools (mitmproxy, and Playwright for
the page-interaction scenarios).  Step 3 and the self-test are pure
standard library.
"""

import argparse
import contextlib
import socket
import sys
import tempfile
from pathlib import Path

_AUDIT_DIR = Path(__file__).resolve().parent
if str(_AUDIT_DIR) not in sys.path:
    sys.path.insert(0, str(_AUDIT_DIR))

import capture           # noqa: E402
import checker           # noqa: E402
from scenarios import driver  # noqa: E402


def _pick_free_port():
    with contextlib.closing(socket.socket()) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Prove that a T3dmium binary generates zero network "
                    "traffic that was not user-initiated.")
    parser.add_argument("--browser", required=True,
                        help="path to the Chromium-family binary under audit")
    parser.add_argument("--scenarios",
                        default=",".join(driver.SCENARIOS),
                        help="comma-separated subset of: {} "
                             "(default: all)".format(
                                 ",".join(driver.SCENARIOS)))
    parser.add_argument("--port", type=int, default=0,
                        help="proxy listen port (default: pick a free one)")
    parser.add_argument("--idle-seconds", type=float, default=120,
                        help="idle-scenario duration (default: %(default)s)")
    parser.add_argument("--settle-seconds", type=float, default=5,
                        help="post-action wait in each scenario "
                             "(default: %(default)s)")
    parser.add_argument("--allowlist",
                        default=str(checker.DEFAULT_ALLOWLIST),
                        help="allowlist JSON (default: %(default)s)")
    parser.add_argument("--output", default=None,
                        help="directory for flows.json and scratch files "
                             "(default: a new temp dir)")
    parser.add_argument("--keep-output", action="store_true",
                        help="always print the output dir path and keep it")
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.scenarios.split(",") if n.strip()]
    port = args.port or _pick_free_port()

    if args.output:
        workdir = Path(args.output)
        workdir.mkdir(parents=True, exist_ok=True)
    else:
        workdir = Path(tempfile.mkdtemp(prefix="t3dmium-audit-"))
    control_file = workdir / "scenario.ctl"
    flows_file = workdir / "flows.json"

    # Fail fast on a broken allowlist before launching anything.
    try:
        allowlist = checker.load_allowlist(args.allowlist)
    except checker.AuditError as exc:
        print("audit error: {}".format(exc), file=sys.stderr)
        return 2

    capture.announce_scenario(control_file, capture.UNATTRIBUTED)
    print("[audit] capture proxy on 127.0.0.1:{} — output in {}".format(
        port, workdir), flush=True)
    try:
        proxy = capture.start_mitmdump(port, control_file, flows_file)
    except capture.CaptureUnavailable as exc:
        print("audit error: {}".format(exc), file=sys.stderr)
        return 2

    ctx = driver.ScenarioContext(
        browser=args.browser, proxy_port=port, control_file=control_file,
        workdir=str(workdir), idle_seconds=args.idle_seconds,
        settle_seconds=args.settle_seconds)
    try:
        driver.run_scenarios(ctx, names)
    except (driver.ScenarioUnavailable,
            capture.CaptureUnavailable) as exc:
        print("audit error: {}".format(exc), file=sys.stderr)
        return 2
    finally:
        capture.stop_mitmdump(proxy)

    try:
        flows = capture.load_flows(flows_file)
        violations = checker.check_flows(flows, allowlist)
    except (OSError, ValueError, checker.AuditError) as exc:
        print("audit error: could not evaluate captured flows: {}".format(
            exc), file=sys.stderr)
        return 2

    print(checker.format_report(violations, len(flows)))
    if args.keep_output:
        print("[audit] flows kept at {}".format(flows_file))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
