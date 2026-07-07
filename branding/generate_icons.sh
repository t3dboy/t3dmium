#!/usr/bin/env bash
# Generate platform icon files from branding/icon.svg.
#
# Produces:
#   branding/out/icon.icns   (macOS app bundle)
#   branding/out/icon.ico    (Windows exe / installer)
#   branding/out/icon_<n>.png (raster sizes; consumed by the branding patch
#                              for chrome/app/theme/)
#
# Requires one SVG rasterizer (rsvg-convert or Inkscape) plus, on macOS,
# iconutil (bundled with Xcode CLT), and ImageMagick for the .ico. These are
# packaging-time tools, not build dependencies.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SVG="$HERE/icon.svg"
OUT="$HERE/out"
mkdir -p "$OUT"

rasterize() {  # rasterize <size> <outfile>
  local size="$1" outfile="$2"
  if command -v rsvg-convert >/dev/null; then
    rsvg-convert -w "$size" -h "$size" "$SVG" -o "$outfile"
  elif command -v inkscape >/dev/null; then
    inkscape "$SVG" --export-type=png -w "$size" -h "$size" -o "$outfile"
  else
    echo "error: need rsvg-convert or inkscape to rasterize the SVG" >&2
    exit 1
  fi
}

SIZES=(16 24 32 48 64 128 256 512)
for s in "${SIZES[@]}"; do
  rasterize "$s" "$OUT/icon_${s}.png"
done

# macOS .icns via iconutil
if command -v iconutil >/dev/null; then
  ICONSET="$OUT/icon.iconset"
  rm -rf "$ICONSET"; mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    cp "$OUT/icon_${s}.png" "$ICONSET/icon_${s}x${s}.png"
    d=$((s*2)); [ -f "$OUT/icon_${d}.png" ] && \
      cp "$OUT/icon_${d}.png" "$ICONSET/icon_${s}x${s}@2x.png" || true
  done
  iconutil -c icns "$ICONSET" -o "$OUT/icon.icns"
fi

# Windows .ico via ImageMagick
if command -v magick >/dev/null || command -v convert >/dev/null; then
  IM="$(command -v magick || command -v convert)"
  "$IM" "$OUT/icon_16.png" "$OUT/icon_32.png" "$OUT/icon_48.png" \
        "$OUT/icon_256.png" "$OUT/icon.ico"
fi

echo "==> Icons written to $OUT"
