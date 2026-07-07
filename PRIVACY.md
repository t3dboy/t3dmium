# T3dmium Privacy Policy and Commitments

This document is the authoritative statement of what T3dmium does and does
not do with the network. It is a living document: every change to the
browser that could affect network behaviour must be reflected here (see
[CONTRIBUTING.md](CONTRIBUTING.md)).

## The commitments, in plain English

1. **T3dmium sends no telemetry, analytics, or usage data to anyone.** Not
   to Google, not to us, not to any third party. There is no metrics
   collection, no crash upload, no experiment enrolment, no install ping.
2. **The only network traffic is user-initiated.** The browser contacts the
   network when *you* do something that requires it: navigating to a page,
   running an update check you have opted into, or installing an extension
   you asked for. Nothing runs in the background on your behalf.
3. **Privacy-protective defaults, user control on top.** Features that
   trade privacy for convenience are off by default and clearly explained
   in the UI when you turn them on. Features that protect you (third-party
   cookie blocking, Do Not Track / Global Privacy Control, non-leaking
   WebRTC) are on by default.
4. **The guarantee is verified, not just promised.** An automated network
   audit harness in [`audit/`](audit/), built on mitmproxy, runs in CI and
   fails if any non-user-initiated request leaves the machine. Anyone can
   run it locally against their own build.

If you observe the browser making a network request that these commitments
do not allow, that is a serious bug. Please report it using the
[privacy leak issue template](.github/ISSUE_TEMPLATE/privacy_leak.md).

## Service-by-service handling

T3dmium is in early development (Phase 0: patch set and tooling). The table
below lists every Google or third-party service in Chromium that generates
network traffic or shapes behaviour, how T3dmium handles it, and the current
implementation status. Statuses are updated as work lands.

| Service / feature | How T3dmium handles it | Status |
| --- | --- | --- |
| Google account sign-in / Chrome Sync / GAIA | Removed entirely. No Google account integration, no sync service, no GAIA endpoints. | Planned (Phase 1) |
| Safe Browsing pings | Remote Safe Browsing removed. Replaced by an optional, fully **local** blocklist — no URLs or hashes ever leave the machine. OFF by default and clearly explained in the UI. | Planned (Phase 1) |
| Field trials / Finch / variations | Removed. No experiment configuration is fetched; all users run the same code with the same defaults. | Planned (Phase 1) |
| Component updater phone-home | Removed. Components (e.g. certificate lists, CRLSets equivalents) ship inside each release rather than being fetched at runtime. | Planned (Phase 1) |
| Crash reporting (Crashpad uploads) | Upload path removed. Crashes are written locally only; nothing is transmitted. | Planned (Phase 1) |
| UMA / UKM metrics | Removed. No usage metrics are collected or sent. | Planned (Phase 1) |
| RLZ | Removed. | Planned (Phase 1) |
| Rappor | Removed. | Planned (Phase 1) |
| Omnibox remote search suggestions | OFF by default. If the user enables suggestions, keystrokes go only to the user-chosen search engine, never anywhere else. | Planned (Phase 1) |
| Network prediction / preconnect / prefetch / DNS prefetch | Conservative defaults; fully user-controllable. Nothing is prefetched from pages you have not chosen to visit without your setting saying so. | Planned (Phase 1) |
| Translate ranker / translate service | Remote translate service and ranker removed. | Planned (Phase 1) |
| Spellcheck download service | Removed. Dictionaries are bundled locally with the browser. | Planned (Phase 1) |
| Promotions / "What's New" / default-browser nags / feed surfaces | Removed. No promotional content is fetched or shown. | Planned (Phase 1) |
| Push via Google Cloud Messaging | Removed. No GCM/FCM connection is established. | Planned (Phase 1) |
| Baked-in Google API keys | None. All Google API keys are removed from the build. | Planned (Phase 1) |
| Default search engine | DuckDuckGo, or the user's choice at first run. Never Google by default. | Planned (Phase 1) |
| WebRTC IP handling | Non-leaking default: local IP addresses are not exposed to sites via WebRTC unless the user changes the setting. | Planned (Phase 1) |
| Do Not Track + Global Privacy Control | Both ON by default. | Planned (Phase 1) |
| Referrer trimming | Cross-site referrers are trimmed. | Planned (Phase 1) |
| Third-party cookie blocking | ON by default. | Planned (Phase 1) |
| Partitioned storage | Third-party storage is partitioned by top-level site. | Planned (Phase 1) |

## User-agent policy

T3dmium's user-agent string **matches Chrome's exactly** for the pinned
Chromium version, with no T3dmium token or other unique marker. Announcing a
niche browser in every request would make users stand out; blending in with
the largest browser population is the fingerprinting-resistant choice.

## Verification

The audit harness in [`audit/`](audit/) launches the browser behind a
mitmproxy instance, exercises it through defined scenarios (fresh profile,
idle, navigation, settings pages), and fails CI if any request is observed
that was not initiated by a scripted user action. You are encouraged to run
it against your own build and to report anything it misses.
