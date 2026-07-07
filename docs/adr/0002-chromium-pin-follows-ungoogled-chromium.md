# ADR-0002: The Chromium pin tracks ungoogled-chromium's pin

**Status:** accepted (2026-07-07)

## Context

Our de-Google layer (patches/degoogle/) is adopted from ungoogled-chromium,
which validates its patch set against exactly one Chromium version at a time.
If our pin diverged from theirs we would own the rebase of ~110 patches onto
a version nobody else tests.

## Decision

`chromium_version.txt` is set to the version ungoogled-chromium targets on
its release tags (currently 150.0.7871.46, their tag 150.0.7871.46-1). Pin
bumps follow their releases rather than raw Chromium stable releases.

## Consequences

- The adopted de-Google patches apply cleanly by construction; only
  T3dmium's own patches (privacy/, branding/, features/) need re-validation
  on a bump.
- We inherit their cadence: typically days behind Chromium stable. For
  security-critical releases we can bump early and carry temporary rebase
  fixes, accepting the extra work for that window.
