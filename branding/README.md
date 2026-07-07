# Branding

Source assets and policy for T3dmium's identity.

- `icon.svg` — the master icon (a privacy shield around a browser orbit with
  the "T3d" wordmark). Everything else is generated from it.
- `generate_icons.sh` — renders `icon.svg` to the platform icon formats
  (`.icns`, `.ico`, and PNG sizes) under `out/`. Requires a rasterizer
  (rsvg-convert or Inkscape) and, per platform, iconutil / ImageMagick.

## How branding reaches the browser

The generated PNGs and the product name feed the branding patch
(`patches/branding/`), which overrides Chromium's product strings and theme
icons (`chrome/app/theme/…`, the `BRANDING` file). The DMG/installer tooling
in `platforms/` uses `out/icon.icns` and `out/icon.ico`.

## User-agent policy (important, and deliberately hands-off)

T3dmium's user-agent string is **left identical to upstream Chrome's** for
the pinned version. We add **no** product token, no version marker, nothing
that would distinguish a T3dmium user from the very large population of
Chrome users. Announcing a niche browser in every HTTP request is a
fingerprinting signal; blending in is the privacy-preserving choice. This is
achieved by *not* patching the UA — there is intentionally no branding patch
that touches the user-agent code path. See PRIVACY.md.
