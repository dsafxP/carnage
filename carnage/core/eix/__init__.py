"""Eix package management functionality."""

# Basic eix operations
from .eix import (
    is_found,
    has_cache,
    has_remote_cache,
    has_protobuf_support,
    eix_update,
    eix_remote_update,
)

# Package search
from .search import Package, PackageVersion, search_packages

# USE flags
from .use import get_all_useflags, get_packages_with_useflag

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
]