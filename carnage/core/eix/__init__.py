"""Eix package management functionality."""

# Basic eix operations
from .eix import (eix_remote_update, eix_update, has_cache,
                  has_protobuf_support, has_remote_cache, is_found)
# Overlay
from .overlay import NO_CACHE_PACKAGE_COUNT, get_package_count
# Package search
from .search import (Package, PackageVersion, get_packages_with_useflag,
                     search_packages)
# USE flags
from .use import get_all_useflags

__all__: list[str] = [
    # Eix operations
    "is_found",
    "has_cache",
    "has_remote_cache",
    "has_protobuf_support",
    "eix_update",
    "eix_remote_update",
    # Search
    "Package",
    "PackageVersion",
    "search_packages",
    "get_packages_with_useflag",
    # USE
    "get_all_useflags",
    # Overlay
    "get_package_count",
    "NO_CACHE_PACKAGE_COUNT"
]
