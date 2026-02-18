"""Utilities for managing Gentoo overlays."""

import concurrent.futures
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Literal

from lxml import etree

from carnage.core.cache import CacheManager
from carnage.core.config import Configuration, get_config
from carnage.core.eix.overlay import NO_CACHE_PACKAGE_COUNT, get_package_count
from carnage.core.portage.portageq import ctx
from carnage.core.privilege import run_privileged

# Cache configuration
CACHE_KEY = "overlays_data"

# Special value to indicate package counting was skipped
SKIPPED_PACKAGE_COUNT = -4

class OverlayQuality(Enum):
    """Quality status of an overlay."""
    CORE = "core"
    EXPERIMENTAL = "experimental"


class OverlayStatus(Enum):
    """Official status of an overlay."""
    OFFICIAL = "official"
    UNOFFICIAL = "unofficial"


class SourceType(Enum):
    """Version control system type."""
    GIT = "git"
    MERCURIAL = "mercurial"
    RSYNC = "rsync"
    CVS = "cvs"


@dataclass
class Owner:
    """Owner information for an overlay."""
    name: str
    email: str
    owner_type: Literal["person", "project"]


@dataclass
class Source:
    """Source repository information."""
    source_type: SourceType
    url: str


@dataclass
class Overlay:
    """Represents a Gentoo overlay repository."""
    name: str
    description: str | None
    homepage: str | None
    owner: Owner
    sources: list[Source]
    feeds: list[str]
    quality: OverlayQuality
    status: OverlayStatus
    installed: bool | None = None
    package_count: int | None = None

    def __str__(self) -> str:
        return f"{self.name} ({self.status.value})"

    def __repr__(self) -> str:
        return f"Overlay(name={self.name!r}, status={self.status.value})"

    def is_installed(self) -> bool:
        """
        Check if this overlay is installed.

        Returns:
            True if the overlay directory exists in the repository directory, False otherwise.
        """
        return Overlay.is_overlay_installed(self.name)

    @staticmethod
    def is_overlay_installed(name: str) -> bool:
        """
        Check if an overlay is installed by name.

        Args:
            name: The name of the overlay to check.

        Returns:
            True if the overlay directory exists in the repository directory, False otherwise.
        """
        from pathlib import Path

        overlay_path: Path = ctx.repos_path / name
        return overlay_path.exists() and overlay_path.is_dir()

    def enable(self) -> tuple[int, str, str]:
        """
        Enable this overlay using eselect.
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        return run_privileged(["eselect", "repository", "enable", self.name], None, False)

    def sync(self) -> tuple[int, str, str]:
        """
        Sync this overlay using emaint.
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        return run_privileged(["emaint", "sync", "-r", self.name], None, False)

    def enable_and_sync(self) -> tuple[int, str, str]:
        """
        Enable and sync this overlay in one operation.
        Returns:
            Tuple of (return_code, stdout, stderr) from the combined operation.
            If enable fails, sync is not attempted.
        """
        cmd: str = f"eselect repository enable {self.name} && emaint sync -r {self.name}"
        return run_privileged(["sh", "-c", cmd], None, False)

    def disable(self) -> tuple[int, str, str]:
        """
        Disable this overlay using eselect.

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        return run_privileged(["eselect", "repository", "disable", self.name], None, False)

    def remove(self) -> tuple[int, str, str]:
        """
        Remove this overlay using eselect.

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        return run_privileged(["eselect", "repository", "remove", self.name], None, False)

    def to_dict(self) -> dict:
        """Convert overlay to dictionary for serialization."""
        return {
            'name': self.name,
            'description': self.description,
            'homepage': self.homepage,
            'owner': {
                'name': self.owner.name,
                'email': self.owner.email,
                'owner_type': self.owner.owner_type
            },
            'sources': [
                {'source_type': s.source_type.value, 'url': s.url}
                for s in self.sources
            ],
            'feeds': self.feeds,
            'quality': self.quality.value,
            'status': self.status.value,
            'installed': self.installed,
            'package_count': self.package_count
        }

    @staticmethod
    def from_dict(data: dict) -> 'Overlay':
        """Create overlay from dictionary after deserialization."""
        return Overlay(
            name=data['name'],
            description=data['description'],
            homepage=data['homepage'],
            owner=Owner(
                name=data['owner']['name'],
                email=data['owner']['email'],
                owner_type=data['owner']['owner_type']
            ),
            sources=[
                Source(
                    source_type=SourceType(s['source_type']),
                    url=s['url']
                )
                for s in data['sources']
            ],
            feeds=data['feeds'],
            quality=OverlayQuality(data['quality']),
            status=OverlayStatus(data['status']),
            installed=data.get('installed'),
            package_count=data.get('package_count')
        )


