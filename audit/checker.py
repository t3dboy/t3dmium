#!/usr/bin/env python3
"""T3dmium network audit — detection engine.

Pure standard library (Python 3.9+). No third-party imports, ever.

The engine answers exactly one question: for every network request the
browser made ("flow"), is there a scripted user action that explains it?

Data model
----------
A *flow* is a dict with these mandatory keys:

    url        full request URL, e.g. "https://example.com/index.html"
    method     HTTP method, e.g. "GET"
    host       destination hostname (no port), e.g. "example.com"
    timestamp  unix time (int or float) when the request started
    scenario   name of the scenario that was active when it was captured

The *allowlist* (see allowlist.json) maps scenario names to lists of
rules.  A rule is a dict:

    host         hostname pattern; either an exact hostname or a
                 wildcard of the form "*.example.com" which matches
                 SUBDOMAINS ONLY (never the apex, never suffix
                 lookalikes such as "evilexample.com")
    path_prefix  optional URL-path prefix (segment-aware; "/dl" does
                 not match "/dl-evil")
    reason       mandatory human explanation of why this traffic is
                 user-initiated

Verdict logic (default deny)
----------------------------
A flow is ALLOWED only if some rule in the allowlist section for the
flow's own scenario matches both its host and (if the rule has one) its
path prefix.  Everything else is a violation:

  * scenario not present in the allowlist  -> violation
  * scenario present but with an empty list -> violation
  * host or path not matched by any rule    -> violation

There is deliberately no "global" section and no fallback: an empty or
missing allowlist section means nothing is allowed for that scenario.
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

REQUIRED_FLOW_KEYS = ("url", "method", "host", "timestamp", "scenario")

DEFAULT_ALLOWLIST = Path(__file__).resolve().parent / "allowlist.json"


class AuditError(Exception):
    """Base class for all audit input errors."""


class FlowError(AuditError):
    """A captured flow record is malformed."""


class AllowlistError(AuditError):
    """The allowlist file is malformed."""


# ---------------------------------------------------------------------------
# matching primitives
# ---------------------------------------------------------------------------

def _normalize_host(host):
    """Lowercase, strip a trailing FQDN dot and a numeric port suffix."""
    host = host.strip().lower().rstrip(".")
    if ":" in host:
        candidate, _, port = host.rpartition(":")
        if port.isdigit():
            host = candidate
    return host


def host_matches(pattern, host):
    """Return True if *host* matches the allowlist *pattern*.

    Supported patterns, and nothing else:

      * exact hostname: "example.com" matches only "example.com"
      * leading wildcard label: "*.example.com" matches any subdomain
        ("www.example.com", "a.b.example.com") but NOT the apex
        "example.com" and NOT suffix lookalikes ("evilexample.com").

    Any other use of "*" is unsupported and raises AllowlistError, so a
    typo in the allowlist fails the audit instead of silently allowing
    traffic.
    """
    if not isinstance(pattern, str) or not pattern:
        raise AllowlistError("host pattern must be a non-empty string, "
                             "got {!r}".format(pattern))
    pattern = _normalize_host(pattern)
    host = _normalize_host(host)
    if pattern.startswith("*."):
        base = pattern[2:]
        if not base or "*" in base:
            raise AllowlistError(
                "unsupported host pattern {!r}: only a single leading "
                "'*.' label is allowed".format(pattern))
        return host.endswith("." + base)
    if "*" in pattern:
        raise AllowlistError(
            "unsupported host pattern {!r}: wildcards are only allowed "
            "as a leading '*.' label".format(pattern))
    return host == pattern


def path_matches(prefix, path):
    """Segment-aware path-prefix match.

    "/downloads" matches "/downloads" and "/downloads/file.bin" but not
    "/downloads-evil".  A prefix ending in "/" matches anything below it.
    """
    if not path.startswith(prefix):
        return False
    if len(path) == len(prefix) or prefix.endswith("/"):
        return True
    return path[len(prefix)] == "/"


def rule_matches(rule, flow):
    """Return True if a single validated allowlist rule explains *flow*."""
    if not host_matches(rule["host"], flow["host"]):
        return False
    prefix = rule.get("path_prefix")
    if prefix is not None:
        path = urlsplit(flow["url"]).path or "/"
        return path_matches(prefix, path)
    return True


# ---------------------------------------------------------------------------
# input validation
# ---------------------------------------------------------------------------

def validate_flow(flow, index):
    """Raise FlowError unless *flow* is a well-formed flow record."""
    where = "flow #{}".format(index)
    if not isinstance(flow, dict):
        raise FlowError("{}: expected an object, got {}".format(
            where, type(flow).__name__))
    for key in REQUIRED_FLOW_KEYS:
        if key not in flow:
            raise FlowError("{}: missing required key {!r}".format(
                where, key))
    for key in ("url", "method", "host", "scenario"):
        value = flow[key]
        if not isinstance(value, str) or not value.strip():
            raise FlowError("{}: key {!r} must be a non-empty string, "
                            "got {!r}".format(where, key, value))
    timestamp = flow["timestamp"]
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        raise FlowError("{}: key 'timestamp' must be a number, got {!r}"
                        .format(where, timestamp))
    parts = urlsplit(flow["url"])
    if not parts.scheme or not parts.netloc:
        raise FlowError("{}: 'url' is not an absolute URL: {!r}".format(
            where, flow["url"]))


def validate_allowlist(allowlist):
    """Raise AllowlistError unless *allowlist* is well formed."""
    if not isinstance(allowlist, dict):
        raise AllowlistError("allowlist root must be an object")
    scenarios = allowlist.get("scenarios")
    if not isinstance(scenarios, dict):
        raise AllowlistError("allowlist must contain a 'scenarios' object")
    for name, rules in scenarios.items():
        if not isinstance(rules, list):
            raise AllowlistError(
                "scenario {!r}: rules must be a list (an empty list means "
                "nothing is allowed)".format(name))
        for i, rule in enumerate(rules):
            where = "scenario {!r} rule #{}".format(name, i)
            if not isinstance(rule, dict):
                raise AllowlistError("{}: expected an object".format(where))
            host = rule.get("host")
            if not isinstance(host, str) or not host.strip():
                raise AllowlistError(
                    "{}: 'host' must be a non-empty string".format(where))
            # Validate the pattern shape now, so a bad pattern fails the
            # audit up front rather than silently never matching.
            host_matches(host, "probe.invalid")
            reason = rule.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise AllowlistError(
                    "{}: 'reason' is mandatory and must explain why this "
                    "traffic is user-initiated".format(where))
            prefix = rule.get("path_prefix")
            if prefix is not None and (not isinstance(prefix, str)
                                       or not prefix.startswith("/")):
                raise AllowlistError(
                    "{}: 'path_prefix' must be a string starting with '/'"
                    .format(where))


def load_allowlist(path=DEFAULT_ALLOWLIST):
    """Load and validate an allowlist JSON file."""
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as fh:
            allowlist = json.load(fh)
    except FileNotFoundError:
        raise AllowlistError("allowlist not found: {}".format(path))
    except json.JSONDecodeError as exc:
        raise AllowlistError("allowlist {} is not valid JSON: {}".format(
            path, exc))
    validate_allowlist(allowlist)
    return allowlist


def load_flows(path):
    """Load a flows JSON file: either a list, or {"flows": [...]}."""
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise FlowError("flows file not found: {}".format(path))
    except json.JSONDecodeError as exc:
        raise FlowError("flows file {} is not valid JSON: {}".format(
            path, exc))
    if isinstance(data, dict) and isinstance(data.get("flows"), list):
        data = data["flows"]
    if not isinstance(data, list):
        raise FlowError("flows file must contain a JSON list of flows "
                        "(or an object with a 'flows' list)")
    return data


# ---------------------------------------------------------------------------
# verdict
# ---------------------------------------------------------------------------

def check_flows(flows, allowlist):
    """Check every flow against the allowlist.

    Returns a list of violation dicts, one per unexplained flow:
        {"flow": <the flow>, "why": <human-readable explanation>}
    An empty return value means every request was explained.

    Raises FlowError / AllowlistError on malformed input: the audit
    refuses to produce a PASS verdict from data it cannot trust.
    """
    validate_allowlist(allowlist)
    scenarios = allowlist["scenarios"]
    violations = []
    for index, flow in enumerate(flows):
        validate_flow(flow, index)
        scenario = flow["scenario"]
        if scenario not in scenarios:
            violations.append({
                "flow": flow,
                "why": "scenario {!r} has no allowlist section "
                       "(default deny: unknown scenarios allow nothing)"
                       .format(scenario),
            })
            continue
        rules = scenarios[scenario]
        if not rules:
            violations.append({
                "flow": flow,
                "why": "scenario {!r} allows no traffic at all; the "
                       "browser must be silent here".format(scenario),
            })
            continue
        if not any(rule_matches(rule, flow) for rule in rules):
            violations.append({
                "flow": flow,
                "why": "none of the {} allowlist rule(s) for scenario "
                       "{!r} match this destination".format(
                           len(rules), scenario),
            })
    return violations


def format_report(violations, total_flows):
    """Render a human-readable verdict report."""
    lines = []
    lines.append("== T3dmium network audit ==")
    lines.append("flows captured : {}".format(total_flows))
    lines.append("violations     : {}".format(len(violations)))
    lines.append("")
    if not violations:
        lines.append("VERDICT: PASS — every captured request is explained "
                     "by a scripted user action.")
        return "\n".join(lines)
    for i, violation in enumerate(violations, 1):
        flow = violation["flow"]
        lines.append("VIOLATION {}/{}".format(i, len(violations)))
        lines.append("  scenario : {}".format(flow["scenario"]))
        lines.append("  request  : {} {}".format(flow["method"], flow["url"]))
        lines.append("  host     : {}".format(flow["host"]))
        lines.append("  time     : {}".format(flow["timestamp"]))
        lines.append("  why      : {}".format(violation["why"]))
        lines.append("")
    lines.append("VERDICT: FAIL — {} request(s) were not explained by any "
                 "scripted user action.".format(len(violations)))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check captured network flows against the T3dmium "
                    "per-scenario allowlist (default deny).")
    parser.add_argument("flows", help="path to a flows JSON file")
    parser.add_argument("--allowlist", default=str(DEFAULT_ALLOWLIST),
                        help="allowlist JSON (default: %(default)s)")
    args = parser.parse_args(argv)
    try:
        flows = load_flows(args.flows)
        allowlist = load_allowlist(args.allowlist)
        violations = check_flows(flows, allowlist)
    except AuditError as exc:
        print("audit input error: {}".format(exc), file=sys.stderr)
        return 2
    print(format_report(violations, len(flows)))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
