#!/usr/bin/env python3
"""Fetch and unpack the pinned Chromium source archives listed in downloads.ini.

Subcommands:
  check     Verify each archive URL is reachable (HTTP HEAD), print its size,
            and compare the projected space requirement against free disk.
            Downloads nothing.
  retrieve  Download each archive into build/download_cache and verify sha256.
  unpack    Extract verified archives into build/ (chromium -> build/src).
"""

import argparse
import hashlib
import shutil
import sys
import tarfile
import urllib.request

from _common import (BUILD_DIR, DOWNLOAD_CACHE, die, free_bytes_for,
                     human_size, read_downloads_ini)

# A Chromium source tarball expands to roughly ten times its compressed size,
# and a build adds tens of GB on top. Used for the honest warning in `check`.
EXTRACTION_MULTIPLIER = 10
BUILD_HEADROOM_BYTES = 40 * 1024 ** 3


def _head(url):
    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request) as response:
        length = response.headers.get("Content-Length")
        return response.status, int(length) if length else None


def cmd_check(_args):
    failures = 0
    for name, item in read_downloads_ini().items():
        try:
            status, size = _head(item["url"])
        except OSError as err:
            print("[{}] FAILED: {} ({})".format(name, item["url"], err))
            failures += 1
            continue
        print("[{}] HTTP {}  {}  {}".format(
            name, status, human_size(size) if size else "size unknown",
            item["url"]))
        if size and item.get("type", "archive") != "file":
            needed = size * (1 + EXTRACTION_MULTIPLIER) + BUILD_HEADROOM_BYTES
            free = free_bytes_for(BUILD_DIR)
            print("      projected need (download + extract + build): ~{}; "
                  "free disk: {}".format(human_size(needed), human_size(free)))
            if free < needed:
                print("      WARNING: not enough free disk for a full "
                      "checkout and build.")
    return 1 if failures else 0


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cmd_retrieve(_args):
    DOWNLOAD_CACHE.mkdir(parents=True, exist_ok=True)
    for name, item in read_downloads_ini().items():
        target = DOWNLOAD_CACHE / item["download_filename"]
        if target.exists() and _sha256(target) == item["sha256"]:
            print("[{}] cached and verified: {}".format(name, target.name))
            continue
        print("[{}] downloading {}".format(name, item["url"]))
        with urllib.request.urlopen(item["url"]) as response, \
                open(target, "wb") as out:
            shutil.copyfileobj(response, out, length=1024 * 1024)
        actual = _sha256(target)
        if actual != item["sha256"]:
            target.unlink()
            die("[{}] sha256 mismatch: expected {}, got {}".format(
                name, item["sha256"], actual))
        print("[{}] sha256 verified".format(name))
    return 0


def _strip_members(archive, strip):
    for member in archive.getmembers():
        parts = member.name.split("/", strip)
        if len(parts) <= strip:
            continue
        member.name = parts[strip]
        yield member


def cmd_unpack(_args):
    for name, item in read_downloads_ini().items():
        cached = DOWNLOAD_CACHE / item["download_filename"]
        if not cached.exists():
            die("[{}] download missing; run `fetch.py retrieve` first".format(
                name))
        if _sha256(cached) != item["sha256"]:
            die("[{}] download failed sha256 verification; delete {} and "
                "re-run retrieve".format(name, cached))
        destination = BUILD_DIR / item["output_path"]
        # A "file" entry (e.g. a filter list) is copied verbatim; the default
        # "archive" entry is extracted.
        if item.get("type", "archive") == "file":
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached, destination)
            print("[{}] copied -> {}".format(name, destination))
            continue
        destination.mkdir(parents=True, exist_ok=True)
        strip = int(item.get("strip_leading_dirs", 0))
        print("[{}] extracting {} -> {}".format(
            name, cached.name, destination))
        with tarfile.open(cached) as archive:
            archive.extractall(destination, members=_strip_members(
                archive, strip) if strip else None)
        print("[{}] done".format(name))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="verify URLs and disk space, download nothing")
    sub.add_parser("retrieve", help="download and sha256-verify archives")
    sub.add_parser("unpack", help="extract verified archives into build/")
    args = parser.parse_args()
    handler = {"check": cmd_check, "retrieve": cmd_retrieve,
               "unpack": cmd_unpack}[args.command]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
