# Feature patches

Patches that add T3dmium features on top of the de-Google base and privacy
defaults. Most require a build to verify behaviour, so they land as a build
host becomes available; the mechanisms they depend on are pinned and
testable now.

## Ad / tracker blocking (Phase 4, ADR-0005)

- **Engine:** Brave's `adblock-rust` (MPL-2.0), integrated as an in-release
  component in the network service. Chosen over `declarativeNetRequest` for
  fuller EasyList/EasyPrivacy syntax coverage and no rule-count ceiling
  (see [ADR-0005](../../docs/adr/0005-adblock-engine.md)).
- **Lists:** pinned in `downloads.ini` to an immutable EasyList commit
  (`type=file` entries, sha256-verified), so a release is reproducible.
- **Updates:** only when the user clicks "Update filter lists". No
  background updater exists. The fetch is covered by the audit harness
  scenario `adblock_update` and an allowlist entry with a reason.

## Local Safe Browsing option (Phase 4)

Google Safe Browsing pings are removed by the de-Google set. As an opt-in
replacement, a **fully local** blocklist (URLs/hashes shipped in-release,
matched on-device) can be enabled — **off by default**, explained in the
settings UI, and generating no network traffic when on.

## Opt-in update checker (Phase 5)

Checks the GitHub Releases API for a newer T3dmium version **only** when the
user clicks "Check for updates". Never polls in the background; covered by an
audit scenario when implemented.

## Deferred until a build host exists

The engine integration, the local Safe Browsing UI, and the settings surface
for these toggles are Chromium-internal patches whose behaviour cannot be
verified by remote patch validation alone — they need a compiled binary and
the audit harness run against it. They are staged here rather than shipped
as guessed diffs.
