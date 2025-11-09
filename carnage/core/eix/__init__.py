"""Eix package management functionality."""

# Basic eix operations
from carnage.core.eix.eix import (eix_remote_update, eix_update, has_cache,
                                  has_protobuf_support, has_remote_cache,
                                  is_found)
# Overlay
from carnage.core.eix.overlay import NO_CACHE_PACKAGE_COUNT, get_package_count
# Package search
from carnage.core.eix.search import (Package, PackageVersion,
                                     fetch_packages_by_query,
                                     get_package_by_atom, search_packages)
# USE flags
from carnage.core.eix.use import get_all_useflags

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
    "fetch_packages_by_query",
    "get_package_by_atom",
    "search_packages",
    # USE
    "get_all_useflags",
    # Overlay
    "get_package_count",
    "NO_CACHE_PACKAGE_COUNT"
]
