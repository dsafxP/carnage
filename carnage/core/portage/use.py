"""USE flag management with caching and description parsing."""

import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from re import Match
from typing import Any, Dict, List

from carnage.core.cache import CacheManager
from carnage.core.config import Configuration, get_config
from carnage.core.eix.use import get_all_useflags
from carnage.core.portage.portageq import get_repos_path

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
        return {
            'name': self.name,
            'description': self.description
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'UseFlag':
        """Create from dictionary after cache load."""
        return cls(
            name=data['name'],
            description=data['description']
        )


def _parse_flag_line(line: str) -> tuple[str | Any, ...] | None:
    """Parse a single USE flag description line.

    Returns:
        Tuple of (flag, description) or None if line is invalid.
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    # Format: "flag - Description"
    match: Match[str] | None = re.match(r'^(\S+)\s+-\s+(.+)$', line)
    if match:
        return match.groups()
    return None


def _parse_local_flag_line(line: str) -> tuple[str | Any, ...] | None:
    """Parse a local USE flag description line.

    Handles both package-specific and global formats.

    Returns:
        Tuple of (flag, description) or None if line is invalid.
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    # Format: "category/package:flag - Description" or "flag - Description"
    if ':' in line:
        match: Match[str] | None = re.match(r'^[^:]+:(\S+)\s+-\s+(.+)$', line)
    else:
        match = re.match(r'^(\S+)\s+-\s+(.+)$', line)

    if match:
        return match.groups()
    return None


def _parse_desc_file(file_path: Path, descriptions: Dict[str, str]) -> None:
    """Parse a use.desc file and update descriptions dict."""
    if not file_path.exists():
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            result = _parse_flag_line(line)
            if result:
                flag, desc = result
                if flag not in descriptions:
                    descriptions[flag] = desc


def _parse_local_desc_file(file_path: Path, descriptions: Dict[str, str]) -> None:
    """Parse a use.local.desc file and update descriptions dict."""
    if not file_path.exists():
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            result = _parse_local_flag_line(line)
            if result:
                flag, desc = result
                if flag not in descriptions:
                    descriptions[flag] = desc


def _parse_repo_useflags(repo_dir: Path, descriptions: Dict[str, str]) -> None:
    """Parse USE flags from a single repository."""
    profiles_dir: Path = repo_dir / "profiles"

    _parse_desc_file(profiles_dir / "use.desc", descriptions)
    _parse_local_desc_file(profiles_dir / "use.local.desc", descriptions)


def _parse_useflag_descriptions() -> Dict[str, str]:
    """Parse USE flag descriptions from profile files."""
    descriptions: Dict[str, str] = {}
    repos_path: Path = get_repos_path()

    if not repos_path.exists():
        return descriptions

    for repo_dir in repos_path.iterdir():
        if not repo_dir.is_dir():
            continue
        _parse_repo_useflags(repo_dir, descriptions)

    return descriptions


def get_or_cache_useflags(cache_manager: CacheManager | None = None,
                          force_refresh: bool = False) -> List[UseFlag]:
    """
    Get USE flags with descriptions from cache or fetch fresh data.

    Args:
        cache_manager: CacheManager instance. If None, creates a new one.
        force_refresh: If True, ignore cache and fetch fresh data.

    Returns:
        List of UseFlag objects with descriptions.
    """
    if cache_manager is None:
        cache_manager = CacheManager()

    config: Configuration = get_config()
    max_age = timedelta(hours=config.use_cache_max_age)

    # Check cache first unless forced refresh
    if not force_refresh and cache_manager.exists(CACHE_KEY_USEFLAGS):
        if not cache_manager.is_stale(CACHE_KEY_USEFLAGS, max_age):
            cached_data = cache_manager.get(CACHE_KEY_USEFLAGS)
            if cached_data:
                return [UseFlag.from_dict(data) for data in cached_data]

    # Fetch fresh data
    print("Fetching USE flags...")
    useflag_names: list[str] = get_all_useflags()

    print("Parsing USE flag descriptions...")
    descriptions: dict[str, str] = _parse_useflag_descriptions()

    print("Building USE flag objects...")
    useflags = []

    for flag_name in useflag_names:
        # Skip flags that are only special characters
        if re.match(r'^[^a-zA-Z0-9]+$', flag_name):
            continue

        # Clean flag name (remove leading + etc.)
        clean_name: str = flag_name.lstrip('+')

        # Get description
        description: str | None = descriptions.get(clean_name) or descriptions.get(flag_name)

        useflag = UseFlag(
            name=clean_name,
            description=description
        )
        useflags.append(useflag)

    # Cache the results
    cache_data = [useflag.to_dict() for useflag in useflags]
    cache_manager.set(CACHE_KEY_USEFLAGS, cache_data)

    return useflags


def clear_useflags_cache(cache_manager: CacheManager | None = None) -> bool:
    """
    Clear the USE flags cache.

    Args:
        cache_manager: CacheManager instance. If None, creates a new one.

    Returns:
        True if cache was cleared, False otherwise.
    """
    if cache_manager is None:
        cache_manager = CacheManager()

    # Clear main useflags cache
    cleared: bool = cache_manager.delete(CACHE_KEY_USEFLAGS)

    return cleared
