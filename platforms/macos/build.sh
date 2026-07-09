#!/usr/bin/env bash
# Full macOS build for Apple Silicon: fetch pinned Chromium, apply patches,
# assemble the toolchain, build, and package T3dmium.dmg.
#
# This encodes the complete, tested recipe. The official Chromium source
# tarball is produced on Linux and ships Linux host tools, so this script
# swaps in the macOS/arm64 toolchain (clang, rust, gn, ninja, node, esbuild)
# at the versions the pin's DEPS names, and applies the macOS build patches.
#
# Requirements (see ../../BUILDING.md):
#   * Apple Silicon Mac, macOS 12+
#   * FULL Xcode (not just Command Line Tools) + its Metal Toolchain component
#   * ~100 GB free disk on the build volume, 16 GB RAM minimum
#   * hours of build time on a first build
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
BUILD="$REPO_ROOT/build"
SRC="$BUILD/src"
DEPOT="$BUILD/depot_tools"
OUT="out/Default"
VERSION="$(cat chromium_version.txt)"

log() { printf '\n==> %s\n' "$*"; }

# --- 1. Environment checks --------------------------------------------------
log "Checking environment"
if ! xcode-select -p 2>/dev/null | grep -q "Xcode.app"; then
  echo "error: full Xcode is required. Install it, then run:" >&2
  echo "  sudo xcode-select -s /Applications/Xcode.app/Contents/Developer" >&2
  echo "  sudo xcodebuild -license accept" >&2
  exit 1
fi
if ! xcrun metal --version >/dev/null 2>&1; then
  log "Metal Toolchain missing; downloading (Xcode 16+ ships it separately)"
  xcodebuild -downloadComponent MetalToolchain
fi

# --- 2. Fetch + unpack Chromium --------------------------------------------
log "Fetching pinned Chromium $VERSION"
python3 tools/fetch.py retrieve
[ -d "$SRC" ] || python3 tools/fetch.py unpack

# --- 3. depot_tools (provides cipd, python3.11, download helpers) ----------
log "Bootstrapping depot_tools"
[ -d "$DEPOT" ] || git clone --depth=1 \
  https://chromium.googlesource.com/chromium/tools/depot_tools.git "$DEPOT"
export DEPOT_TOOLS_UPDATE=0
export CIPD_CACHE_DIR="$BUILD/.cipd_cache"
# depot_tools' bundled Python 3.11 MUST precede system python3 (3.9): several
# build scripts use 3.10+ syntax. Its bin dir is created on first gclient run.
"$DEPOT/gclient" --version >/dev/null 2>&1 || true
export PATH="$DEPOT/python-bin:$DEPOT:$PATH"

# --- 4. Patches -------------------------------------------------------------
log "Applying core patch series"
python3 tools/apply_patches.py apply
log "Applying macOS build patches"
while IFS= read -r p; do
  [ -z "$p" ] || [ "${p#\#}" != "$p" ] && continue
  patch -p1 --ignore-whitespace --no-backup-if-mismatch --forward \
    -i "platforms/macos/patches/$p" -d "$SRC" >/dev/null
done < platforms/macos/patches/series

# --- 5. Branding overlay (icons; product name comes from the patch) --------
log "Overlaying branding icons"
cp -R branding/theme-overlay/* "$SRC/"

# --- 6. Toolchain: swap Linux host tools for macOS/arm64 -------------------
log "Assembling macOS/arm64 toolchain at pinned versions"
cd "$SRC"

# clang + rust: fetch the mac-arm64 toolchains and write revision stamps.
python3 tools/clang/scripts/update.py
python3 tools/rust/update_rust.py

# gn: CIPD package pinned by DEPS gn_version.
GN_VER="$(python3 -c "import re;print(re.search(r\"'gn_version': '([^']+)'\", open('DEPS').read()).group(1))")"
printf 'gn/gn/mac-arm64 %s\n' "$GN_VER" | cipd ensure -root buildtools/mac -ensure-file -

# ninja: CIPD package pinned by DEPS ninja_package/ninja_version.
NINJA_VER="$(python3 -c "import re;print(re.search(r\"'ninja_version': '([^']+)'\", open('DEPS').read()).group(1))")"
printf 'infra/3pp/tools/ninja/mac-arm64 %s\n' "$NINJA_VER" | cipd ensure -root third_party/ninja -ensure-file -

# node: GCS object pinned by DEPS (src/third_party/node/mac_arm64).
NODE_OBJ="$(python3 -c "
import re,sys
d=open('DEPS').read()
b=d[d.index(\"'src/third_party/node/mac_arm64'\"):]
print(re.search(r\"'object_name': '([0-9a-f]+)'\", b).group(1))")"
mkdir -p third_party/node/mac_arm64
curl -sfL "https://storage.googleapis.com/chromium-nodejs/$NODE_OBJ" \
  -o third_party/node/mac_arm64/node-darwin-arm64.tar.gz
tar -xzf third_party/node/mac_arm64/node-darwin-arm64.tar.gz -C third_party/node/mac_arm64/

# esbuild: CIPD, pinned in devtools-frontend's own DEPS.
ESBUILD_VER="$(python3 -c "import re;print(re.search(r\"esbuild/\\\$\{\{platform\}\}',\s*'version': '([^']+)'\", open('third_party/devtools-frontend/src/DEPS').read()).group(1))" 2>/dev/null || echo "version:3@0.25.1.chromium.2")"
printf 'infra/3pp/tools/esbuild/mac-arm64 %s\n' "$ESBUILD_VER" \
  | cipd ensure -root third_party/devtools-frontend/src/third_party/esbuild -ensure-file -

# llvm-otool / llvm-nm: not in the minimal clang package; the mac linker
# driver needs them. Point at the system tools (compatible for its uses).
LLVMBIN="third_party/llvm-build/Release+Asserts/bin"
ln -sf /usr/bin/otool "$LLVMBIN/llvm-otool"
ln -sf /usr/bin/nm    "$LLVMBIN/llvm-nm"

# --- 7. Configure -----------------------------------------------------------
log "Configuring (gn gen)"
mkdir -p "$OUT"
cat "$REPO_ROOT/flags.gn" "$REPO_ROOT/platforms/macos/flags.macos.gn" > "$OUT/args.gn"
gn gen "$OUT" --fail-on-unused-args

# --- 8. Build ---------------------------------------------------------------
log "Building (ninja) — this takes hours"
JOBS="${NINJA_JOBS:-6}"   # modest default: safe for 16 GB RAM + slow disks
third_party/ninja/ninja -j "$JOBS" -C "$OUT" chrome

# --- 9. Package -------------------------------------------------------------
log "Packaging DMG"
"$REPO_ROOT/platforms/macos/create_dmg.sh"
log "Done. See build/T3dmium-$VERSION-arm64.dmg"