def _parse_owner(repo_elem: etree._Element) -> Owner | None:
    """Parse owner information from XML element."""
    owner_elems = repo_elem.xpath("owner")
    if not owner_elems:
        return None

    owner_elem = owner_elems[0]

    name = owner_elem.xpath("string(name)")
    email = owner_elem.xpath("string(email)")
    owner_type = owner_elem.get("type", "person")

    if not name or not email:
        return None

    return Owner(
        name=name,
        email=email,
        owner_type=owner_type  # type: ignore
    )


def _parse_sources(repo_elem: etree._Element) -> list[Source]:
    """Parse source repositories from XML element."""
    sources: list[Source] = []

    source_elems = repo_elem.xpath("source")
    for source_elem in source_elems:
        source_type_str = source_elem.get("type")
        url = source_elem.text or ""

        if url:
            source_type = SourceType(source_type_str)
            sources.append(Source(source_type=source_type, url=url))

    return sources


def _parse_feeds(repo_elem: etree._Element) -> list[str]:
    """Parse feed URLs from XML element."""
    feeds = repo_elem.xpath("feed/text()")
    return [feed for feed in feeds if feed]


def _parse_overlay(repo_elem: etree._Element) -> Overlay | None:
    """Parse a single overlay from XML element."""
    name = repo_elem.xpath("string(name)")
    if not name:
        return None

    # Get description
    description = repo_elem.xpath("string(description)")
    homepage = repo_elem.xpath("string(homepage)")

    owner = _parse_owner(repo_elem)
    if owner is None:
        return None

    sources = _parse_sources(repo_elem)
    feeds = _parse_feeds(repo_elem)

    quality_str = repo_elem.get("quality", "experimental")
    status_str = repo_elem.get("status", "unofficial")

    try:
        quality = OverlayQuality(quality_str)
        status = OverlayStatus(status_str)
    except ValueError:
        # Unknown quality/status, skip this overlay
        return None

    return Overlay(
        name=name,
        description=description if description else None,
        homepage=homepage if homepage else None,
        owner=owner,
        sources=sources,
        feeds=feeds,
        quality=quality,
        status=status
    )


def fetch(source_url: str | None = None) -> list[Overlay]:
    """
    Fetch and parse overlay information from Gentoo API.

    Args:
        source_url: Optional specific URL to fetch from.
                    Defaults to configured URL.

    Returns:
        List of parsed Overlay objects.

    Raises:
        urllib.error.URLError: If fetching fails.
        etree.ParseError: If XML parsing fails.
    """
    config: Configuration = get_config()

    url: str = source_url or config.overlay_source

    with urllib.request.urlopen(url, timeout=30) as response:
        xml_data = response.read()

    parser = etree.XMLParser(recover=True, remove_comments=True)
    root = etree.fromstring(xml_data, parser=parser)

    overlays: list[Overlay] = []

    repo_elems = root.xpath("//repo")
    for repo_elem in repo_elems:
        overlay = _parse_overlay(repo_elem)
        if overlay is not None:
            overlays.append(overlay)

    return overlays


def get_installed() -> list[str]:
    """
    Get list of installed overlay names.

    Returns:
        List of directory names from repository directory.
    """
    repos_path: Path = ctx.repos_path

    if not repos_path.exists():
        return []

    return [
        item.name
        for item in repos_path.iterdir()
        if item.is_dir()
    ]


def _get_overlay_package_count(overlay: Overlay) -> tuple[Overlay, int]:
    """Get package count for a single overlay."""
    try:
        count: int = get_package_count(overlay.name)
        return overlay, count
    except:
        return overlay, -1


