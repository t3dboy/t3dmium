<#
.SYNOPSIS
  Full Windows x64 build: fetch pinned Chromium, apply patches, build, and
  optionally package the NSIS installer.

.DESCRIPTION
  Run from a Visual Studio 2022 "x64 Native Tools" developer prompt (so the
  MSVC toolchain and Windows SDK are on PATH). Requires ~100 GB free disk
  and several hours. See ..\..\BUILDING.md.

.PARAMETER Package
  After building, run makensis to produce build\T3dmium-<version>-setup.exe.
#>
param(
  [switch]$Package
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $RepoRoot

if (-not $env:VSINSTALLDIR) {
  Write-Warning "Not in a Visual Studio developer environment. Open an 'x64 Native Tools Command Prompt for VS 2022' and run again."
}

Write-Host "==> Fetching pinned Chromium source"
python tools\fetch.py retrieve
python tools\fetch.py unpack

Write-Host "==> Applying patch series"
python tools\apply_patches.py apply

Write-Host "==> Building (gn + ninja)"
python tools\build.py --targets chrome

if ($Package) {
  Write-Host "==> Building NSIS installer"
  $version = (Get-Content "$RepoRoot\chromium_version.txt").Trim()
  makensis /DVERSION=$version "$PSScriptRoot\installer.nsi"
  Write-Host "==> Installer ready in build\"
}

Write-Host "==> Done."
