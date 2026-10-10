"""USE flag management with caching and description parsing."""

import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from re import Match

from carnage.core.cache import CacheManager
from carnage.core.config import Configuration, get_config
from carnage.core.eix.use import get_all_useflags
from carnage.core.portage.portageq import ctx

# Cache configuration
CACHE_KEY_USEFLAGS = "useflags_data"


@dataclass
class UseFlag:
    """USE flag with description."""

    name: str
    description: str | None = None

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"UseFlag({self.name!r}, desc={bool(self.description)})"

    def to_dict(self) -> dict:
        """Convert to dictionary for caching."""
        return {"name": self.name, "description": self.description}

    @classmethod
    def from_dict(cls, data: dict) -> "UseFlag":
        """Create from dictionary after cache load."""
        return cls(name=data["name"], description=data["description"])


# In-memory decoded USE flags. Reset whenever the on-disk cache is refreshed
# (see below) and between tests.
_useflags_memo: list[UseFlag] | None = None


def _parse_flag_line(line: str) -> tuple[str, ...] | None:
    """Parse a single USE flag description line.

    Returns:
        Tuple of (flag, description) or None if line is invalid.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Format: "flag - Description"
    match: Match[str] | None = re.match(r"^(\S+)\s+-\s+(.+)$", line)
    if match:
        return match.groups()
    return None


def _parse_local_flag_line(line: str) -> tuple[str, ...] | None:
    """Parse a local USE flag description line.

    Handles both package-specific and global formats.

    Returns:
        Tuple of (flag, description) or None if line is invalid.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Format: "category/package:flag - Description" or "flag - Description"
    if ":" in line:
        match: Match[str] | None = re.match(r"^[^:]+:(\S+)\s+-\s+(.+)$", line)
    else:
        match = re.match(r"^(\S+)\s+-\s+(.+)$", line)

    if match:
        return match.groups()
    return None


def _parse_desc_file(file_path: Path, descriptions: dict[str, str]) -> None:
    """Parse a use.desc file and update descriptions dict."""
    if not file_path.exists():
        return

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            result = _parse_flag_line(line)
            if result:
                flag, desc = result
                if flag not in descriptions:
                    descriptions[flag] = desc


def _parse_local_desc_file(file_path: Path, descriptions: dict[str, str]) -> None:
    """Parse a use.local.desc file and update descriptions dict."""
    if not file_path.exists():
        return

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            result = _parse_local_flag_line(line)
            if result:
                flag, desc = result
                if flag not in descriptions:
                    descriptions[flag] = desc


def _parse_repo_useflags(repo_dir: Path, descriptions: dict[str, str]) -> None:
    """Parse USE flags from a single repository."""
    profiles_dir: Path = repo_dir / "profiles"

    _parse_desc_file(profiles_dir / "use.desc", descriptions)
    _parse_local_desc_file(profiles_dir / "use.local.desc", descriptions)


def _parse_useflag_descriptions() -> dict[str, str]:
    """Parse USE flag descriptions from profile files."""
    descriptions: dict[str, str] = {}
    repos_path: Path = ctx.repos_path

    if not repos_path.exists():
        return descriptions

    for repo_dir in repos_path.iterdir():
        if not repo_dir.is_dir():
            continue
        _parse_repo_useflags(repo_dir, descriptions)

    return descriptions


def get_or_cache_useflags(cache_manager: CacheManager, force_refresh: bool = False) -> list[UseFlag]:
    """
    Get USE flags with descriptions from cache or fetch fresh data.

    The decoded list is memoized in memory: the tab calls this on every
    keystroke, and re-reading plus re-decoding a ~463 KB msgpack file each
    time is what made typing stutter.

    Args:
        cache_manager: CacheManager instance.
        force_refresh: If True, ignore cache and fetch fresh data.

    Returns:
        List of UseFlag objects with descriptions.
    """
    global _useflags_memo

    config: Configuration = get_config()
    max_age = timedelta(hours=config.use_cache_max_age)

    # Check cache first unless forced refresh
    if not force_refresh and cache_manager.exists(CACHE_KEY_USEFLAGS):
        if not cache_manager.is_stale(CACHE_KEY_USEFLAGS, max_age):
            if _useflags_memo is None:
                cached_data = cache_manager.get(CACHE_KEY_USEFLAGS)
                if cached_data:
                    _useflags_memo = [UseFlag.from_dict(data) for data in cached_data]

            if _useflags_memo is not None:
                return _useflags_memo

    # Fetch fresh data
    useflag_names: list[str] = get_all_useflags()
    descriptions: dict[str, str] = _parse_useflag_descriptions()
    useflags: list[UseFlag] = []

    for flag_name in useflag_names:
        # Skip flags that are only special characters
        if re.match(r"^[^a-zA-Z0-9]+$", flag_name):
            continue

        # Clean flag name (remove leading + etc.)
        clean_name: str = flag_name.lstrip("+")

        # Get description
        description: str | None = descriptions.get(clean_name) or descriptions.get(flag_name)

        useflag = UseFlag(name=clean_name, description=description)
        useflags.append(useflag)

    # Cache the results
    cache_data = [useflag.to_dict() for useflag in useflags]
    cache_manager.set(CACHE_KEY_USEFLAGS, cache_data)
    _useflags_memo = useflags

    return useflags


def invalidate_useflags_memo() -> None:
    """Forget the in-memory USE flags so they are decoded again."""
    global _useflags_memo

    _useflags_memo = None