def _populate_package_counts(overlays: list[Overlay]) -> None:
    """Populate package counts for all overlays in parallel."""

    # Calculate optimal worker count
    cpu_count: int = os.cpu_count() or 1
    max_workers: int = max(2, min(cpu_count // 2, 8))

    # Use ThreadPoolExecutor for parallel execution
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_overlay = {
            executor.submit(_get_overlay_package_count, overlay): overlay
            for overlay in overlays
        }

        # Process completed tasks as they finish
        for future in concurrent.futures.as_completed(future_to_overlay):
            try:
                overlay, count = future.result()
                overlay.package_count = count
            except:
                # If anything goes wrong with the future itself, set count to -1
                overlay: Overlay = future_to_overlay[future]
                overlay.package_count = -1


def _populate_skipped_package_counts(overlays: list[Overlay]) -> None:
    """Set package counts to SKIPPED_PACKAGE_COUNT for all overlays."""
    for overlay in overlays:
        overlay.package_count = SKIPPED_PACKAGE_COUNT


def fetch_extra(source_url: str | None = None) -> list[Overlay]:
    """
    Fetch overlays and populate installation status and package counts.

    Args:
        source_url: Optional specific URL to fetch from.

    Returns:
        List of Overlay objects with 'installed' and 'package_count' fields populated.

    Raises:
        urllib.error.URLError: If fetching fails.
        etree.ParseError: If XML parsing fails.
    """
    overlays: list[Overlay] = fetch(source_url)
    installed_names: set[str] = set(get_installed())

    for overlay in overlays:
        overlay.installed = overlay.name in installed_names

    # Populate package counts based on configuration
    config: Configuration = get_config()
    if config.skip_package_counting:
        _populate_skipped_package_counts(overlays)
    else:
        _populate_package_counts(overlays)

    return overlays


def get_or_cache(cache_manager: CacheManager | None = None,
                source_url: str | None = None,
                force_refresh: bool = False) -> list[Overlay]:
    """
    Get overlays from cache or fetch fresh data if cache is stale/missing.

    Args:
        cache_manager: CacheManager instance. If None, creates a new one.
        source_url: Optional specific URL to fetch from.
        force_refresh: If True, ignore cache and fetch fresh data.

    Returns:
        List of Overlay objects with all metadata populated.
    """
    if cache_manager is None:
        cache_manager = CacheManager()

    config: Configuration = get_config()
    max_age = timedelta(hours=config.overlays_cache_max_age)

    # Check cache first unless forced refresh
    if not force_refresh and cache_manager.exists(CACHE_KEY):
        if not cache_manager.is_stale(CACHE_KEY, max_age):
            cached_data = cache_manager.get(CACHE_KEY)
            if cached_data:
                cached_overlays: list[Overlay] = [Overlay.from_dict(data) for data in cached_data]
                
                # Check if we need to refresh package counts due to configuration change
                if config.skip_package_counting:
                    # If package counting is now skipped, but we have real counts, that's fine
                    return cached_overlays
                else:
                    # If package counting is enabled, check if we have skipped counts
                    has_skipped_counts: bool = any(
                        overlay.package_count == SKIPPED_PACKAGE_COUNT 
                        for overlay in cached_overlays
                    )

                    has_non_cached: bool = any(
                        overlay.package_count == NO_CACHE_PACKAGE_COUNT
                        for overlay in cached_overlays
                    )

                    if not has_skipped_counts and not has_non_cached:
                        return cached_overlays
                    # If we have skipped counts or -3 but now want real counts, force refresh

    # Fetch fresh data
    overlays: list[Overlay] = fetch_extra(source_url)

    # Cache the results
    cache_data = [overlay.to_dict() for overlay in overlays]
    cache_manager.set(CACHE_KEY, cache_data)

    return overlays


def clear_cache(cache_manager: CacheManager | None = None) -> bool:
    """
    Clear the overlays cache.

    Args:
        cache_manager: CacheManager instance. If None, creates a new one.

    Returns:
        True if cache was cleared, False otherwise.
    """
    if cache_manager is None:
        cache_manager = CacheManager()

    return cache_manager.delete(CACHE_KEY)
