"""USE flag management with caching and description parsing."""

from dataclasses import dataclass
from pathlib import Path
from re import Match
from typing import List, Dict
import re

from .cache import CacheManager
from .eix.use import get_all_useflags
from datetime import timedelta

# Cache configuration
CACHE_KEY_USEFLAGS = "useflags_data"
CACHE_KEY_DESCRIPTIONS = "useflag_descriptions"
CACHE_MAX_AGE = timedelta(hours=24)


@dataclass
class UseFlag:
    """USE flag with description."""
    name: str
    description: str | None = None
    source: str = "global"  # "global", "local", or package-specific

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"UseFlag({self.name!r}, desc={bool(self.description)})"

    def to_dict(self) -> dict:
        """Convert to dictionary for caching."""
        return {
            'name': self.name,
            'description': self.description,
            'source': self.source
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'UseFlag':
        """Create from dictionary after cache load."""
        return cls(
            name=data['name'],
            description=data['description'],
            source=data.get('source', 'global')
        )


def _parse_useflag_descriptions() -> Dict[str, str]:
    """Parse USE flag descriptions from profile files."""
    descriptions: Dict[str, str] = {}
    repos_path = Path("/var/db/repos")

    if not repos_path.exists():
        return descriptions

    # Look for use.desc and use.local.desc in all repositories
    for repo_dir in repos_path.iterdir():
        if not repo_dir.is_dir():
            continue

        # Parse global use.desc
        use_desc_path: Path = repo_dir / "profiles" / "use.desc"
        if use_desc_path.exists():
            with open(use_desc_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Format: "flag - Description"
                        match: Match[str] | None = re.match(r'^(\S+)\s+-\s+(.+)$', line)
                        if match:
                            flag, desc = match.groups()
                            if flag not in descriptions:  # First match wins
                                descriptions[flag] = desc

        # Parse local use.local.desc
        use_local_path: Path = repo_dir / "profiles" / "use.local.desc"
        if use_local_path.exists():
            with open(use_local_path, 'r', encoding='utf-8') as f:
                line: str
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Format: "category/package:flag - Description" or "flag - Description"
                        if ':' in line:
                            # Package-specific: "category/package:flag - Description"
                            match = re.match(r'^[^:]+:(\S+)\s+-\s+(.+)$', line)
                        else:
                            # Global: "flag - Description"
                            match = re.match(r'^(\S+)\s+-\s+(.+)$', line)

                        if match:
                            flag, desc = match.groups()
                            if flag not in descriptions:  # First match wins
                                descriptions[flag] = desc

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

    # Check cache first unless forced refresh
    if not force_refresh and cache_manager.exists(CACHE_KEY_USEFLAGS):
        if not cache_manager.is_stale(CACHE_KEY_USEFLAGS, CACHE_MAX_AGE):
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
            description=description,
            source="global"
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

    # Also clear any package caches
    cache_keys: list[str] = cache_manager.list_keys()
    for key in cache_keys:
        if key.startswith("useflag_packages_"):
            cache_manager.delete(key)

    return cleared