# ADR-0004: Single repository with a platforms/ directory

**Status:** accepted (2026-07-07)

## Context

ungoogled-chromium splits platform packaging into separate repositories
(ungoogled-chromium-macos, -windows) that consume the core repo as a git
submodule. That suits their federated, per-platform maintainer model.

## Decision

T3dmium is one repository. Platform-specific packaging lives in
`platforms/macos/` and `platforms/windows/`; the core patch set and tooling
are platform-neutral. macOS and Windows are first-class, equal-priority
targets; macOS is the primary test platform.

## Consequences

- "Clone one repo, follow BUILDING.md" holds for every platform — no
  submodule choreography for contributors.
- CI can build both platforms from one ref, so a patch change that breaks
  one platform's packaging is visible in the same PR that caused it.
- If platform maintainership ever federates, the directory split makes a
  future repo split mechanical.
