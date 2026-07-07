# macOS packaging

Packaging and signing for the macOS build (arm64 and x86_64). The build
itself is platform-neutral (`tools/build.py`); this directory adds:

- `create_dmg.sh` — assemble `T3dmium.app` from the ninja output and wrap it
  in a DMG (Phase 5)
- `entitlements/` — codesigning entitlements (Phase 5)
- signing documentation: ad-hoc signing for local/dev builds
  (`codesign --force --deep --sign -`), Developer ID + notarization
  (`xcrun notarytool`, `xcrun stapler`) for releases (Phase 5)

Until Phase 5 lands, see BUILDING.md for the build walkthrough.
