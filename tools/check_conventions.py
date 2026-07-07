#!/usr/bin/env python3
"""Repository convention checks, run locally and in CI (pr-check).

Checks:
  * every entry in patches/series exists on disk, and every .patch file under
    patches/ is listed in series (no orphans)
  * every patch: .patch suffix, UTF-8, LF line endings, and a header with
    `Description:` and `Origin:` lines before the first `---` line
  * chromium_version.txt and revision.txt are single non-empty lines
  * downloads.ini entries have url, download_filename, sha256, output_path
"""

import re
import subprocess
import sys

from _common import (PATCHES_DIR, ROOT, chromium_version, read_downloads_ini,
                     read_series, t3dmium_revision)

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


def check_series(problems):
    series = read_series()
    seen = set()
    for entry in series:
        if entry in seen:
            problems.append("series: duplicate entry {}".format(entry))
        seen.add(entry)
        if not entry.endswith(".patch"):
            problems.append("series: {} lacks .patch suffix".format(entry))
        if not (PATCHES_DIR / entry).is_file():
            problems.append("series: entry has no file: {}".format(entry))
    on_disk = {p.relative_to(PATCHES_DIR).as_posix()
               for p in PATCHES_DIR.rglob("*.patch")}
    for orphan in sorted(on_disk - seen):
        problems.append("patch file not listed in series: {}".format(orphan))
    return series


def check_patch_files(problems, series):
    for entry in series:
        path = PATCHES_DIR / entry
        if not path.is_file():
            continue  # already reported
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            problems.append("{}: not valid UTF-8".format(entry))
            continue
        if b"\r\n" in raw:
            problems.append("{}: CRLF line endings".format(entry))
        header_lines = []
        for line in text.splitlines():
            if line.startswith("---"):
                break
            header_lines.append(line)
        header = "\n".join(header_lines)
        for field in ("Description:", "Origin:"):
            if field not in header:
                problems.append("{}: missing `{}` in header (before first "
                                "`---` line)".format(entry, field))


def check_pins(problems):
    if not VERSION_RE.match(chromium_version()):
        problems.append("chromium_version.txt: not a x.y.z.w version")
    if not t3dmium_revision().isdigit():
        problems.append("revision.txt: not an integer")
    for name, item in read_downloads_ini().items():
        for key in ("url", "download_filename", "sha256", "output_path"):
            if key not in item:
                problems.append("downloads.ini [{}]: missing {}".format(
                    name, key))
        sha = item.get("sha256", "")
        if sha and not re.match(r"^[0-9a-f]{64}$", sha):
            problems.append("downloads.ini [{}]: sha256 malformed".format(
                name))


def check_workflows(problems):
    workflows = ROOT / ".github" / "workflows"
    for required in ("pr-check.yml", "release-build.yml"):
        if not (workflows / required).is_file():
            problems.append(".github/workflows/{} missing".format(required))


def main():
    problems = []
    series = check_series(problems)
    check_patch_files(problems, series)
    check_pins(problems)
    check_workflows(problems)
    if problems:
        print("{} convention problem(s):".format(len(problems)))
        for problem in problems:
            print("  {}".format(problem))
        return 1
    print("conventions ok ({} patches in series)".format(len(series)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
