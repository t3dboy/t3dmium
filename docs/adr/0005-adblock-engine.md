# ADR-0005: Ad and tracker blocking engine

**Status:** accepted (2026-07-07)

## Context

T3dmium ships built-in ad/tracker blocking driven by EasyList and
EasyPrivacy. Two implementation routes exist in a Chromium fork:

1. **Brave's `adblock-rust`** — a Rust engine that parses Adblock Plus
   filter syntax and matches network requests. Brave integrates it as a
   component in the network service. It supports the full filter syntax
   (cosmetic filters, `$`-options, exceptions) and is fast.
2. **Chromium's own `declarativeNetRequest` (DNR)** — the Manifest V3 API.
   Filter lists are converted to DNR JSON rules shipped as a built-in
   ("reserved") ruleset. No new engine; uses machinery already in the
   browser.

## Decision

**Adopt `adblock-rust` as the blocking engine, shipped as an in-release
component; keep a DNR-based ruleset as a documented fallback.**

Reasons adblock-rust wins for our goals:

- **Coverage.** EasyList/EasyPrivacy use the full Adblock Plus syntax,
  including cosmetic rules and option modifiers that DNR cannot express. A
  DNR conversion silently drops unsupported rules, weakening protection in
  ways users cannot see.
- **Rule-count ceiling.** DNR caps the number of rules (the dynamic and
  static ruleset limits). EasyList + EasyPrivacy combined exceed comfortable
  DNR budgets; adblock-rust has no such cap.
- **Privacy alignment.** The lists ship inside each release. Updates happen
  only when the user clicks "Update filter lists" (an explicit,
  user-initiated fetch to a pinned list URL over the network audit's
  allowlist), never via a background component-updater ping. This matches
  T3dmium's core guarantee; the removed Google component updater is not
  reintroduced.
- **Licensing.** adblock-rust is MPL-2.0 — compatible with our
  distribution; attribution goes in NOTICE and the integration patch header.

DNR is retained as a fallback strategy (documented in the integration
patch and this ADR) for two cases: environments where compiling the Rust
component is undesirable, and extension-authored rules, which continue to
use Chromium's native DNR untouched.

## Consequences

- The build gains a Rust component and its crate dependencies; BUILDING.md
  documents the extra toolchain (Chromium already builds Rust, so the
  incremental cost is the crate vendor step).
- Filter lists are a versioned artifact: `downloads.ini` pins EasyList and
  EasyPrivacy snapshots by URL + sha256, exactly like the Chromium tarball,
  so a release is reproducible and the shipped lists are auditable.
- The list-update path is the only new network capability; it is
  user-initiated and covered by an audit-harness scenario and an allowlist
  entry with a reason.

## Status of implementation

The engine integration is a substantial patch against the network service
and requires a build to verify behaviour, which this environment cannot
produce (see BUILDING.md hardware notes). This ADR fixes the decision and
the list-pinning mechanism; the integration patch lands with the branding
and packaging work once a build host is available. The list pinning and the
audit scenario are wired up now so the privacy contract is testable ahead of
the engine.
