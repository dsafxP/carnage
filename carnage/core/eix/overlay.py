"""Interactions with eix for overlay-specific operations."""

import os
from subprocess import CompletedProcess

from lxml import etree

from carnage.core.eix.eix import has_cache, has_remote_cache
from carnage.core.process import tracked_run

NO_CACHE_PACKAGE_COUNT = -3


def get_all_package_counts() -> dict[str, int] | None:
    """
    Count packages found exclusively in each overlay with a single eix query.

    Equivalent to calling get_package_count() per overlay: a package counts
    for an overlay only when all its versions come from there. One database
    scan replaces hundreds of subprocess spawns.

    Returns:
        Mapping of overlay name to package count, or None when no eix
        cache exists at all.

    Raises:
        subprocess.SubprocessError: If eix fails.
        OSError: If eix cannot be run.
        etree.ParseError: If eix output is not valid XML.
    """
    # Set environment to disable limits
    env: dict[str, str] = os.environ.copy()
    env["EIX_LIMIT"] = "0"

    # Same database view as the per-overlay queries: remote cache when
    # available, local otherwise.
    if has_remote_cache():
        cmd: list[str] = ["eix", "-R", "--xml", "*"]
    elif has_cache():
        cmd = ["eix", "--xml", "*"]
    else:
        return None  # No cache available

    result: CompletedProcess[bytes] = tracked_run(cmd, env=env)

    parser = etree.XMLParser(remove_comments=True)
    root = etree.fromstring(result.stdout, parser=parser)

    counts: dict[str, int] = {}

    for package_elem in root.iter("package"):
        repos = {(v.get("repository") or "gentoo") for v in package_elem.findall("version")}
        if len(repos) == 1:
            name = next(iter(repos))
            counts[name] = counts.get(name, 0) + 1

    return counts
