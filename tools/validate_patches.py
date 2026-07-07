#!/usr/bin/env python3
"""Validate that the patch series applies to the pinned Chromium sources
without a local Chromium checkout (~50 GB).

Series mode (default, no arguments):
    Walks patches/series in order, building a sparse source tree: every file
    a patch touches is fetched from chromium.googlesource.com at the tag in
    chromium_version.txt the first time it is needed, then patches are
    REALLY applied in sequence — so patches that stack on the same file are
    validated exactly as they will apply at build time.

Isolated mode (explicit patch arguments):
    Each named patch is dry-run against pristine pinned sources. Suitable
    while authoring a new patch; a patch that depends on earlier patches in
    the series may false-fail here — use series mode for the truth.

Fetched files are cached in build/gitiles_cache/<version>/ so repeated runs
are cheap. --offline forbids network fetches (cache only), for CI cache hits.
"""

import argparse
import base64
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from _common import (BUILD_DIR, PATCHES_DIR, chromium_version, die,
                     read_series)
from _deps import fetch_subrepo_file, load_dep_map

GITILES_BASE = ("https://chromium.googlesource.com/chromium/src/+/"
                "refs/tags/{version}/{path}?format=TEXT")
FETCH_RETRIES = 4

OLD_FILE_RE = re.compile(r"^--- (\S+)")


def parse_patch_preimages(patch_path):
    """Paths (a/ stripped) whose current content the patch expects.
    Files the patch creates (--- /dev/null) are excluded."""
    targets = []
    for line in patch_path.read_text(encoding="utf-8").splitlines():
        match = OLD_FILE_RE.match(line)
        if not match:
            continue
        name = match.group(1)
        if name == "/dev/null":
            continue
        if name.startswith("a/"):
            name = name[2:]
        if name not in targets:
            targets.append(name)
    return targets


class PinnedSourceFetcher:
    def __init__(self, version, offline=False):
        self.version = version
        self.offline = offline
        self.cache_root = BUILD_DIR / "gitiles_cache" / version
        self.fetched = 0
        self.cache_hits = 0
        self._dep_map = None

    def dep_map(self):
        if self._dep_map is None:
            if self.offline:
                self._dep_map = {}
            else:
                self._dep_map = load_dep_map(self.version, self.cache_root)
        return self._dep_map

    def _fetch_from_src(self, rel_path):
        url = GITILES_BASE.format(version=self.version,
                                  path=urllib.parse.quote(rel_path))
        for attempt in range(FETCH_RETRIES):
            try:
                with urllib.request.urlopen(url) as response:
                    return base64.b64decode(response.read()), True
            except urllib.error.HTTPError as err:
                if err.code == 404:
                    return None, False  # not in chromium/src; try DEPS
                if err.code in (429, 500, 502, 503) and \
                        attempt < FETCH_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except OSError:
                if attempt < FETCH_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
        return None, False  # pragma: no cover

    def get(self, rel_path):
        """Return file bytes at the pin, or None if genuinely absent. Files
        under a DEPS-managed sub-tree are fetched from that sub-repo at its
        pinned commit."""
        cache_path = self.cache_root / rel_path
        missing_marker = self.cache_root / (rel_path + ".ABSENT")
        if cache_path.exists():
            self.cache_hits += 1
            return cache_path.read_bytes()
        if missing_marker.exists():
            self.cache_hits += 1
            return None
        if self.offline:
            die("--offline but {} is not in the cache".format(rel_path))

        content, found_in_src = self._fetch_from_src(rel_path)
        if not found_in_src:
            content, deps_managed = fetch_subrepo_file(rel_path,
                                                       self.dep_map())
            if not deps_managed and content is None:
                # Genuinely absent from both chromium/src and DEPS.
                missing_marker.parent.mkdir(parents=True, exist_ok=True)
                missing_marker.write_bytes(b"")
                return None
            if content is None:
                missing_marker.parent.mkdir(parents=True, exist_ok=True)
                missing_marker.write_bytes(b"")
                return None
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(content)
        self.fetched += 1
        return content


