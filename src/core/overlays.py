"""Utilities for managing Gentoo overlays."""

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Any
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
from xml.etree.ElementTree import Element

OVERLAY_SOURCES: list[str] = [
    "https://api.gentoo.org/overlays/repositories.xml"
]


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

    def __str__(self) -> str:
        return f"{self.name} ({self.status.value})"

    def __repr__(self) -> str:
        return f"Overlay(name={self.name!r}, status={self.status.value})"

    def enable(self) -> tuple[int, str, str]:
        """
        Enable this overlay using eselect.

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        import subprocess

        result: CompletedProcess[str] = subprocess.run(
            ["eselect", "repository", "enable", self.name],
            capture_output=True,
            text=True
        )
        return result.returncode, result.stdout, result.stderr

    def sync(self) -> tuple[int, str, str]:
        """
        Sync this overlay using emerge.

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        import subprocess

        result: CompletedProcess[str] = subprocess.run(
            ["emerge", "--sync", self.name],
            capture_output=True,
            text=True
        )
        return result.returncode, result.stdout, result.stderr

    def enable_and_sync(self) -> tuple[int, str, str]:
        """
        Enable and sync this overlay in one operation.

        Returns:
            Tuple of (return_code, stdout, stderr) from the combined operation.
            If enable fails, sync is not attempted.
        """
        import subprocess

        cmd: str = f"eselect repository enable {self.name} && emerge --sync {self.name}"
        result: CompletedProcess[str] = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )
        return result.returncode, result.stdout, result.stderr


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

    quality_str = repo_elem.get("quality", "experimental")
    status_str = repo_elem.get("status", "unofficial")

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