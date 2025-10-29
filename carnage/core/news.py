"""Utilities for managing Gentoo repository news."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess

from .portageq import get_gentoo_repo_path


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


def _parse_news_list_line(line: str, index: int) -> News | None:
    """
    Parse a line from eselect news list output.

    Format: "N  2019-05-23  Change of ACCEPT_LICENSE default"
            "   2020-06-23  sys-libs/pam-1.4.0 upgrade" (read items have spaces)

    First character indicates: N = unread, space = read

    Args:
        line: Line from eselect news list
        index: 1-based index of the news item

    Returns:
        News object or None if parsing fails
    """
    # Check if line is long enough to contain a date
    if len(line) < 12:  # Need at least "X YYYY-MM-DD"
        return None

    # First character indicates read status: 'N' = unread, space/other = read
    read: bool = line[0] != 'N'

    # Find the date - look for YYYY-MM-DD pattern
    # The date always starts after the status indicator and some spaces
    date_start: int | None = None
    for i in range(min(5, len(line) - 10)):  # Check first few positions
        if (line[i:i + 4].isdigit() and line[i + 4] == '-' and
                line[i + 5:i + 7].isdigit() and line[i + 7] == '-' and
                line[i + 8:i + 10].isdigit()):
            date_start = i
            break

    if date_start is None:
        return None

    # Extract date (10 characters: YYYY-MM-DD)
    date: str = line[date_start:date_start + 10]

    # Extract title - everything after the date and any trailing spaces
    title_start: int = date_start + 10
    # Skip any spaces after the date
    while title_start < len(line) and line[title_start].isspace():
        title_start += 1

    if title_start >= len(line):
        return None

    title: str = line[title_start:].strip()

    if not date or not title:
        return None

    return News(index=index, date=date, title=title, read=read)


def _parse_news_file(news_path: Path) -> dict[str, str]:
    """
    Parse a news file and extract metadata.
    
    Args:
        news_path: Path to the news .txt file
    
    Returns:
        Dictionary with parsed fields
    """
    if not news_path.exists():
        return {}
    
    with open(news_path, "r", encoding="utf-8") as f:
        content: str = f.read()
    
    lines: list[str] = content.split("\n")
    metadata = {}
    content_start: int = 0
    
    # Parse header fields
    for i, line in enumerate(lines):
        if line.strip() == "":
            content_start = i + 1
            break
        
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip().lower().replace("-", "_")] = value.strip()
    
    # Get the actual content (after headers)
    if content_start < len(lines):
        metadata["content"] = "\n".join(lines[content_start:]).strip()
    else:
        metadata["content"] = ""
    
    return metadata


def get_news() -> list[News]:
    """
    Get all news items (both read and unread).

    Returns:
        List of News objects with full content loaded
    """

    news_dir: Path = get_gentoo_repo_path() / "metadata" / "news"

    # Get all news list (both read and unread)
    result: CompletedProcess[str] = subprocess.run(
        ["eselect", "--colour=no", "--brief", "news", "list"],
        capture_output=True,
        text=True
    )

    news_items: list[News] = []
    lines: list[str] = result.stdout.strip().split("\n")

    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue

        news: News | None = _parse_news_list_line(line, index)
        if news is None:
            continue

        # Find the news file
        # Format: /var/db/repos/gentoo/metadata/news/YYYY-MM-DD-*/YYYY-MM-DD-*.txt
        date_pattern: str = news.date  # e.g., "2019-05-23"
        news_files: list[Path] = list(news_dir.glob(f"{date_pattern}-*/{date_pattern}-*.txt"))

        if news_files:
            # Parse the news file to get full content
            metadata: dict[str, str] = _parse_news_file(news_files[0])

            news.author = metadata.get("author")
            news.posted = metadata.get("posted")
            news.revision = metadata.get("revision")
            news.format_version = metadata.get("news_item_format")
            news.display_if_installed = metadata.get("display_if_installed")
            news.content = metadata.get("content")

        news_items.append(news)

    return news_items


def mark_news_read(news_index: int) -> tuple[int, str, str]:
    """
    Mark a news item as read.
    
    Args:
        news_index: 1-based index of the news item to mark as read
    
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

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    result: CompletedProcess[str] = subprocess.run(
        ["eselect", "news", "purge"],
        capture_output=True,
        text=True
    )

    return result.returncode, result.stdout, result.stderr
