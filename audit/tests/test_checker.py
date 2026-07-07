"""Self-test for the T3dmium network-audit detection engine.

Pure stdlib unittest, runnable on Python 3.9 with zero third-party
packages:

    cd <repo root>
    python3 -m unittest discover -s audit/tests -v
"""

import copy
import sys
import unittest
from pathlib import Path

AUDIT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AUDIT_DIR))

import checker  # noqa: E402

FIXTURES = AUDIT_DIR / "fixtures"

# The leaks planted in leaky_run.json, as (scenario, host) pairs.
PLANTED_LEAKS = [
    ("idle", "update.googleapis.com"),
    ("idle", "clientservices.googlechrome.com"),
    ("navigation", "safebrowsing.googleapis.com"),
    ("settings", "clients2.google.com"),
    ("search", "evilduckduckgo.com"),
]


def make_flow(**overrides):
    flow = {
        "url": "https://example.com/",
        "method": "GET",
        "host": "example.com",
        "timestamp": 1751900000.0,
        "scenario": "navigation",
    }
    flow.update(overrides)
    return flow


class FixtureTests(unittest.TestCase):
    """The shipped fixtures against the shipped allowlist."""

    @classmethod
    def setUpClass(cls):
        cls.allowlist = checker.load_allowlist()
        cls.clean = checker.load_flows(FIXTURES / "clean_run.json")
        cls.leaky = checker.load_flows(FIXTURES / "leaky_run.json")

    def test_clean_run_has_zero_violations(self):
        violations = checker.check_flows(self.clean, self.allowlist)
        self.assertEqual(violations, [])

    def test_leaky_run_flags_exactly_the_planted_leaks(self):
        violations = checker.check_flows(self.leaky, self.allowlist)
        flagged = sorted((v["flow"]["scenario"], v["flow"]["host"])
                         for v in violations)
        self.assertEqual(flagged, sorted(PLANTED_LEAKS))

    def test_each_planted_leak_host_appears_in_the_report(self):
        violations = checker.check_flows(self.leaky, self.allowlist)
        report = checker.format_report(violations, len(self.leaky))
        for _, host in PLANTED_LEAKS:
            self.assertIn(host, report)
        self.assertIn("FAIL", report)

    def test_leaky_run_is_clean_run_plus_the_leaks(self):
        """Guard the fixtures themselves: leaky must be clean + leaks."""
        leaked = [f for f in self.leaky if f not in self.clean]
        self.assertEqual(sorted((f["scenario"], f["host"]) for f in leaked),
                         sorted(PLANTED_LEAKS))
        self.assertEqual(len(self.leaky), len(self.clean) + len(leaked))


class HostGlobTests(unittest.TestCase):
    """Glob matching edge cases: no suffix trickery may slip through."""

    def test_wildcard_matches_subdomains(self):
        self.assertTrue(
            checker.host_matches("*.duckduckgo.com", "www.duckduckgo.com"))
        self.assertTrue(
            checker.host_matches("*.duckduckgo.com", "a.b.duckduckgo.com"))

    def test_wildcard_rejects_suffix_lookalikes(self):
        self.assertFalse(
            checker.host_matches("*.duckduckgo.com", "evilduckduckgo.com"))
        self.assertFalse(
            checker.host_matches("*.duckduckgo.com",
                                 "duckduckgo.com.evil.example"))

    def test_wildcard_does_not_match_the_apex(self):
        # Apex access needs its own explicit rule; *.host is subdomains only.
        self.assertFalse(
            checker.host_matches("*.duckduckgo.com", "duckduckgo.com"))

    def test_exact_match_is_exact(self):
        self.assertTrue(checker.host_matches("example.com", "example.com"))
        self.assertFalse(checker.host_matches("example.com",
                                              "www.example.com"))
        self.assertFalse(checker.host_matches("example.com",
                                              "notexample.com"))

    def test_matching_is_case_insensitive_and_ignores_trailing_dot(self):
        self.assertTrue(checker.host_matches("Example.COM", "example.com."))
        self.assertTrue(
            checker.host_matches("*.duckduckgo.com", "WWW.DuckDuckGo.com"))

    def test_port_suffix_is_stripped(self):
        self.assertTrue(checker.host_matches("example.com",
                                             "example.com:8443"))

    def test_unsupported_wildcard_placement_fails_closed(self):
        for bad in ("example.*", "ex*mple.com", "*", "*.", "*.*.com"):
            with self.assertRaises(checker.AllowlistError):
                checker.host_matches(bad, "example.com")

    def test_path_prefix_is_segment_aware(self):
        self.assertTrue(checker.path_matches("/dl", "/dl"))
        self.assertTrue(checker.path_matches("/dl", "/dl/file.bin"))
        self.assertFalse(checker.path_matches("/dl", "/dl-evil/file.bin"))
        self.assertTrue(checker.path_matches("/dl/", "/dl/anything"))


