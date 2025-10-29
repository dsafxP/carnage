"""Eix package management functionality."""

# Basic eix operations
from .eix import (eix_remote_update, eix_update, has_cache,
                  has_protobuf_support, has_remote_cache, is_found)
# Package search
from .search import (Package, PackageVersion, get_packages_with_useflag,
                     search_packages)
# USE flags
from .use import get_all_useflags

__all__ = [
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
    "get_packages_with_useflag"
]
