"""Core functionality for Carnage."""

# Expose main classes and functions
# args
from carnage.core.args import APP_DESC, APP_NAME, config_path
from carnage.core.cache import CacheManager
from carnage.core.config import Configuration, get_config
# GLSA management
from carnage.core.portage.glsas import (GLSA, fetch_glsas, fix_glsas,
                                        get_affected_glsas)
# News management
from carnage.core.portage.news import (News, get_news, mark_all_news_read,
                                       mark_news_read, purge_read_news)
# Overlay management
from carnage.core.portage.overlays import (Overlay, OverlayQuality,
                                           OverlayStatus, Owner, Source,
                                           SourceType, clear_cache)
from carnage.core.portage.overlays import fetch as fetch_overlays
from carnage.core.portage.overlays import fetch_extra as fetch_overlays_extra
from carnage.core.portage.overlays import \
    get_installed as get_installed_overlays
# portageq
from carnage.core.portage.portageq import get_gentoo_repo_path, get_repos_path
# USE
from carnage.core.portage.use import UseFlag, get_or_cache_useflags
from carnage.core.privilege import detect_backend, run_privileged

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
    "Configuration",
    # args
    "config_path",
    "APP_NAME",
    "APP_DESC"
]
