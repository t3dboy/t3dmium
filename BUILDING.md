# Building T3dmium

T3dmium is built from a **pinned Chromium release** plus this repository's
patch set, branding, and build configuration. This repo contains no Chromium
source; the tooling fetches it.

Building Chromium is a heavy job. Budget for it.

## Requirements

| | Minimum | Comfortable |
| --- | --- | --- |
| Free disk (build volume) | ~100 GB | 150 GB+ |
| RAM | 16 GB | 32 GB+ |
| First build time | several hours | — |

The first compile takes hours even on fast hardware; on a spinning/USB disk
it can run overnight. Subsequent incremental builds are much faster.

---

## macOS (Apple Silicon)

macOS on Apple Silicon (arm64) is the primary, tested target.

### Prerequisites

1. **Full Xcode** — not just the Command Line Tools. Chromium's build looks
   for the SDK inside `Xcode.app`. After installing:
   ```sh
   sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
   sudo xcodebuild -license accept
   ```
2. **Metal Toolchain** — Xcode 16+ ships it as a separate component (ANGLE
   compiles Metal shaders during the build). `build.sh` downloads it
   automatically if missing, or run it yourself:
   ```sh
   xcodebuild -downloadComponent MetalToolchain
   ```
3. **Python 3** and **git** (git ships with the Command Line Tools).

### Build

One command does everything — fetch, patch, assemble the toolchain, build,
and package:

```sh
./platforms/macos/build.sh
```

The result is `build/T3dmium-<version>-arm64.dmg` (ad-hoc signed).

`build.sh` performs, in order:

1. Verifies full Xcode and the Metal Toolchain.
2. `tools/fetch.py` — download (sha256-verified) and unpack the pinned
   Chromium tarball.
3. Bootstraps `depot_tools` (provides `cipd` and a bundled Python 3.11 that
   several build scripts require).
4. Applies `patches/series`, then the macOS build patches in
   `platforms/macos/patches/series`.
5. Overlays the T3dmium branding icons.
6. **Assembles the macOS/arm64 toolchain.** The official source tarball is
   produced on Linux and ships Linux host binaries, so the script fetches the
   mac-arm64 builds at the versions the pin's `DEPS` names: `clang` and
   `rust` (via Chromium's own `update.py` / `update_rust.py`), `gn`, `ninja`,
   and `esbuild` (via CIPD), and `node` (via Google Cloud Storage). It also
   symlinks `llvm-otool`/`llvm-nm` to the system tools, which the minimal
   clang package omits.
7. `gn gen` with `flags.gn` + `platforms/macos/flags.macos.gn`.
8. `ninja chrome` (set `NINJA_JOBS` to tune parallelism; default 6, chosen to
   be safe on 16 GB RAM and slow disks).
9. Packages the DMG via `platforms/macos/create_dmg.sh`.

### Build configuration notes

- The downloadable release is a **non-official build**
  (`is_official_build=false`, no ThinLTO/PGO). This is deliberate: the
  official build's final link needs 25–40 GB of RAM and OOMs on a 16 GB
  machine. The non-official build is fully functional. On a 32 GB+ host, edit
  `platforms/macos/flags.macos.gn` to set `is_official_build=true` and remove
  the `use_thin_lto` / `enable_precompiled_headers` overrides for an optimized
  release artifact.
- `clang_version="23"` in the macOS flags corrects a stale value in the pin's
  `toolchain.gni` (it says `22`, but the clang the pin fetches is `23`).

### Signing and packaging

Local/dev builds are **ad-hoc signed** — no Apple Developer account needed.
For notarized, distributable builds, see
[platforms/macos/SIGNING.md](platforms/macos/SIGNING.md).

---

## Windows (planned)

Windows is a first-class target in the design, but the automated build is not
yet wired end-to-end. The pieces exist (`platforms/windows/build.ps1`,
`platforms/windows/installer.nsi`). Build from a **Visual Studio 2022** x64
Native Tools prompt with the C++ workload and Windows SDK installed:

```powershell
python tools\fetch.py retrieve
python tools\fetch.py unpack
python tools\apply_patches.py apply
python tools\build.py
platforms\windows\build.ps1 -Package
```

A Windows build cannot be produced from macOS — Chromium has no supported
macOS→Windows cross-compile.

---

## Continuous integration

The per-PR workflow (`.github/workflows/pr-check.yml`) validates patches,
conventions, and the audit-harness self-test — it does **not** do a full
build (that exceeds hosted-runner limits). The full build workflow
(`.github/workflows/release-build.yml`) is written for **self-hosted
runners**; a full Chromium build on a hosted runner will time out.

---

## Troubleshooting

- **"Install Xcode…" from `find_sdk.py`** — you have only Command Line Tools.
  Install full Xcode and run the `xcode-select` / `-license` commands above.
- **`cannot execute tool 'metal'`** — the Metal Toolchain isn't installed;
  run `xcodebuild -downloadComponent MetalToolchain`.
- **`Exec format error` on a toolchain binary** — a Linux host tool slipped
  through; `build.sh` replaces clang/rust/node/esbuild, but if you built
  manually, re-run the toolchain step.
- **Out of memory at the final link** — you are on an official build; switch
  to the non-official flags (default), or lower `NINJA_JOBS`.
- **Download failures** — delete `build/download_cache` and re-run. **Any
  other corruption** — delete `build/src` and re-run.
