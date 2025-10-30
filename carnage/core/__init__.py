"""Core functionality for Carnage."""

# Expose main classes and functions
from .cache import CacheManager
from .config import Configuration, get_config
# GLSA management
from .glsas import GLSA, fetch_glsas, fix_glsas, get_affected_glsas
# News management
from .news import (News, get_news, mark_all_news_read, mark_news_read,
                   purge_read_news)
# Overlay management
from .overlays import (Overlay, OverlayQuality, OverlayStatus, Owner, Source,
                       SourceType, clear_cache)
from .overlays import fetch as fetch_overlays
from .overlays import fetch_extra as fetch_overlays_extra
from .overlays import get_installed as get_installed_overlays
# portageq
from .portageq import get_gentoo_repo_path, get_repos_path
from .privilege import detect_backend, run_privileged
# USE
from .use import UseFlag, get_or_cache_useflags

__all__ = [
    # Cache
    "CacheManager",
    # Privilege
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
    "get_installed_overlays"
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
