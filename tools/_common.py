"""Shared helpers for T3dmium tooling. Stdlib only; Python 3.9+."""

import configparser
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
SOURCE_TREE = BUILD_DIR / "src"
DOWNLOAD_CACHE = BUILD_DIR / "download_cache"
PATCHES_DIR = ROOT / "patches"
SERIES_FILE = PATCHES_DIR / "series"


def chromium_version():
    return (ROOT / "chromium_version.txt").read_text(encoding="utf-8").strip()


def t3dmium_revision():
    return (ROOT / "revision.txt").read_text(encoding="utf-8").strip()


def read_series():
    """Return the ordered list of patch paths (relative to patches/)."""
    entries = []
    for raw in SERIES_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def read_downloads_ini():
    """Return {section: dict} from downloads.ini with {version} expanded."""
    parser = configparser.ConfigParser()
    with open(ROOT / "downloads.ini", encoding="utf-8") as handle:
        parser.read_file(handle)
    version = chromium_version()
    sections = {}
    for name in parser.sections():
        item = dict(parser.items(name))
        for key in ("url", "download_filename"):
            if key in item:
                item[key] = item[key].format(version=version)
        sections[name] = item
    return sections


def read_list_file(path):
    """Read a .list file: one entry per line, # comments and blanks ignored."""
    entries = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def die(message, code=1):
    print("error: {}".format(message), file=sys.stderr)
    raise SystemExit(code)


def free_bytes_for(path):
    """Free bytes on the filesystem that holds `path`, resolving symlinks and
    walking up to the nearest existing ancestor. Correct even when build/ is a
    symlink to another volume (e.g. an external drive)."""
    import shutil
    probe = Path(path).resolve()
    while not probe.exists():
        if probe.parent == probe:
            break
        probe = probe.parent
    return shutil.disk_usage(probe).free


def human_size(num_bytes):
    value = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return "{:.1f} {}".format(value, unit)
        value /= 1024
