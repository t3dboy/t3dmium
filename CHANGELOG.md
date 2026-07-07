# Changelog

All notable changes to T3dmium. Versions correspond to roadmap phases; each
is tagged in git. Dates are ISO-8601.

The project pins **Chromium 150.0.7871.46** throughout this series.

## [0.7.0] — 2026-07-07 — Phase 6: self-hosted encrypted sync
- `sync/`: self-hostable, zero-knowledge encrypted sync server. Client-side
  key derivation (PBKDF2 → HKDF), server stores only opaque ciphertext and a
  hash of the group auth token. Pure-stdlib server + reference client + 15
  passing tests; Dockerfile/compose. ADR-0006 records the design; browser
  client integration is deferred until a build host exists.

## [0.6.0] — 2026-07-07 — Phase 5: branding + installers
- `branding/`: SVG master icon and generator; user-agent policy (identical
  to Chrome, no unique token, for fingerprinting resistance).
- `platforms/macos/`: build + DMG packaging, ad-hoc and Developer ID signing
  with notarization, entitlements, reproducible-build notes.
- `platforms/windows/`: build script, NSIS installer, signing docs.

## [0.5.0] — 2026-07-07 — Phase 4: ad/tracker blocking + local Safe Browsing
- ADR-0005: adopt Brave's adblock-rust over declarativeNetRequest.
- EasyList/EasyPrivacy pinned in `downloads.ini` (immutable commit, real
  sha256, `type=file`); `fetch.py` verify-and-copy support.
- Audit `adblock_update` scenario: list fetch allowed only on a user action.
- Local Safe Browsing blocklist option documented (off by default).

## [0.4.0] — 2026-07-07 — Phase 3: privacy defaults
- `patches/privacy/enable-do-not-track-by-default.patch`: Do Not Track and
  Global Privacy Control on by default, validated against the pin.
- Documented deferred items (DuckDuckGo default search needs a build).

## [0.3.0] — 2026-07-07 — Phase 2: network audit harness
- `audit/`: mitmproxy-based capture, default-deny detection engine, scenario
  driver, and a browserless self-test (24 tests) wired into CI.

## [0.2.0] — 2026-07-07 — Phase 1: de-Google patch set
- Adopted ungoogled-chromium's 108-patch set (tag 150.0.7871.46-1) under
  `patches/degoogle/`, plus pruning/domain-substitution lists.
- DEPS-aware remote patch validation; full series validates against the pin.

## [0.1.0] — 2026-07-07 — Phase 0: scaffold + toolchain
- Repository skeleton: version pin, `downloads.ini`, `flags.gn`, tooling
  (fetch/apply/validate/build/lint), docs (README, BUILDING, PRIVACY,
  CONTRIBUTING, code of conduct), ADRs 0001–0004, CI workflows.

[0.7.0]: https://github.com/t3dboy/t3dmium/releases/tag/v0.7.0-phase6
[0.6.0]: https://github.com/t3dboy/t3dmium/releases/tag/v0.6.0-phase5
[0.5.0]: https://github.com/t3dboy/t3dmium/releases/tag/v0.5.0-phase4
[0.4.0]: https://github.com/t3dboy/t3dmium/releases/tag/v0.4.0-phase3
[0.3.0]: https://github.com/t3dboy/t3dmium/releases/tag/v0.3.0-phase2
[0.2.0]: https://github.com/t3dboy/t3dmium/releases/tag/v0.2.0-phase1
[0.1.0]: https://github.com/t3dboy/t3dmium/releases/tag/v0.1.0-phase0
