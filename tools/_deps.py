"""Resolve Chromium DEPS-managed sub-repositories at the pinned tag.

The official source tarball bundles every dependency listed in Chromium's
DEPS file (devtools-frontend, v8, and many third_party/* trees live in their
own git repositories). Those files are therefore NOT in the chromium/src git
tree served by gitiles, so a patch that touches them cannot be validated by
fetching from chromium/src alone.

This module reads DEPS at the pinned tag, resolves each dependency's
repository URL and commit, and lets the validator fetch a bundled file from
the correct sub-repository at the exact revision the pin uses.

DEPS is executable Python (that is how gclient consumes it); we exec it in a
controlled namespace providing the handful of helpers it references.
"""

import base64
import urllib.parse
import urllib.request

GITILES_FILE = "{repo}/+/{commit}/{path}?format=TEXT"
DEPS_URL = ("https://chromium.googlesource.com/chromium/src/+/"
            "refs/tags/{version}/DEPS?format=TEXT")


def _exec_deps(source):
    namespace = {}

    def var(name):
        return namespace["vars"][name]

    namespace["Var"] = var
    namespace["Str"] = str  # DEPS occasionally wraps values in Str()
    exec(compile(source, "DEPS", "exec"), namespace)  # noqa: S102
    return namespace.get("vars", {}), namespace.get("deps", {})


def load_dep_map(version, cache_root, opener=urllib.request.urlopen):
    """Return {local_path_prefix: (repo_url, commit)} for every git-backed
    dependency, with the leading 'src/' stripped so keys match patch paths.
    Cached to <cache_root>/DEPS.
    """
    cache_path = cache_root / "DEPS"
    if cache_path.exists():
        source = cache_path.read_text(encoding="utf-8")
    else:
        with opener(DEPS_URL.format(version=version)) as response:
            source = base64.b64decode(response.read()).decode("utf-8")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(source, encoding="utf-8")

    _, deps = _exec_deps(source)
    dep_map = {}
    for local_path, spec in deps.items():
        url = spec.get("url") if isinstance(spec, dict) else spec
        if not isinstance(url, str) or "@" not in url:
            continue  # CIPX packages / conditionals without a git url
        repo, _, commit = url.rpartition("@")
        key = local_path[4:] if local_path.startswith("src/") else local_path
        dep_map[key.rstrip("/")] = (repo, commit)
    return dep_map


def resolve(rel_path, dep_map):
    """If rel_path lives inside a DEPS sub-repo, return (repo, commit,
    subpath); else None. Longest prefix wins (nested deps)."""
    best = None
    for prefix, (repo, commit) in dep_map.items():
        if rel_path == prefix or rel_path.startswith(prefix + "/"):
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, repo, commit)
    if best is None:
        return None
    prefix, repo, commit = best
    subpath = rel_path[len(prefix):].lstrip("/")
    return repo, commit, subpath


def fetch_subrepo_file(rel_path, dep_map, opener=urllib.request.urlopen):
    """Fetch a DEPS-managed file's bytes at its pinned commit, or None if the
    path is not DEPS-managed or absent in the sub-repo."""
    resolved = resolve(rel_path, dep_map)
    if resolved is None:
        return None, False
    repo, commit, subpath = resolved
    url = GITILES_FILE.format(repo=repo, commit=commit,
                              path=urllib.parse.quote(subpath))
    try:
        with opener(url) as response:
            return base64.b64decode(response.read()), True
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None, True  # DEPS-managed but truly absent
        raise
