"""Core functionality for Carnage."""

# Expose main classes and functions
from .cache import CacheManager
from .privilege import PrivilegeBackend, detect_backend, run_privileged

# Overlay management
from .overlays import (
    Overlay,
    OverlayQuality,
    OverlayStatus,
    Source,
    SourceType,
    Owner,
    fetch as fetch_overlays,
    fetch_extra as fetch_overlays_extra,
    get_installed as get_installed_overlays,
)

# GLSA management
from .glsas import GLSA, fetch_glsas, get_affected_glsas, fix_glsas

# News management
from .news import News, get_news, mark_news_read, mark_all_news_read, purge_read_news

# USE
from .use import UseFlag, get_or_cache_useflags

# portageq
from .portageq import get_repos_path, get_gentoo_repo_path

from .config import get_config, Configuration

__all__ = [
    # Cache
    "CacheManager",
    # Privilege
    "PrivilegeBackend",
    "detect_backend",
    "run_privileged",
    # Overlays
    "Overlay",
    "OverlayQuality",
    "OverlayStatus",
    "Source",
    "SourceType",
    "Owner",
    "fetch_overlays",
    "fetch_overlays_extra",
    "get_installed_overlays",
    # GLSAs
    "GLSA",
    "fetch_glsas",
    "get_affected_glsas",
    "fix_glsas",
    # News
    "News",
    "get_news",
    "mark_news_read",
    "mark_all_news_read",
    "purge_read_news",
    # USE
    "UseFlag",
    "get_or_cache_useflags",
    # portageq
    "get_repos_path",
    "get_gentoo_repo_path",
    # Configuration
    "get_config",
    "Configuration"
]