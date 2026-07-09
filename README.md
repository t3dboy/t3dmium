# T3dmium

[![pr-check](https://github.com/t3dboy/t3dmium/actions/workflows/pr-check.yml/badge.svg)](https://github.com/t3dboy/t3dmium/actions/workflows/pr-check.yml)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](LICENSE)

**T3dmium is a privacy-first web browser built on Chromium that sends nothing to
Google — or anyone else — in the background.** It is the real Chromium engine,
with real Chrome performance, web compatibility, and extension support, but with
every form of telemetry, analytics, and "phone home" traffic stripped out. The
only network traffic T3dmium ever generates is traffic **you** start: loading a
page, an update check you opted into, or installing an extension you asked for.
Nothing runs behind your back. And this isn't just a promise — it's checked
automatically on every change (see [Verified, not promised](#verified-not-promised)).

## Why

Chromium is an outstanding browser engine wrapped in a large amount of
Google-facing plumbing. A normal Chrome or Chromium install quietly contacts
Google many times before you have even typed a web address: it enrols in
experiments, uploads usage statistics, checks for component updates, reports
crashes, fetches promotional content, and more. Most of this happens with no
visible sign and no easy off switch.

Plenty of "private" Chromium builds *reduce* this traffic. T3dmium's goal is to
**eliminate** it — and to make that elimination something you can independently
verify rather than take on faith.

## What makes it private

T3dmium removes or neutralizes the entire de-Google surface and turns on
protective defaults. In short:

- **No telemetry, analytics, or usage metrics** (UMA/UKM, RLZ — all gone).
- **No experiments or field trials** (Finch/variations gone — everyone runs the
  exact same code).
- **No crash uploads** (crashes stay on your machine, never transmitted).
- **No component-updater or "check in" background pings.**
- **No Google account sign-in, Chrome Sync, or GAIA.**
- **No Safe Browsing pings** (an optional, **fully local** blocklist is planned
  instead — off by default, nothing ever leaves your machine).
- **No search-suggestion pings by default** (if you turn them on, keystrokes go
  only to *your* chosen search engine).
- **No Google Cloud Messaging push, no translate pings, no spellcheck download
  service** (dictionaries are local), **no promos, "What's New", or
  default-browser nags.**
- **No baked-in Google API keys**, and **the default search engine is not
  Google.**
- **Do Not Track and Global Privacy Control (GPC): ON by default.**
- **Third-party cookies: blocked by default.**
- **Referrer trimming and partitioned storage**, plus a **user-agent that
  matches Chrome exactly** so you blend into the crowd instead of standing out.

The full, plain-English rundown of every item — what it is, why it matters, and
what T3dmium does about it — is in
[docs/privacy-features.md](docs/privacy-features.md). If you want the philosophy
and threat model, see [docs/why-privacy-first.md](docs/why-privacy-first.md). The
authoritative, service-by-service commitments live in [PRIVACY.md](PRIVACY.md).

> **Shipped now vs. planned.** The de-Google removal set above, Do Not Track +
> GPC on by default, and third-party cookie blocking on by default are all in
> the build today. A dedicated ad/tracker-blocking engine and a first-run
> DuckDuckGo search picker are on the roadmap and not yet shipped — this README
> and the docs flag which is which so nothing is oversold.

## Verified, not promised

Any browser can *claim* it doesn't phone home. T3dmium proves it.

The repository includes an automated network-audit harness (in
[`audit/`](audit/), built on [mitmproxy](https://mitmproxy.org/)) that launches
the browser behind a proxy, drives it through defined scenarios — fresh profile,
sitting idle, navigating, opening settings pages — and **fails the build if any
request leaves the machine that a user action did not initiate.** It runs in CI,
and you can run it yourself against your own build. If T3dmium ever makes a
request it shouldn't, that's a bug we want reported, not a footnote.

## Download & install

A ready-to-run **macOS build for Apple Silicon (M1/M2/M3/M4)** is available on
the [Releases page](https://github.com/t3dboy/t3dmium/releases). Download the
DMG, open it, and drag **T3dmium** to your Applications folder.

**First launch note:** this is an independent, open-source build that is
*ad-hoc signed* rather than notarized by Apple (paid Apple Developer
notarization isn't part of this project). So the first time you open it, macOS
will warn that it "cannot verify the developer." This is expected. Right-click
(or Control-click) the app → **Open** → **Open**, just once, and it runs normally
from then on. Because the entire source is public and auditable, you don't have
to trust the binary blindly — you can read exactly what it does.

Full step-by-step instructions, including how to confirm you have the correct
architecture and how to uninstall, are in [INSTALL.md](INSTALL.md).

**Honest platform limits:**

- **Apple Silicon only** for now. An **Intel (x86_64) macOS build** and a
  **Windows build** are planned but not yet available.
- The downloadable build is a **non-official configuration**: release-only speed
  optimizations (LTO/PGO) are turned off. It is fully functional, but the binary
  is a little larger and not as speed-tuned as a commercial release build would
  be. Everything works; it's just not squeezed for maximum benchmark numbers.

## Build from source

You can build T3dmium yourself. This repository does not contain Chromium
source — it is a **patch set**, build configuration, and tooling that fetch the
pinned Chromium release, apply the patches, and build with gn/ninja.

Building Chromium is a heavy, multi-hour job (roughly 100 GB of free disk, plenty
of RAM, and a real toolchain). See [BUILDING.md](BUILDING.md) for the full
prerequisites and the exact commands.

## How it's built

T3dmium follows the **patch-set model** pioneered by
[ungoogled-chromium](https://github.com/ungoogled-software/ungoogled-chromium):
rather than forking and maintaining a whole copy of Chromium, it keeps a curated
series of patches plus build flags that are applied on top of a specific,
**pinned** upstream Chromium release. This keeps the changes reviewable and makes
it clear exactly what has been altered and why.

- **Pinned to Chromium 150.0.7871.46.** A fixed pin means reproducible builds and
  no surprise upstream changes to browser behavior. See
  [`chromium_version.txt`](chromium_version.txt).
- **Real Chrome engine** → real performance, real web compatibility, and support
  for standard Chrome extensions.

## Credits

- **[ungoogled-chromium](https://github.com/ungoogled-software/ungoogled-chromium)**
  — the de-Google patch set and tooling model T3dmium builds on. Licensed
  BSD-3-Clause, © The ungoogled-chromium Authors.
- **[The Chromium Project](https://www.chromium.org/)** — the underlying browser
  engine, licensed BSD.
- **Studied prior art:** [Brave](https://brave.com/) and
  [Cromite](https://github.com/uazo/cromite) were valuable references for how a
  privacy-respecting Chromium can be assembled. T3dmium is an independent project
  and not affiliated with either.

See [NOTICE](NOTICE) for attribution details.

## License

BSD-3-Clause. See [LICENSE](LICENSE).

## Maintainer

T3dmium is maintained by **Ted Roubour** ([@t3dboy](https://github.com/t3dboy)).
Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md).