def run_patch(patch_path, tree, dry_run):
    command = ["patch", "-p1", "--ignore-whitespace", "--forward",
               "--no-backup-if-mismatch", "-i", str(patch_path.resolve()),
               "-d", str(tree)]
    if dry_run:
        command.append("--dry-run")
    return subprocess.run(command, capture_output=True, text=True)


def materialize(fetcher, tree, rel_path, problems, patch_name):
    """Ensure rel_path exists in the sparse tree; fetch it at the pin if a
    previous patch has not already created/modified it."""
    local = tree / rel_path
    if local.exists():
        return
    content = fetcher.get(rel_path)
    if content is None:
        problems.append("{}: pre-image file absent at pin and not created "
                        "by an earlier patch: {}".format(patch_name, rel_path))
        return
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(content)


def validate_series(fetcher):
    series = read_series()
    if not series:
        print("series is empty; nothing to validate")
        return 0
    failures = []
    with tempfile.TemporaryDirectory(prefix="t3dmium-validate-") as tmp:
        tree = Path(tmp)
        for index, entry in enumerate(series, 1):
            patch_path = PATCHES_DIR / entry
            if not patch_path.is_file():
                die("series entry has no file: {}".format(entry))
            problems = []
            for rel_path in parse_patch_preimages(patch_path):
                materialize(fetcher, tree, rel_path, problems, entry)
            if not problems:
                result = run_patch(patch_path, tree, dry_run=False)
                if result.returncode != 0:
                    problems.append("{}: failed to apply:\n{}{}".format(
                        entry, result.stdout, result.stderr))
            print("{:6} [{}/{}] {}".format(
                "FAILED" if problems else "ok", index, len(series), entry))
            failures.extend(problems)
    _summary(fetcher)
    if failures:
        print("\n{} failure(s):".format(len(failures)))
        for problem in failures:
            print("  {}".format(problem))
        return 1
    print("full series ({} patches) applies to Chromium {}".format(
        len(series), fetcher.version))
    return 0


def validate_isolated(fetcher, patch_paths):
    failures = []
    for patch_path in patch_paths:
        if not patch_path.is_file():
            die("no such patch: {}".format(patch_path))
        problems = []
        with tempfile.TemporaryDirectory(prefix="t3dmium-validate-") as tmp:
            tree = Path(tmp)
            for rel_path in parse_patch_preimages(patch_path):
                materialize(fetcher, tree, rel_path, problems,
                            patch_path.name)
            if not problems:
                result = run_patch(patch_path, tree, dry_run=True)
                if result.returncode != 0:
                    problems.append(
                        "{}: does not apply to pristine pinned sources "
                        "(if it stacks on earlier series patches, use "
                        "series mode):\n{}{}".format(
                            patch_path.name, result.stdout, result.stderr))
        print("{:6} {}".format("FAILED" if problems else "ok",
                               patch_path.name))
        failures.extend(problems)
    _summary(fetcher)
    if failures:
        print("\n{} failure(s):".format(len(failures)))
        for problem in failures:
            print("  {}".format(problem))
        return 1
    print("all {} patch(es) valid against Chromium {}".format(
        len(patch_paths), fetcher.version))
    return 0


def _summary(fetcher):
    print("(pinned sources: {} fetched, {} cache hits)".format(
        fetcher.fetched, fetcher.cache_hits))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", action="store_true", default=True,
                        help="fetch pinned sources from "
                             "chromium.googlesource.com (default)")
    parser.add_argument("--offline", action="store_true",
                        help="use only the local gitiles cache; fail on miss")
    parser.add_argument("patches", nargs="*",
                        help="specific .patch files for isolated validation; "
                             "default: sequential validation of the series")
    args = parser.parse_args()

    fetcher = PinnedSourceFetcher(chromium_version(), offline=args.offline)
    if args.patches:
        return validate_isolated(fetcher, [Path(p) for p in args.patches])
    return validate_series(fetcher)


if __name__ == "__main__":
    sys.exit(main())
