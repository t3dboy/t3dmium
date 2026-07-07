# ADR-0003: Licensing and attribution

**Status:** accepted (2026-07-07)

## Context

T3dmium combines original work with material from ungoogled-chromium
(BSD-3-Clause) and builds Chromium (BSD-3-Clause). Later phases evaluate
Brave's adblock engine (MPL-2.0) and patches from Cromite (GPL-3.0), whose
licenses have stronger conditions.

## Decision

- T3dmium's own code and patches: **BSD-3-Clause** (LICENSE).
- Adopted material keeps its upstream license; attributions are centralised
  in `NOTICE` and named per-patch via the mandatory `Origin:` header line.
- GPL-licensed patches (e.g. from Cromite) may only be adopted if we accept
  the resulting distribution obligations for the built binary; each such
  adoption needs its own ADR before merging. BSD/MPL material needs no
  special handling beyond NOTICE entries.

## Consequences

- The repository stays permissively licensed; consumers can reuse our
  tooling and patches freely.
- `tools/check_conventions.py` enforces the `Origin:` header so provenance
  is never lost.
