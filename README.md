# T3dmium

[![pr-check](https://github.com/t3dboy/t3dmium/actions/workflows/pr-check.yml/badge.svg)](https://github.com/t3dboy/t3dmium/actions/workflows/pr-check.yml)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](LICENSE)

T3dmium is a privacy-first, open-source web browser based on Chromium. It aims
to deliver the Chromium engine — its rendering, performance, and web
compatibility — with every form of telemetry, analytics, and background
"phone home" traffic removed.

## Why

Chromium is an excellent browser engine wrapped in a large amount of
Google-facing plumbing: metrics uploads, field-trial fetches, component
updater pings, crash reporting, promotional surfaces, and more. Most
"private" Chromium derivatives reduce this traffic; T3dmium's goal is to
eliminate it and to *prove* the elimination.

## Privacy guarantees

- **Zero telemetry or analytics.** No metrics, crash reports, usage data, or
  experiment pings are sent to Google or any third party. Ever.
- **No background traffic.** The only network traffic the browser generates
  is user-initiated: navigating to a page, an opt-in update check, or a
  user-requested extension install.
- **Verified, not promised.** An automated network audit harness (in
  [`audit/`](audit/), built on mitmproxy) runs in CI and fails the build if
  any non-user-initiated request leaves the machine.

The full commitments, and a service-by-service table of how each piece of
Google/third-party plumbing is handled, are in [PRIVACY.md](PRIVACY.md).

## Project status

**Early development.** The current focus is the patch set and build tooling —
fetching a pinned Chromium release, applying patches, and building
reproducibly on macOS and Windows. There are **no binary releases yet**;
installable, signed builds will come later. If you want to run T3dmium today,
you will need to build it yourself (see below).

macOS and Windows are first-class targets with equal priority; macOS is the
primary test platform. Linux is a stretch goal and not yet supported.

## Building

This repository does not contain Chromium source. It contains a patch set,
build configuration, and Python tooling that fetch the pinned Chromium
release (see [`chromium_version.txt`](chromium_version.txt)), apply the
patches, and build with gn/ninja:

```
python3 tools/fetch.py check
python3 tools/fetch.py retrieve
python3 tools/fetch.py unpack
python3 tools/apply_patches.py apply
python3 tools/build.py
```

Building Chromium is a heavy job: roughly 100 GB of free disk, 16 GB RAM
minimum, and several hours for a first build. See
[BUILDING.md](BUILDING.md) for full requirements and step-by-step
walkthroughs for macOS and Windows.

## Repository layout

| Path | Contents |
| --- | --- |
| `patches/` | Quilt-style patch set applied to the Chromium tree (`series` defines order) |
| `flags.gn` | GN build arguments |
| `downloads.ini` | Pinned source tarball URLs and checksums |
| `pruning.list` | Binary/unwanted files removed from the source tree |
| `domain_substitution.list`, `domain_regex.list` | Domain substitution rules |
| `tools/` | Python tooling: fetch, patch, build, validate |
| `audit/` | mitmproxy-based network audit harness (runs in CI) |
| `sync/` | Optional self-hosted, zero-knowledge encrypted sync server |
| `branding/` | Icon source and generator; user-agent policy |
| `platforms/macos/`, `platforms/windows/` | Platform packaging: signing/notarisation, NSIS installer |
| `docs/adr/` | Architecture decision records |
| `chromium_version.txt` | Pinned Chromium version |
| `.github/workflows/` | CI: PR checks and release builds |

## Development status by area

Everything except the compiled binary is verifiable without a build host;
those parts are validated in CI on every change. The final compile is gated
only by hardware (see [BUILDING.md](BUILDING.md)).

| Area | Status | Verified by |
| --- | --- | --- |
| De-Google patch set (109 patches) | Applies cleanly to the pin | `tools/validate_patches.py` in CI |
| Network audit harness | Detection logic tested | `audit/tests` (self-test) in CI |
| Privacy defaults | DNT + GPC patch validated | `tools/validate_patches.py` |
| Ad/tracker blocking | Engine decided, lists pinned | ADR-0005; `fetch.py check` |
| Branding + installers | Assets + packaging scripts | script review |
| Self-hosted sync | Server + tests passing | `sync/tests` (live round-trip) in CI |
| Compiled browser + signed release | Needs ~100 GB disk + Xcode / self-hosted runner | build host |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for patch conventions, validation
requirements, and the privacy bar every change must clear. Unexpected network
traffic is treated as a serious bug — please report it with the
[privacy leak template](.github/ISSUE_TEMPLATE/privacy_leak.md).

## Credits

T3dmium builds on the work of others and would not exist without them:

- **[ungoogled-chromium](https://github.com/ungoogled-software/ungoogled-chromium)**
  (BSD-3-Clause, © The ungoogled-chromium Authors) — T3dmium's patch set and
  fork model build directly on ungoogled-chromium's patches and tooling
  design, and our Chromium version pin tracks theirs.
- **[Chromium](https://www.chromium.org/)** (BSD) — the browser itself.
- **[Brave](https://github.com/brave/brave-browser)** and
  **[Cromite](https://github.com/uazo/cromite)** — prior art we study for
  privacy hardening approaches.

## License

T3dmium's own code and patches are licensed under the
[BSD-3-Clause license](LICENSE). Chromium and the ungoogled-chromium patch
set carry their own BSD licenses; see their respective projects for details.

Maintained by Ted Roubour ([@t3dboy](https://github.com/t3dboy)).