class DefaultDenyTests(unittest.TestCase):
    """Anything not explicitly allowed is a violation."""

    def test_unknown_scenario_denies_even_allowlisted_hosts(self):
        allowlist = {"scenarios": {"navigation": [
            {"host": "example.com", "reason": "scripted navigation"}]}}
        flow = make_flow(scenario="mystery")
        violations = checker.check_flows([flow], allowlist)
        self.assertEqual(len(violations), 1)
        self.assertIn("mystery", violations[0]["why"])

    def test_empty_scenario_section_allows_nothing(self):
        allowlist = {"scenarios": {"idle": []}}
        flow = make_flow(scenario="idle",
                         url="https://update.googleapis.com/x",
                         host="update.googleapis.com")
        violations = checker.check_flows([flow], allowlist)
        self.assertEqual(len(violations), 1)

    def test_completely_empty_allowlist_allows_nothing(self):
        violations = checker.check_flows([make_flow()], {"scenarios": {}})
        self.assertEqual(len(violations), 1)

    def test_rule_in_one_scenario_does_not_leak_into_another(self):
        allowlist = {"scenarios": {
            "navigation": [{"host": "example.com", "reason": "scripted"}],
            "idle": [],
        }}
        flow = make_flow(scenario="idle")  # same host, wrong scenario
        violations = checker.check_flows([flow], allowlist)
        self.assertEqual(len(violations), 1)

    def test_path_prefix_restricts_the_rule(self):
        allowlist = {"scenarios": {"downloads": [
            {"host": "example.com", "path_prefix": "/files",
             "reason": "scripted download"}]}}
        ok = make_flow(scenario="downloads",
                       url="https://example.com/files/a.bin")
        bad = make_flow(scenario="downloads",
                        url="https://example.com/telemetry")
        self.assertEqual(checker.check_flows([ok], allowlist), [])
        self.assertEqual(len(checker.check_flows([bad], allowlist)), 1)

    def test_no_violations_means_empty_list(self):
        allowlist = {"scenarios": {"navigation": [
            {"host": "example.com", "reason": "scripted"}]}}
        self.assertEqual(checker.check_flows([make_flow()], allowlist), [])


class MalformedInputTests(unittest.TestCase):
    """The audit must refuse to pass on data it cannot trust."""

    ALLOWLIST = {"scenarios": {"navigation": [
        {"host": "example.com", "reason": "scripted"}]}}

    def test_flow_missing_each_required_key_is_rejected(self):
        for key in checker.REQUIRED_FLOW_KEYS:
            flow = make_flow()
            del flow[key]
            with self.assertRaises(checker.FlowError):
                checker.check_flows([flow], self.ALLOWLIST)

    def test_non_dict_flow_is_rejected(self):
        with self.assertRaises(checker.FlowError):
            checker.check_flows(["not a flow"], self.ALLOWLIST)

    def test_wrong_types_are_rejected(self):
        bad_flows = [
            make_flow(url=""),
            make_flow(url="no-scheme"),
            make_flow(method=7),
            make_flow(host=""),
            make_flow(timestamp="yesterday"),
            make_flow(timestamp=True),
            make_flow(scenario=""),
        ]
        for flow in bad_flows:
            with self.assertRaises(checker.FlowError):
                checker.check_flows([flow], self.ALLOWLIST)

    def test_rule_without_reason_is_rejected(self):
        allowlist = copy.deepcopy(self.ALLOWLIST)
        del allowlist["scenarios"]["navigation"][0]["reason"]
        with self.assertRaises(checker.AllowlistError):
            checker.check_flows([make_flow()], allowlist)

    def test_allowlist_without_scenarios_key_is_rejected(self):
        with self.assertRaises(checker.AllowlistError):
            checker.check_flows([make_flow()], {})

    def test_bad_path_prefix_is_rejected(self):
        allowlist = copy.deepcopy(self.ALLOWLIST)
        allowlist["scenarios"]["navigation"][0]["path_prefix"] = "files"
        with self.assertRaises(checker.AllowlistError):
            checker.check_flows([make_flow()], allowlist)


if __name__ == "__main__":
    unittest.main()
