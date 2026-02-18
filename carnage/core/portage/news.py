"""Utilities for managing Gentoo repository news."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess

from portage.const import NEWS_LIB_PATH
from portage.news import NewsItem
from portage.util import grabfile

from carnage.core.portage.portageq import ctx

_NEWS_REPO_ID = "gentoo"
_LANGUAGE_ID = "en"


@dataclass
class News:
    """Represents a Gentoo news item."""
    index: int
    date: str
    title: str
    read: bool
    author: str | None = None
    posted: str | None = None
    revision: str | None = None
    format_version: str | None = None
    display_if_installed: str | None = None
    content: str | None = None

    def __str__(self) -> str:
        status: str = "Read" if self.read else "Unread"
        return f"[{self.date}] {self.title} ({status})"

    def __repr__(self) -> str:
        return f"News(date={self.date!r}, title={self.title!r}, read={self.read})"


def _news_tracking_dir() -> Path:
    """Directory holding eselect's news tracking files."""
    return Path(ctx.settings["EROOT"]) / NEWS_LIB_PATH / "news"


def _unread_file() -> Path:
    return _news_tracking_dir() / f"news-{_NEWS_REPO_ID}.unread"


def _read_file() -> Path:
    return _news_tracking_dir() / f"news-{_NEWS_REPO_ID}.read"


def _news_dir() -> Path:
    return ctx.gentoo_repo_path / "metadata" / "news"


def _profile_path() -> str | None:
    """
    Return the profile path relative to the profiles base directory, as
    NewsItem.isRelevant() expects (mirrors NewsManager._profile_path logic).
    """
    import os
    portdir: str | None = ctx.portdbapi.repositories.mainRepoLocation()
    if portdir is None:
        return None
    profiles_base: str = portdir + "/profiles/"
    profile = ctx.settings.profile_path
    if not profile:
        return None
    profile = os.path.realpath(profile)
    if profile.startswith(profiles_base):
        return profile[len(profiles_base):]
    return profile


def _read_tracking_set(path: Path) -> set[str]:
    """Read an eselect news tracking file into a set of item names."""
    if not path.exists():
        return set()
    return set(grabfile(str(path)))


def _parse_news_file(news_path: Path) -> dict[str, str]:
    """Parse a GLEP 42 news file and return its header fields and content."""
    if not news_path.exists():
        return {}

    with open(news_path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    lines = content.split("\n")
    metadata: dict[str, str] = {}
    content_start = 0

    for i, line in enumerate(lines):
        if line.strip() == "":
            content_start = i + 1
            break
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip().lower().replace("-", "_")] = value.strip()

    metadata["content"] = "\n".join(lines[content_start:]).strip()
    return metadata


def get_news() -> list[News]:
    """
    Get all news items that eselect is currently tracking (unread and read).

    eselect maintains two files per repo:
      - news-gentoo.unread  items that are relevant and not yet read
      - news-gentoo.read    items that have been read

    Items absent from both files have been purged or were never relevant,
    and are not shown. Relevancy is additionally verified via portage's
    NewsItem.isRelevant() so that items added to the tracking files before
    a system change are not shown if they no longer apply.

    Returns:
        List of News objects sorted by date (unread first, then read).
    """
    news_dir: Path = _news_dir()

    if not news_dir.exists():
        return []

    unread: set[str] = _read_tracking_set(_unread_file())
    read: set[str] = _read_tracking_set(_read_file())
    tracked: set[str] = unread | read

    if not tracked:
        return []

    profile: str | None = _profile_path()
    news_items: list[News] = []
    index = 1

    for item_dir in sorted(news_dir.iterdir()):
        if not item_dir.is_dir():
            continue

        item_name: str = item_dir.name

        # Only show items eselect is actively tracking.
        if item_name not in tracked:
            continue

        news_file: Path = item_dir / f"{item_name}.{_LANGUAGE_ID}.txt"
        if not news_file.exists():
            continue

        item = NewsItem(str(news_file), item_name)
        if not item.isValid():
            continue
        if not item.isRelevant(ctx.vardbapi, ctx.settings, profile):
            continue

        metadata: dict[str, str] = _parse_news_file(news_file)
        date: str = item_name[:10] if len(item_name) >= 10 else item_name

        news_items.append(News(
            index=index,
            date=date,
            title=metadata.get("title", item_name),
            read=item_name in read,
            author=metadata.get("author"),
            posted=metadata.get("posted"),
            revision=metadata.get("revision"),
            format_version=metadata.get("news_item_format"),
            display_if_installed=metadata.get("display_if_installed"),
            content=metadata.get("content"),
        ))
        index += 1

    return news_items


def mark_news_read(news_index: int) -> tuple[int, str, str]:
    """
    Mark a news item as read.

    Args:
        news_index: 1-based index of the news item to mark as read.

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    result: CompletedProcess[str] = subprocess.run(
        ["eselect", "news", "read", "--quiet", str(news_index)],
        capture_output=True,
        text=True
    )
    
    return result.returncode, result.stdout, result.stderr


def mark_all_news_read() -> tuple[int, str, str]:
    """
    Mark all news items as read.
    
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    result: CompletedProcess[str] = subprocess.run(
        ["eselect", "news", "read", "--quiet", "all"],
        capture_output=True,
        text=True
    )
    
    return result.returncode, result.stdout, result.stderr


def purge_read_news() -> tuple[int, str, str]:
    """
    Purge all read news items.

    Purging clears the read tracking file, removing those items from view
    entirely. They will not reappear unless eselect re-adds them as unread.

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    result: CompletedProcess[str] = subprocess.run(
        ["eselect", "news", "purge"],
        capture_output=True,
        text=True
    )

    return result.returncode, result.stdout, result.stderr