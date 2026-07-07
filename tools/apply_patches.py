#!/usr/bin/env python3
"""Apply the T3dmium patch series to an unpacked Chromium tree.

Patches are applied in patches/series order with GNU patch:
    patch -p1 --ignore-whitespace --no-backup-if-mismatch

Subcommands:
  apply     Apply every patch in series order (use --dry-run to test only).
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from _common import PATCHES_DIR, SOURCE_TREE, die, read_series


def find_patch_binary():
    binary = os.environ.get("PATCH_BIN") or shutil.which("patch")
    if not binary:
        die("GNU patch not found; install it or set PATCH_BIN")
    return binary


def apply_one(patch_binary, patch_path, tree, dry_run=False, reverse=False):
    command = [
        patch_binary, "-p1", "--ignore-whitespace",
        "--no-backup-if-mismatch", "-i", str(patch_path), "-d", str(tree),
    ]
    if dry_run:
        command.append("--dry-run")
    if reverse:
        command.append("--reverse")
    else:
        command.append("--forward")
    result = subprocess.run(command, capture_output=True, text=True)
    return result


def cmd_apply(args):
    tree = args.tree
    if not tree.is_dir():
        if args.dry_run and not read_series():
            # An empty series is trivially appliable; allow verifying the
            # tooling before any source tree exists.
            print("series is empty; nothing to apply")
            return 0
        die("source tree {} does not exist; run fetch.py first".format(tree))
    patch_binary = find_patch_binary()
    series = read_series()
    if not series:
        print("series is empty; nothing to apply")
        return 0
    entries = list(reversed(series)) if args.reverse else series
    failed = []
    for entry in entries:
        patch_path = PATCHES_DIR / entry
        if not patch_path.is_file():
            die("series entry has no file: {}".format(entry))
        result = apply_one(patch_binary, patch_path, tree,
                           dry_run=args.dry_run, reverse=args.reverse)
        status = "ok" if result.returncode == 0 else "FAILED"
        print("{:6} {}".format(status, entry))
        if result.returncode != 0:
            failed.append(entry)
            sys.stderr.write(result.stdout)
            sys.stderr.write(result.stderr)
            if not args.keep_going:
                break
    if failed:
        print("\n{} patch(es) failed{}:".format(
            len(failed), " (dry run)" if args.dry_run else ""))
        for entry in failed:
            print("  {}".format(entry))
        return 1
    print("\nall {} patch(es) {} cleanly{}".format(
        len(series), "reverse" if args.reverse else "applied",
        " (dry run)" if args.dry_run else ""))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    apply_parser = sub.add_parser("apply", help="apply patches in series order")
    apply_parser.add_argument("--tree", type=Path, default=SOURCE_TREE,
                              help="target source tree (default: build/src)")
    apply_parser.add_argument("--dry-run", action="store_true",
                              help="test whether patches apply; change nothing")
    apply_parser.add_argument("--reverse", action="store_true",
                              help="unapply the series (reverse order)")
    apply_parser.add_argument("--keep-going", action="store_true",
                              help="continue past failures to list them all")
    args = parser.parse_args()
    return cmd_apply(args)


if __name__ == "__main__":
    sys.exit(main())
