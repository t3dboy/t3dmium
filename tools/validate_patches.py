#!/usr/bin/env python3
"""Validate that patches apply against the pinned Chromium sources.

With --remote (the default and currently only mode), every file a patch
touches is fetched from chromium.googlesource.com at the tag in
chromium_version.txt, placed in a temporary tree, and the patch is dry-run
with GNU patch -p1. This proves hunk context matches the real pinned sources
without needing a local Chromium checkout (~50 GB).

Fetched files are cached in build/gitiles_cache/<version>/ so repeated runs
are cheap.

Usage:
  validate_patches.py --remote                 # validate everything in series
  validate_patches.py --remote patches/privacy/foo.patch [...]
"""

import argparse
import base64
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from _common import (BUILD_DIR, PATCHES_DIR, chromium_version, die,
                     read_series)

GITILES_BASE = ("https://chromium.googlesource.com/chromium/src/+/"
                "refs/tags/{version}/{path}?format=TEXT")

OLD_FILE_RE = re.compile(r"^--- (\S+)")
NEW_FILE_RE = re.compile(r"^\+\+\+ (\S+)")


def parse_patch_targets(patch_path):
    """Return the set of pre-image paths (relative, a/ stripped) the patch
    expects to exist. Files created by the patch (--- /dev/null) are skipped.
    """
    targets = set()
    for line in patch_path.read_text(encoding="utf-8").splitlines():
        match = OLD_FILE_RE.match(line)
        if not match:
            continue
        name = match.group(1)
        if name == "/dev/null":
            continue
        if name.startswith("a/"):
            name = name[2:]
        # Strip a possible timestamp column is unnecessary: \S+ already
        # stopped at whitespace.
        targets.add(name)
    return targets


def fetch_pinned_file(rel_path, version, cache_root):
    """Fetch one source file at the pinned tag via gitiles; return bytes or
    None if the file does not exist at the pin."""
    cache_path = cache_root / rel_path
    if cache_path.exists():
        return cache_path.read_bytes()
    url = GITILES_BASE.format(version=version,
                              path=urllib.parse.quote(rel_path))
    try:
        with urllib.request.urlopen(url) as response:
            content = base64.b64decode(response.read())
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(content)
    return content


def validate_patch(patch_path, version, cache_root):
    """Fetch the patch's pre-image files and dry-run GNU patch. Returns a
    list of problem strings (empty = valid)."""
    problems = []
    targets = parse_patch_targets(patch_path)
    with tempfile.TemporaryDirectory(prefix="t3dmium-validate-") as tmp:
        tree = Path(tmp)
        for rel_path in sorted(targets):
            content = fetch_pinned_file(rel_path, version, cache_root)
            if content is None:
                problems.append(
                    "{}: file not present at pin: {}".format(
                        patch_path.name, rel_path))
                continue
            local = tree / rel_path
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(content)
        if problems:
            return problems
        result = subprocess.run(
            ["patch", "-p1", "--ignore-whitespace", "--dry-run", "--forward",
             "-i", str(patch_path.resolve()), "-d", str(tree)],
            capture_output=True, text=True)
        if result.returncode != 0:
            problems.append("{}: does not apply to pinned sources:\n{}{}"
                            .format(patch_path.name, result.stdout,
                                    result.stderr))
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", action="store_true", default=True,
                        help="fetch pinned sources from "
                             "chromium.googlesource.com (default)")
    parser.add_argument("patches", nargs="*",
                        help="specific .patch files; default: all of series")
    args = parser.parse_args()

    version = chromium_version()
    cache_root = BUILD_DIR / "gitiles_cache" / version

    if args.patches:
        patch_paths = [Path(p) for p in args.patches]
    else:
        patch_paths = [PATCHES_DIR / entry for entry in read_series()]
    if not patch_paths:
        print("series is empty; nothing to validate")
        return 0

    all_problems = []
    for patch_path in patch_paths:
        if not patch_path.is_file():
            die("no such patch: {}".format(patch_path))
        problems = validate_patch(patch_path, version, cache_root)
        print("{:6} {}".format("FAILED" if problems else "ok",
                               patch_path.name))
        all_problems.extend(problems)
    if all_problems:
        print("\nvalidation failures:")
        for problem in all_problems:
            print("  {}".format(problem))
        return 1
    print("\nall {} patch(es) valid against Chromium {}".format(
        len(patch_paths), version))
    return 0


if __name__ == "__main__":
    sys.exit(main())
