# Building T3dmium

This document describes how to build T3dmium from source on macOS and
Windows. Both platforms are first-class targets with equal priority; macOS is
the primary test platform. **Linux is a stretch goal and is not yet
supported.**

Read the requirements section honestly before you start — building Chromium
is one of the heaviest open-source builds there is.

## Requirements (read this first)

- **Disk:** roughly **100 GB free**. The source tarball, extracted tree,
  and build output are all large. `tools/fetch.py check` verifies your free
  space before you download anything.
- **RAM:** **16 GB minimum, 32 GB recommended.** Linking Chromium with less
  than 16 GB will swap heavily or fail outright.
- **Time:** a first build takes **several hours even on fast hardware**
  (e.g. an 8+ core machine). Plan accordingly. Incremental rebuilds are much
  faster, and ccache/reclient can help further (see
  [Speeding up rebuilds](#speeding-up-rebuilds)).
- **Python 3** (3.10 or newer recommended) for the tooling in `tools/`.
- **Network:** the pinned Chromium release tarball is several gigabytes.

### macOS

- macOS **12 or later**.
- **Full Xcode** (from the App Store or Apple Developer site) with the
  current macOS SDK. The Command Line Tools alone are **not** sufficient —
  the Chromium build requires the full SDK and toolchain that ship with
  Xcode.
- Targets: **arm64 (Apple Silicon)** and **x86_64**.

### Windows

- **Visual Studio 2022** with the **Desktop development with C++** workload.
- The **Windows SDK** (installable via the Visual Studio installer).

## How the build works

This repository does not contain Chromium source. It contains:

- `chromium_version.txt` — the pinned Chromium version (currently
  **150.0.7871.46**, tracking ungoogled-chromium's pin);
- `downloads.ini` — where to fetch the pinned source tarball and its
  checksum;
- `patches/` + `patches/series` — the quilt-style patch set;
- `pruning.list`, `domain_substitution.list`, `domain_regex.list` — files to
  remove and domains to substitute in the source tree;
- `flags.gn` — the GN build arguments;
- `tools/` — Python tooling that drives the whole process.

The flow is: **fetch** the pinned tarball → **unpack** it into `build/src` →
**apply patches** → **build** with gn/ninja.

## Tooling reference

```
python3 tools/fetch.py check                # verify tarball URL/size and your free disk, no download
python3 tools/fetch.py retrieve             # download + sha256-verify into build/download_cache
python3 tools/fetch.py unpack               # extract into build/src
python3 tools/apply_patches.py apply        # apply patches/series to build/src (GNU patch -p1)
python3 tools/apply_patches.py apply --dry-run
python3 tools/validate_patches.py --remote  # validate patches against pinned sources fetched from chromium.googlesource.com (no local tree needed)
python3 tools/build.py                      # depot_tools bootstrap, flags.gn -> args.gn, gn gen, ninja
python3 tools/check_conventions.py          # repo lint: patch headers, series consistency
```

`tools/validate_patches.py --remote` is useful when working on patches: it
checks every patch against the pinned sources fetched directly from
chromium.googlesource.com, so you do not need a local source tree at all.

## macOS walkthrough

1. **Install Xcode.** Install full Xcode (not just Command Line Tools) and
   make sure the active developer directory points at it:

   ```
   xcode-select -p          # should print .../Xcode.app/Contents/Developer
   sudo xcode-select -s /Applications/Xcode.app
   xcodebuild -version
   ```

   Launch Xcode at least once so it can finish installing its components,
   and accept the license if prompted (`sudo xcodebuild -license accept`).

2. **Clone the repository:**

   ```
   git clone https://github.com/t3dboy/t3dmium.git
   cd t3dmium
   ```

3. **Check prerequisites** (verifies the tarball URL/size and your free
   disk, downloads nothing):

   ```
   python3 tools/fetch.py check
   ```

4. **Download and verify the source tarball** (sha256-verified into
   `build/download_cache`):

   ```
   python3 tools/fetch.py retrieve
   ```

5. **Unpack** into `build/src`:

   ```
   python3 tools/fetch.py unpack
   ```

6. **Apply the patch set.** You can dry-run first:

   ```
   python3 tools/apply_patches.py apply --dry-run
   python3 tools/apply_patches.py apply
   ```

7. **Build.** This bootstraps depot_tools, converts `flags.gn` into
   `args.gn`, runs `gn gen`, and then ninja:

   ```
   python3 tools/build.py
   ```

   This is the long step — expect several hours on a first build.

8. **Sign the app for local use.** For a local build, ad-hoc codesigning is
   fine:

   ```
   codesign --force --deep --sign - path/to/T3dmium.app
   ```

   Release builds require real signing and notarisation — a Developer ID
   certificate, `xcrun notarytool`, and `stapler` — which is documented in
   `platforms/macos/`.

Both arm64 (Apple Silicon) and x86_64 are supported build targets.

## Windows walkthrough

1. **Install Visual Studio 2022** with the *Desktop development with C++*
   workload and the Windows SDK (select it in the Visual Studio installer).

2. **Install Python 3** and make sure `python3` (or `py -3`) is on your
   `PATH`.

3. **Clone the repository:**

   ```
   git clone https://github.com/t3dboy/t3dmium.git
   cd t3dmium
   ```

4. **Check prerequisites:**

   ```
   python3 tools/fetch.py check
   ```

5. **Download, verify, and unpack the source:**

   ```
   python3 tools/fetch.py retrieve
   python3 tools/fetch.py unpack
   ```

6. **Apply the patch set:**

   ```
   python3 tools/apply_patches.py apply --dry-run
   python3 tools/apply_patches.py apply
   ```

7. **Build:**

   ```
   python3 tools/build.py
   ```

   The build script locates your Visual Studio and Windows SDK
   installations, bootstraps depot_tools, generates `args.gn` from
   `flags.gn`, and runs gn/ninja. As on macOS, the first build takes several
   hours.

8. **Build the installer (optional).** The Windows installer is built with
   NSIS; the scripts and instructions live in `platforms/windows/`.

## Speeding up rebuilds

- **ccache** (macOS) or a compatible compiler cache can dramatically shorten
  rebuilds after patch changes.
- **reclient** (remote execution) helps if you have access to a compatible
  remote build cluster.

Neither is required — they only help iteration speed.

## CI builds

Full browser builds exceed the limits of free GitHub-hosted runners in both
time and disk. **Self-hosted runners are the realistic path** for CI release
builds; see `.github/workflows/release-build.yml` for the release build
workflow. The lighter PR checks (patch validation, convention linting) run
fine on hosted runners.

## Troubleshooting

- **`fetch.py check` fails on disk space:** free up space or point the build
  at a larger volume. Do not skip this check — running out of disk hours
  into a build is the most common failure mode.
- **Patches fail to apply:** make sure `build/src` is a clean unpack of the
  pinned version in `chromium_version.txt`. If you have modified the tree,
  re-run `tools/fetch.py unpack` and apply again. Use
  `tools/validate_patches.py --remote` to check whether a patch itself is
  stale against the pinned sources.
- **macOS build errors mentioning missing SDK or toolchain:** you are
  probably building against the Command Line Tools instead of full Xcode.
  Re-check `xcode-select -p`.
