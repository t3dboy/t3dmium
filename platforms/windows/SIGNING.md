# Windows code signing

Windows does not require signing to run a locally built browser, but
unsigned installers trigger SmartScreen warnings on other machines. For
distributable builds, sign both `chrome.exe` and the installer with an
Authenticode certificate (an EV certificate avoids SmartScreen reputation
warm-up).

## Signing the build

Using `signtool` from the Windows SDK, with a timestamp so signatures remain
valid after the certificate expires:

```powershell
$files = @("build\src\out\Default\chrome.exe", "build\T3dmium-<version>-setup.exe")
foreach ($f in $files) {
  signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 `
    /n "Your Certificate Subject Name" $f
}
```

For a certificate stored in a PFX file instead of the certificate store,
replace `/n "…"` with `/f cert.pfx /p <password>`.

## Reproducible builds

As on macOS, the build inputs are pinned (`chromium_version.txt` +
`downloads.ini` sha256 + `patches/series` + `flags.gn`). Signing is the last
step and does not alter the compiled payload, so two builders can compare
their unsigned `chrome.exe` to confirm identical output before signing.
