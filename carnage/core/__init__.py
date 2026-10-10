"""Core functionality for Carnage."""

# Expose main classes and functions
# args
from carnage.core.args import get_config_path
from carnage.core.cache import CacheManager
from carnage.core.config import Configuration, get_config

# News management
from carnage.core.portage.news import (
    News,
    get_news,
    mark_all_news_read,
    mark_news_read,
    purge_read_news,
)

# Overlay management
from carnage.core.portage.overlays import (
    Overlay,
    OverlayQuality,
    OverlayStatus,
    Owner,
    Source,
    SourceType,
    clear_cache,
)
from carnage.core.portage.overlays import fetch as fetch_overlays
from carnage.core.portage.overlays import fetch_extra as fetch_overlays_extra
from carnage.core.portage.overlays import get_installed as get_installed_overlays

# USE
from carnage.core.portage.use import UseFlag, get_or_cache_useflags

# Process
from carnage.core.process import TrackedProcess, tracked_run

# GLSA management is resolved lazily: portage.glsa is the single most
# expensive import in the tree, and nothing needs it before the first
# advisory scan runs in a worker.
_LAZY_GLSA = "carnage.core.portage.glsas"


def __getattr__(name: str) -> object:
    """Load the GLSA names on first use (PEP 562)."""
    if name in {"GLSA", "fetch_glsas", "fix_glsas", "fix_glsas_by_ids"}:
        import importlib

        module = importlib.import_module(_LAZY_GLSA)
        value = getattr(module, name)
        globals()[name] = value
        return value

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Grouped by feature rather than alphabetically, which is what a reader wants
# here; ruff would flatten it.
__all__ = [  # noqa: RUF022
    # Cache
    "CacheManager",
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
    "clear_cache",
    # GLSAs
    "GLSA",
    "fetch_glsas",
    "fix_glsas",
    "fix_glsas_by_ids",
    # News
    "News",
    "get_news",
    "mark_news_read",
    "mark_all_news_read",
    "purge_read_news",
    # USE
    "UseFlag",
    "get_or_cache_useflags",
    # Configuration
    "get_config",
    "Configuration",
    # args
    "get_config_path",
    # Process
    "TrackedProcess",
    "tracked_run",
]
