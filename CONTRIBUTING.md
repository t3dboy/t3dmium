# Contributing to T3dmium

Thanks for your interest in contributing. This document explains how to
propose changes and the conventions the repository enforces.

## How to propose changes

1. **Open an issue first for anything non-trivial.** Describe the problem
   or feature before writing a patch, so we can agree on the approach.
   Small fixes (typos, obvious tooling bugs) can go straight to a PR.
2. **Fork, branch, and open a pull request** against `main` at
   [t3dboy/t3dmium](https://github.com/t3dboy/t3dmium).
3. **Fill in the PR template** and make sure the checks below pass.

## The privacy bar

T3dmium's core promise is that the only network traffic is user-initiated.
Every change is held to that bar:

- **Any change that could generate network traffic** — new feature, changed
  default, modified patch — **must update [PRIVACY.md](PRIVACY.md)** to
  document the behaviour, **and** must be covered by the audit harness in
  `audit/` so the behaviour is verified in CI, not just described.
- If you are unsure whether a change affects network behaviour, say so in
  the PR and we will work it out together.

## Patch conventions

The patch set is the heart of the repository. Patches must follow these
rules (enforced by `tools/check_conventions.py`):

- **Location:** patches live under one of four category directories:
  `patches/degoogle/`, `patches/privacy/`, `patches/branding/`,
  `patches/features/`.
- **Ordering:** `patches/series` is a quilt-format file listing every patch
  in application order. **Order matters.** Paths are relative to
  `patches/`, and lines starting with `#` are comments.
- **Format:** unified diff, applied with `-p1` strip, using `a/` and `b/`
  path prefixes, 3 lines of context, UTF-8 encoding, `.patch` file suffix.
- **Header:** every patch starts with a header before the first `---` line:

  ```
  Description: <one-or-two sentence what & why>
  Origin: <t3dmium | adapted from <project> (<original path or URL>)>
  ```

- **Never submit a patch authored blind.** Every hunk must be generated
  against the pinned Chromium sources (see `chromium_version.txt`) — either
  a local `build/src` tree or the remote pinned sources. Hand-written hunks
  that "should" apply are not acceptable; `tools/validate_patches.py
  --remote` will catch them, but do not make it do so.

## Required checks

Before opening a PR, run:

```
python3 tools/check_conventions.py         # repo lint: patch headers, series consistency
python3 tools/validate_patches.py --remote # validate patches against the pinned sources
```

Both run in CI (`pr-check`) and PRs must pass them. `--remote` fetches the
pinned files from chromium.googlesource.com, so you do not need a local
Chromium tree to validate.

If your change touches the build tooling or `flags.gn`, a local build
(`python3 tools/build.py`) on at least one platform is strongly encouraged —
note in the PR which platform(s) you built on.

## Commit style

- Conventional-ish, imperative subject line: `patches: remove translate
  ranker endpoint`, `tools: fix sha256 check on partial downloads`.
- Keep the subject under ~72 characters; explain the *why* in the body when
  it is not obvious.
- One logical change per commit where practical.

## Questions

Open an issue on GitHub — that is the project's main communication channel.
