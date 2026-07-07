# ADR-0001: Fork model — patch set, not a vendored tree

**Status:** accepted (2026-07-07)

## Context

Chromium is roughly 30 million lines of code; a full checkout is ~50 GB and
builds take hours. Vendoring it would make the repository unusable and
reviews meaningless. The established alternative, proven by
ungoogled-chromium and (in spirit) Brave, is a repository containing only a
version pin, a patch series, build configuration, and tooling.

## Decision

This repository never contains Chromium source. `chromium_version.txt` pins
one stable release; `downloads.ini` describes the official source tarball
(sha256-verified); `patches/series` defines an ordered quilt-format patch
set; `tools/` fetches, patches, and builds. Everything under `build/` is
generated and gitignored.

## Consequences

- The repo stays small, reviewable, and diffable; a patch is the unit of
  change.
- Every Chromium version bump is an explicit, testable event: update the pin,
  rebase the series, re-run validation.
- Patches must be validated against the pin without assuming contributors
  have a 50 GB tree — hence `tools/validate_patches.py --remote`, which
  fetches only the touched files from chromium.googlesource.com at the
  pinned tag.
