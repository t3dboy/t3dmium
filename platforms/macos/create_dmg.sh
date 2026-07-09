#!/usr/bin/env bash
# Assemble T3dmium.app from the ninja output and wrap it in a DMG.
#
# Local/dev builds are ad-hoc signed (no Apple Developer account needed).
# For distributable, notarized builds see SIGNING.md and set the
# MACOS_CERTIFICATE_NAME / notarization environment variables.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARCH="${1:-$(uname -m)}"
OUT="$REPO_ROOT/build/src/out/Default"
VERSION="$(cat "$REPO_ROOT/chromium_version.txt")"
# With the branding patch applied, ninja emits T3dmium.app directly; fall
# back to Chromium.app if building without branding.
APP_SRC="$OUT/T3dmium.app"
[ -d "$APP_SRC" ] || APP_SRC="$OUT/Chromium.app"
APP_NAME="T3dmium.app"
STAGE="$REPO_ROOT/build/dmg-stage"
DMG="$REPO_ROOT/build/T3dmium-$VERSION-$ARCH.dmg"

if [ ! -d "$APP_SRC" ]; then
  echo "error: $APP_SRC not found. Run the build first." >&2
  exit 1
fi

echo "==> Staging $APP_NAME"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP_SRC" "$STAGE/$APP_NAME"
ln -s /Applications "$STAGE/Applications"

echo "==> Signing"
ENTITLEMENTS="$REPO_ROOT/platforms/macos/entitlements/app.entitlements"
if [ -n "${MACOS_CERTIFICATE_NAME:-}" ]; then
  echo "    Developer ID: $MACOS_CERTIFICATE_NAME"
  codesign --force --deep --options runtime \
    --entitlements "$ENTITLEMENTS" \
    --sign "$MACOS_CERTIFICATE_NAME" "$STAGE/$APP_NAME"
else
  echo "    ad-hoc (local/dev; not distributable)"
  codesign --force --deep --sign - \
    --entitlements "$ENTITLEMENTS" "$STAGE/$APP_NAME"
fi

echo "==> Building DMG: $DMG"
rm -f "$DMG"
hdiutil create -volname "T3dmium $VERSION" -srcfolder "$STAGE" \
  -ov -format UDZO "$DMG"

if [ -n "${MACOS_CERTIFICATE_NAME:-}" ] && \
   [ -n "${PROD_MACOS_NOTARIZATION_APPLE_ID:-}" ]; then
  echo "==> Notarizing (see SIGNING.md)"
  xcrun notarytool submit "$DMG" \
    --apple-id "$PROD_MACOS_NOTARIZATION_APPLE_ID" \
    --team-id "$PROD_MACOS_NOTARIZATION_TEAM_ID" \
    --password "$PROD_MACOS_NOTARIZATION_PWD" --wait
  xcrun stapler staple "$DMG"
fi

echo "==> DMG ready: $DMG"
