"""Utilities for managing Gentoo overlays."""
import concurrent.futures
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal, Any
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
from xml.etree.ElementTree import Element
from datetime import timedelta

from .cache import CacheManager
from .eix.overlay import get_package_count

OVERLAY_SOURCES: list[str] = [
    "https://api.gentoo.org/overlays/repositories.xml"
]

# Cache configuration
CACHE_KEY = "overlays_data"
CACHE_MAX_AGE = timedelta(hours=48)


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
            True if the overlay directory exists in /var/db/repos, False otherwise.
        """
        from pathlib import Path

        overlay_path: Path = Path("/var/db/repos") / self.name
        return overlay_path.exists() and overlay_path.is_dir()

    def enable(self) -> tuple[int, str, str]:
        """
        Enable this overlay using eselect.
        Returns:
            Tuple of (return_code, stdout,< >stderr)
        """
        from .privilege import run_privileged

        return run_privileged(["eselect", "repository", "enable", self.name])

    def sync(self) -> tuple[int, str, str]:
        """
        Sync this overlay using emerge.
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        from .privilege import run_privileged

        return run_privileged(["emerge", "--sync", self.name])

    def enable_and_sync(self) -> tuple[int, str, str]:
        """
        Enable and sync this overlay in one operation.
        Returns:
            Tuple of (return_code, stdout, stderr) from the combined operation.
            If enable fails, sync is not attempted.
        """
        from .privilege import run_privileged

        cmd: str = f"eselect repository enable {self.name} && emerge --sync {self.name}"
        return run_privileged(["sh", "-c", cmd])

    def disable(self) -> tuple[int, str, str]:
        """
        Disable this overlay using eselect.

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        from .privilege import run_privileged

        return run_privileged(["eselect", "repository", "disable", self.name])

    def remove(self) -> tuple[int, str, str]:
        """
        Remove this overlay using eselect.

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        from .privilege import run_privileged

        return run_privileged(["eselect", "repository", "remove", self.name])

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


def _parse_owner(repo_elem: ET.Element) -> Owner | None:
    """Parse owner information from XML element."""
    owner_elem: Element | None = repo_elem.find("owner")
    if owner_elem is None:
        return None

    name_elem: Element | None = owner_elem.find("name")
    email_elem: Element | None = owner_elem.find("email")
    owner_type: str = owner_elem.get("type", "person")

    if name_elem is None or email_elem is None:
        return None

    return Owner(
        name=name_elem.text or "",
        email=email_elem.text or "",
        owner_type=owner_type  # type: ignore
    )


def _parse_sources(repo_elem: ET.Element) -> list[Source]:
    """Parse source repositories from XML element."""
    sources: list[Any] = []
    for source_elem in repo_elem.findall("source"):
        source_type_str: str = source_elem.get("type", "git")
        url: str = source_elem.text or ""

        if url:
            try:
                source_type = SourceType(source_type_str)
                sources.append(Source(source_type=source_type, url=url))
            except ValueError:
                # Unknown source type, skip
                continue

    return sources


def _parse_feeds(repo_elem: ET.Element) -> list[str]:
    """Parse feed URLs from XML element."""
    feeds: list[str] = []
    for feed_elem in repo_elem.findall("feed"):
        if feed_elem.text:
            feeds.append(feed_elem.text)
    return feeds


def _parse_overlay(repo_elem: ET.Element) -> Overlay | None:
    """Parse a single overlay from XML element."""
    name_elem: Element | None = repo_elem.find("name")
    desc_elem: Element | None = repo_elem.find("description[@lang='en']")
    homepage_elem: Element | None = repo_elem.find("homepage")

    if name_elem is None or name_elem.text is None:
        return None

    owner: Owner | None = _parse_owner(repo_elem)
    if owner is None:
        return None

    sources: list[Source] = _parse_sources(repo_elem)
    feeds: list[str] = _parse_feeds(repo_elem)

    quality_str: str = repo_elem.get("quality", "experimental")
    status_str: str = repo_elem.get("status", "unofficial")

    try:
        quality = OverlayQuality(quality_str)
        status = OverlayStatus(status_str)
    except ValueError:
        # Unknown quality/status, skip this overlay
        return None

    return Overlay(
        name=name_elem.text,
        description=desc_elem.text if desc_elem is not None else "",
        homepage=homepage_elem.text if homepage_elem is not None else "",
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
                   Defaults to first URL in OVERLAY_SOURCES.

    Returns:
        List of parsed Overlay objects.

    Raises:
        urllib.error.URLError: If fetching fails.
        ET.ParseError: If XML parsing fails.
    """
    url: str = source_url or OVERLAY_SOURCES[0]

    with urllib.request.urlopen(url, timeout=30) as response:
        xml_data = response.read()

    root: Element = ET.fromstring(xml_data)

    overlays: list[Overlay] = []
    for repo_elem in root.findall("repo"):
        overlay: Overlay | None = _parse_overlay(repo_elem)

        if overlay is not None:
            overlays.append(overlay)

    return overlays


def get_installed() -> list[str]:
    """
    Get list of installed overlay names.

    Returns:
        List of directory names from /var/db/repos.
    """
    repos_path = Path("/var/db/repos")

    if not repos_path.exists():
        return []

    return [
        item.name
        for item in repos_path.iterdir()
        if item.is_dir()
    ]


def _populate_package_counts(overlays: list[Overlay]) -> None:
    """Populate package counts for all overlays in parallel."""

    def _get_count(overlay: Overlay) -> tuple[Overlay, int]:
        """Get package count for a single overlay."""
        try:
            count: int = get_package_count(overlay.name)
            return overlay, count
        except:
            return overlay, -1

    # Use ThreadPoolExecutor for parallel execution
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        # Submit all tasks
        future_to_overlay = {
            executor.submit(_get_count, overlay): overlay
            for overlay in overlays
        }

        # Process completed tasks as they finish
        for future in concurrent.futures.as_completed(future_to_overlay):
            try:
                overlay: object
                overlay, count = future.result()
                overlay.package_count = count
            except:
                # If anything goes wrong with the future itself, set count to -1
                overlay = future_to_overlay[future]
                overlay.package_count = -1


def fetch_extra(source_url: str | None = None) -> list[Overlay]:
    """
    Fetch overlays and populate installation status and package counts.

    Args:
        source_url: Optional specific URL to fetch from.

    Returns:
        List of Overlay objects with 'installed' and 'package_count' fields populated.

    Raises:
        urllib.error.URLError: If fetching fails.
        xml.etree.ElementTree.ParseError: If XML parsing fails.
    """
    overlays: list[Overlay] = fetch(source_url)
    installed_names: set[str] = set(get_installed())

    for overlay in overlays:
        overlay.installed = overlay.name in installed_names

    # Populate package counts (this may take a while)
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

    # Check cache first unless forced refresh
    if not force_refresh and cache_manager.exists(CACHE_KEY):
        if not cache_manager.is_stale(CACHE_KEY, CACHE_MAX_AGE):
            cached_data = cache_manager.get(CACHE_KEY)
            if cached_data:
                return [Overlay.from_dict(data) for data in cached_data]

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