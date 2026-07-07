# macOS signing and notarization

Two signing paths, chosen automatically by `create_dmg.sh` based on
environment variables.

## Local / development builds (default)

No Apple Developer account required. The app is **ad-hoc signed**:

```sh
codesign --force --deep --sign - --entitlements entitlements/app.entitlements T3dmium.app
```

Ad-hoc-signed apps run on the machine that built them. Gatekeeper will warn
on other machines — that is expected; ad-hoc builds are not for
distribution.

## Release builds (Developer ID + notarization)

Set these environment variables, then run `build.sh` (or `create_dmg.sh`
directly):

| Variable | Meaning |
| --- | --- |
| `MACOS_CERTIFICATE_NAME` | Developer ID Application certificate common name |
| `PROD_MACOS_NOTARIZATION_APPLE_ID` | Apple ID used for notarization |
| `PROD_MACOS_NOTARIZATION_TEAM_ID` | Developer Team ID |
| `PROD_MACOS_NOTARIZATION_PWD` | App-specific password (or keychain profile) |

The flow `create_dmg.sh` runs:

1. `codesign --force --deep --options runtime --entitlements … --sign "$MACOS_CERTIFICATE_NAME"`
   — hardened-runtime signing of the app bundle and its nested helpers.
2. `hdiutil create … -format UDZO` — build the DMG.
3. `xcrun notarytool submit … --wait` — upload to Apple and wait for the
   ticket.
4. `xcrun stapler staple` — attach the notarization ticket to the DMG so it
   validates offline.

## Reproducible builds

The build inputs are pinned: `chromium_version.txt` + the sha256 in
`downloads.ini` fix the source; `patches/series` fixes the patch set;
`flags.gn` fixes the build configuration. Given the same Xcode/SDK version,
the compiled output is intended to be reproducible. Signing and notarization
are applied after the reproducible step, so two builders can compare the
unsigned `.app` payloads to verify they built the same bits.
