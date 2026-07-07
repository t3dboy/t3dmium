#!/usr/bin/env python3
"""T3dmium network audit — mitmproxy capture addon + runner.

Two roles in one file:

1. mitmproxy ADDON.  When mitmdump loads this file with ``-s capture.py``
   it registers ``CaptureAddon``, which records every HTTP(S) request as
   a flow dict in the checker's format and continuously dumps the list
   to a flows JSON file.  The addon itself imports nothing from
   mitmproxy — it only reads attributes of the flow objects mitmdump
   hands it — so this module stays importable on a machine without
   mitmproxy installed (e.g. to run the self-test).

2. RUNNER helpers.  ``start_mitmdump()`` spawns the ``mitmdump``
   subprocess with this file as its addon script and waits for the
   proxy port to accept connections.  It needs only the ``mitmdump``
   binary on PATH (``pip install mitmproxy``); a clear error is raised
   when it is missing.

Scenario attribution — the control file
---------------------------------------
The scenario driver and the capture addon run in different processes,
so they share state through a small CONTROL FILE (the simplest
mechanism that survives process boundaries and crashes):

  * the driver atomically writes the active scenario name (a single
    line) to the control file before each scenario starts, and writes
    the sentinel ``__between__`` after it ends;
  * the addon re-reads that file for every captured request and stamps
    the flow with its content.

Both paths are passed via environment variables, which the mitmdump
subprocess inherits:

  T3DMIUM_SCENARIO_FILE  control file the driver writes to
  T3DMIUM_FLOWS_FILE     where the addon dumps captured flows (JSON)

Any request captured while no scenario is active is stamped with a
sentinel scenario name.  Sentinels have no allowlist section, so the
checker's default-deny stance flags such traffic automatically.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCENARIO_FILE_ENV = "T3DMIUM_SCENARIO_FILE"
FLOWS_FILE_ENV = "T3DMIUM_FLOWS_FILE"

#: Stamped on flows captured before the driver announced any scenario.
UNATTRIBUTED = "__unattributed__"


def write_atomic(path, text):
    """Write *text* to *path* atomically (write temp file, then rename)."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent),
                               prefix=path.name + ".tmp.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def announce_scenario(control_file, scenario):
    """Publish the currently-active scenario name to the control file."""
    write_atomic(control_file, scenario + "\n")


def read_scenario(control_file):
    """Read the active scenario from the control file (sentinel if unset)."""
    try:
        text = Path(control_file).read_text(encoding="utf-8").strip()
    except OSError:
        return UNATTRIBUTED
    return text or UNATTRIBUTED


# ---------------------------------------------------------------------------
# mitmproxy addon (no mitmproxy imports needed — duck-typed flow objects)
# ---------------------------------------------------------------------------

class CaptureAddon:
    """Records every request, stamped with the active scenario."""

    def __init__(self, scenario_file=None, flows_file=None):
        self.scenario_file = Path(
            scenario_file or os.environ.get(SCENARIO_FILE_ENV,
                                            "t3dmium_scenario.txt"))
        self.flows_file = Path(
            flows_file or os.environ.get(FLOWS_FILE_ENV, "flows.json"))
        self.flows = []

    # -- mitmproxy hooks --------------------------------------------------

    def running(self):
        # Proxy is up: write an empty (but valid) dump so a zero-traffic
        # run still yields a readable flows file.  Done here rather than
        # in __init__ so that merely importing this module (as audit.py
        # does) never touches the filesystem.
        self._dump()

    def request(self, flow):
        record = {
            "url": flow.request.pretty_url,
            "method": flow.request.method,
            "host": flow.request.pretty_host,
            "timestamp": flow.request.timestamp_start or time.time(),
            "scenario": read_scenario(self.scenario_file),
        }
        self.flows.append(record)
        # Dump after every request: audit traffic volumes are tiny and
        # this way a crash or hard kill never loses evidence.
        self._dump()

    def done(self):
        self._dump()

    # -- persistence -------------------------------------------------------

    def _dump(self):
        write_atomic(self.flows_file,
                     json.dumps({"flows": self.flows}, indent=2) + "\n")


# Registered only when mitmdump loads this file as an addon script.
addons = [CaptureAddon()]


# ---------------------------------------------------------------------------
# runner helpers (used by audit.py; only need the mitmdump binary)
# ---------------------------------------------------------------------------

class CaptureUnavailable(RuntimeError):
    pass


def _find_mitmdump():
    mitmdump = shutil.which("mitmdump")
    if not mitmdump:
        raise CaptureUnavailable(
            "mitmdump not found on PATH. Live capture needs mitmproxy: "
            "python3 -m pip install mitmproxy  (see audit/requirements.txt; "
            "the checker self-test does NOT need it)")
    return mitmdump


def wait_for_port(port, proc=None, host="127.0.0.1", timeout=20.0):
    """Block until *port* accepts TCP connections (or raise)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            raise CaptureUnavailable(
                "mitmdump exited early with status {}".format(
                    proc.returncode))
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError:
            time.sleep(0.2)
    raise CaptureUnavailable(
        "proxy port {}:{} did not open within {}s".format(
            host, port, timeout))


def start_mitmdump(listen_port, scenario_file, flows_file, quiet=True):
    """Spawn mitmdump with this file as the capture addon.

    Returns the subprocess.Popen handle once the proxy port is open.
    Equivalent manual invocation (documented for debugging):

        T3DMIUM_SCENARIO_FILE=... T3DMIUM_FLOWS_FILE=... \\
            mitmdump -q --listen-host 127.0.0.1 --listen-port <port> \\
            -s audit/capture.py
    """
    mitmdump = _find_mitmdump()
    env = os.environ.copy()
    env[SCENARIO_FILE_ENV] = str(scenario_file)
    env[FLOWS_FILE_ENV] = str(flows_file)
    cmd = [mitmdump,
           "--listen-host", "127.0.0.1",
           "--listen-port", str(listen_port),
           "--set", "stream_large_bodies=1m",
           "-s", str(Path(__file__).resolve())]
    if quiet:
        cmd.insert(1, "-q")
    proc = subprocess.Popen(cmd, env=env)
    try:
        wait_for_port(listen_port, proc=proc)
    except BaseException:
        stop_mitmdump(proc)
        raise
    return proc


def stop_mitmdump(proc, timeout=10.0):
    """Terminate mitmdump gracefully so the addon's done() hook runs."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def load_flows(flows_file):
    """Read the flows the addon dumped (checker-compatible list)."""
    with open(flows_file, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["flows"] if isinstance(data, dict) else data


# ---------------------------------------------------------------------------
# standalone CLI: run a capture proxy by hand
# ---------------------------------------------------------------------------

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(
        description="Run a standalone capture proxy (mitmdump + addon). "
                    "Point a browser at it, then Ctrl+C to stop and keep "
                    "the flows file.")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--scenario-file", default="t3dmium_scenario.txt")
    parser.add_argument("--flows-file", default="flows.json")
    args = parser.parse_args(argv)

    Path(args.scenario_file).parent.mkdir(parents=True, exist_ok=True)
    if not Path(args.scenario_file).exists():
        announce_scenario(args.scenario_file, UNATTRIBUTED)
    try:
        proc = start_mitmdump(args.port, args.scenario_file, args.flows_file,
                              quiet=False)
    except CaptureUnavailable as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    print("capture proxy on 127.0.0.1:{} — flows -> {}".format(
        args.port, args.flows_file))
    try:
        proc.wait()
    except KeyboardInterrupt:
        stop_mitmdump(proc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
