# T3dmium network audit harness

T3dmium's core guarantee is that the browser generates **zero network
traffic that was not user-initiated**. This harness exists to prove it,
run after run, against real built binaries — not to assert it.

It launches a Chromium-family binary behind an intercepting proxy,
drives it through scripted user scenarios, records every request the
process makes, and **fails if a single request is not explained by a
scripted user action**.

## How it works

```
audit.py (orchestrator, exit code = verdict)
  ├─ capture.py ──► mitmdump -s capture.py     records every request,
  │                 (intercepting proxy)       stamped with the active
  │                        ▲                   scenario, into flows.json
  │                        │ --proxy-server
  ├─ scenarios/driver.py ──┴─► browser binary  fresh temp profile per
  │        │                                   scenario; scripted actions
  │        └─ writes active scenario name to a control file,
  │           which the capture addon re-reads per request
  └─ checker.py            pure-stdlib detection engine: default-deny
                           allowlist verdict over flows.json
```

- **Scenario attribution.** The driver and the proxy are separate
  processes. They share one small *control file*: the driver atomically
  writes the active scenario name before each scenario and the sentinel
  `__between__` after it; the capture addon reads the file for every
  request and stamps the flow. Sentinels have no allowlist section, so
  traffic in the gaps (or before the driver starts) is flagged
  automatically.
- **Default deny.** A request is allowed only if a rule in
  `allowlist.json` under the *flow's own scenario* matches its host
  (and optional path prefix). Missing scenario section, empty section,
  unknown scenario — all deny. Every rule must carry a `reason`
  explaining which user action generates the traffic.
- **Host globs are strict.** `*.example.com` matches subdomains only —
  never the apex (`example.com` needs its own rule) and never suffix
  lookalikes (`evilexample.com`). Any other use of `*` is rejected, so
  an allowlist typo fails the audit instead of silently allowing
  traffic.

### Scenarios

| scenario     | scripted user action                                     | allowed traffic          |
|--------------|----------------------------------------------------------|--------------------------|
| `idle`       | fresh profile, blank page, no input, 120 s               | **nothing**              |
| `navigation` | open `https://example.com/`                              | example.com + subdomains |
| `bookmarks`  | bookmark a page, rename it, delete it (chrome://bookmarks) | **nothing**            |
| `history`    | open chrome://history, scroll                            | **nothing**              |
| `downloads`  | click a same-origin download link on example.com         | example.com only         |
| `settings`   | open chrome://settings, flip privacy toggles back/forth  | **nothing**              |
| `search`     | submit a query to the chosen engine (DuckDuckGo)         | duckduckgo.com + subdomains |

## Running the self-test (no third-party packages, Python 3.9+)

The detection engine and its fixtures are pure standard library:

```sh
cd <repo root>
python3 -m unittest discover -s audit/tests -v
```

The fixtures give the checker something real to chew on:

- `fixtures/clean_run.json` — a well-behaved run; must yield zero
  violations.
- `fixtures/leaky_run.json` — the same run plus realistic leaks (update
  ping and variations fetch during idle, Safe Browsing during
  navigation, crash upload during settings, and a suffix-lookalike
  host during search); the checker must flag every one:

```sh
python3 audit/checker.py audit/fixtures/leaky_run.json   # exits 1, prints report
python3 audit/checker.py audit/fixtures/clean_run.json   # exits 0
```

## Running live against a built binary

Requires Python 3.10+ with the live-capture tools installed
(`python3 -m pip install -r audit/requirements.txt`; no
`playwright install` needed — the harness attaches to the audited
binary over CDP rather than downloading Playwright's own browsers).

```sh
python3 audit/audit.py --browser /path/to/T3dmium.app/Contents/MacOS/T3dmium
python3 audit/audit.py --browser ./out/Default/chrome --scenarios idle,navigation
python3 audit/audit.py --browser ./chrome --idle-seconds 30 --keep-output
```

Exit code **is** the verdict: `0` pass, `1` unexplained traffic (a
per-request report is printed), `2` the audit could not run.

Browser launch flags used (and why):

- `--user-data-dir=<fresh temp dir>` — throwaway profile per scenario,
  no state bleed.
- `--proxy-server=http://127.0.0.1:<port>` — route HTTP(S) through the
  capture proxy.
- `--disable-quic` — QUIC/HTTP3 is raw UDP and would bypass an HTTP
  proxy entirely; forcing TCP makes that traffic visible (see
  Limitations).
- `--ignore-certificate-errors` — the proxy terminates TLS with its own
  CA. Acceptable for auditing because we are verifying *which* requests
  happen, not their authenticity, and the profile is a throwaway. A
  stricter alternative is installing the mitmproxy CA into the test
  profile's trust store.
- `--no-first-run`, `--no-default-browser-check` — deterministic
  startup.

Deliberately **not** passed: `--disable-background-networking` or any
other flag that muzzles phone-home traffic. The audit must observe the
binary's real default behaviour.

Pieces can also be run standalone for debugging: `python3
audit/capture.py --port 8080` starts just the proxy; `python3
audit/scenarios/driver.py --browser ... --proxy-port 8080
--control-file ...` runs just the driver; `python3 audit/checker.py
flows.json` re-checks a saved capture.

## Limitations (honest ones)

This harness observes traffic *through an HTTP(S) proxy*. Traffic that
never reaches the proxy is invisible to it:

- **Raw UDP / QUIC.** An HTTP proxy only sees proxied TCP. We launch
  with `--disable-quic` to force HTTP over TCP, but that is a mitigation
  supplied by the very binary under audit — a hostile build could ignore
  the flag or open arbitrary UDP sockets.
- **OS-level DNS lookups.** For proxied requests the proxy does the
  resolving, but any name resolution the browser or OS performs directly
  (prefetching, system services on the same machine) bypasses the proxy
  and is not captured.
- **Proxy bypass in general.** `--proxy-server` is a request, not a
  cage. Code that ignores proxy settings and opens direct sockets is
  invisible here.
- **Attribution at boundaries.** Scenario stamping uses wall-clock
  ordering via the control file; a request in flight exactly when a
  scenario ends can be stamped with the neighbouring sentinel. That
  direction of error is safe (sentinels deny everything), but be aware
  of it when reading reports.

**Future hardening** — turning "we saw nothing" into "nothing could get
out": run the browser inside an isolated network namespace (or behind a
host firewall, e.g. a PF rule set on macOS) that drops *all* egress
except the proxy port, and log the drops. At that point QUIC, direct
sockets and stray DNS are blocked and evidenced, and the proxy capture
becomes the complete record rather than the best available one. Until
then, treat a PASS from this harness as strong evidence, not a formal
guarantee.

## Files

- `audit.py` — orchestrator CLI; exit code = verdict
- `checker.py` — pure-stdlib detection engine (data model + verdict)
- `allowlist.json` — per-scenario allow rules, each with a mandatory reason
- `capture.py` — mitmproxy addon + proxy runner
- `scenarios/driver.py` — scripted user scenarios (Playwright-over-CDP
  where page interaction is needed, plain subprocess otherwise)
- `fixtures/` — recorded-style flows for the self-test
- `tests/test_checker.py` — stdlib unittest suite
- `requirements.txt` — live-capture-only dependencies
