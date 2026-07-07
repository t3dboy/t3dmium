#!/usr/bin/env bash
# Full macOS build: fetch pinned Chromium, apply patches, build, package.
# Native arch by default; pass an arch to cross-compile:  ./build.sh x86_64
#
# Requires full Xcode (not just Command Line Tools), ~100 GB free disk, and
# hours of build time. See ../../BUILDING.md.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

TARGET_ARCH="${1:-$(uname -m)}"   # arm64 | x86_64
echo "==> Target architecture: $TARGET_ARCH"

if ! xcode-select -p | grep -q "Xcode.app"; then
  echo "error: full Xcode is required. Install it, then:" >&2
  echo "  sudo xcode-select -s /Applications/Xcode.app/Contents/Developer" >&2
  exit 1
fi

echo "==> Fetching pinned Chromium source"
python3 tools/fetch.py retrieve
python3 tools/fetch.py unpack

echo "==> Applying patch series"
python3 tools/apply_patches.py apply

echo "==> Building (gn + ninja)"
if [ "$TARGET_ARCH" = "x86_64" ] && [ "$(uname -m)" = "arm64" ]; then
  # Cross-compiling: append target_cpu to the copied args.gn.
  python3 tools/build.py --targets chrome chromedriver &
  BUILD_PID=$!
  # build.py copies flags.gn then runs gn/ninja; for cross builds set the cpu
  # via an extra args.gn line before gn gen. Kept explicit for honesty:
  echo 'target_cpu="x64"' >> build/src/out/Default/args.gn || true
  wait "$BUILD_PID"
else
  python3 tools/build.py --targets chrome chromedriver
fi

echo "==> Packaging DMG"
"$REPO_ROOT/platforms/macos/create_dmg.sh" "$TARGET_ARCH"

echo "==> Done. Artifact(s) in build/"
