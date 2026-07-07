; NSIS installer for T3dmium (Windows x64).
; Build with:  makensis /DVERSION=<x.y.z.w> installer.nsi
; Expects the build output under ..\..\build\src\out\Default.

!ifndef VERSION
  !define VERSION "0.0.0.0"
!endif

!define APPNAME "T3dmium"
!define PUBLISHER "Ted Roubour"
!define BUILDDIR "..\..\build\src\out\Default"

Name "${APPNAME} ${VERSION}"
OutFile "..\..\build\T3dmium-${VERSION}-setup.exe"
Unicode True
InstallDir "$PROGRAMFILES64\${APPNAME}"
InstallDirRegKey HKLM "Software\${APPNAME}" "InstallDir"
RequestExecutionLevel admin

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  ; Ship the browser payload. The build emits chrome.exe and its resources;
  ; they are installed under the T3dmium product name.
  File /r "${BUILDDIR}\*.exe"
  File /r "${BUILDDIR}\*.dll"
  File /r "${BUILDDIR}\*.pak"
  File /r "${BUILDDIR}\*.bin"
  File /r "${BUILDDIR}\locales"

  CreateShortcut "$SMPROGRAMS\${APPNAME}.lnk" "$INSTDIR\chrome.exe"
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\chrome.exe"

  WriteRegStr HKLM "Software\${APPNAME}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "DisplayName" "${APPNAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "Publisher" "${PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "UninstallString" "$INSTDIR\uninstall.exe"
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\${APPNAME}.lnk"
  Delete "$DESKTOP\${APPNAME}.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
  DeleteRegKey HKLM "Software\${APPNAME}"
SectionEnd
