#!/usr/bin/env python3
"""Configure and build T3dmium from the prepared source tree.

Steps:
  1. Sanity-check the environment (source tree present, disk, macOS: full
     Xcode; Windows: run from a VS developer environment).
  2. Bootstrap depot_tools into build/depot_tools if not already present.
  3. Copy flags.gn to build/src/out/Default/args.gn.
  4. gn gen out/Default --fail-on-unused-args
  5. ninja -C out/Default <targets>

The first build takes several hours and needs roughly 100 GB of free disk in
total. See BUILDING.md.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

from _common import (BUILD_DIR, ROOT, SOURCE_TREE, die, free_bytes_for,
                     human_size)

DEPOT_TOOLS_URL = "https://chromium.googlesource.com/chromium/tools/depot_tools.git"
DEFAULT_TARGETS = ["chrome", "chromedriver"]


def check_environment():
    if not SOURCE_TREE.is_dir():
        die("no source tree at {}; run fetch.py retrieve && fetch.py unpack "
            "first".format(SOURCE_TREE))
    free = free_bytes_for(BUILD_DIR)
    if free < 60 * 1024 ** 3:
        print("WARNING: only {} free on the build volume; a Chromium build "
              "typically needs far more. See BUILDING.md.".format(
                  human_size(free)))
    if platform.system() == "Darwin":
        developer_dir = subprocess.run(["xcode-select", "-p"],
                                       capture_output=True, text=True)
        if "Xcode.app" not in developer_dir.stdout:
            die("full Xcode is required (found: {}). Install Xcode and run "
                "`sudo xcode-select -s /Applications/Xcode.app/Contents/"
                "Developer`".format(developer_dir.stdout.strip() or "nothing"))
    elif platform.system() == "Windows":
        if "VSINSTALLDIR" not in os.environ:
            print("WARNING: not running inside a Visual Studio developer "
                  "environment; the build will likely fail. See BUILDING.md.")


def bootstrap_depot_tools():
    depot_tools = BUILD_DIR / "depot_tools"
    if not depot_tools.is_dir():
        print("cloning depot_tools ...")
        subprocess.run(["git", "clone", "--depth=1", DEPOT_TOOLS_URL,
                        str(depot_tools)], check=True)
    env = os.environ.copy()
    env["PATH"] = str(depot_tools) + os.pathsep + env["PATH"]
    # Never let depot_tools update itself or report usage.
    env["DEPOT_TOOLS_UPDATE"] = "0"
    env["DEPOT_TOOLS_METRICS"] = "0"
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="out/Default",
                        help="output directory relative to the source tree")
    parser.add_argument("--targets", nargs="+", default=DEFAULT_TARGETS,
                        help="ninja targets (default: {})".format(
                            " ".join(DEFAULT_TARGETS)))
    parser.add_argument("--jobs", "-j", type=int, default=None,
                        help="parallel ninja jobs (default: ninja's choice)")
    args = parser.parse_args()

    check_environment()
    env = bootstrap_depot_tools()

    out_dir = SOURCE_TREE / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "flags.gn", out_dir / "args.gn")
    print("wrote {}".format(out_dir / "args.gn"))

    subprocess.run(["gn", "gen", args.out, "--fail-on-unused-args"],
                   cwd=SOURCE_TREE, env=env, check=True)
    ninja = ["ninja", "-C", args.out]
    if args.jobs:
        ninja += ["-j", str(args.jobs)]
    ninja += args.targets
    subprocess.run(ninja, cwd=SOURCE_TREE, env=env, check=True)
    print("build complete: {}".format(out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
