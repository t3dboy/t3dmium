# Windows packaging

Packaging for the Windows x64 build. The build itself is platform-neutral
(`tools/build.py`, run from a Visual Studio developer prompt); this directory
adds:

- `build.ps1` — convenience wrapper: environment checks, build, and
  `-Package` to produce the installer (Phase 5)
- `installer.nsi` — NSIS installer script (Phase 5)

Until Phase 5 lands, see BUILDING.md for the build walkthrough.
