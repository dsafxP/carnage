"""Cache management for Carnage using msgpack."""

import msgpack
from pathlib import Path
from typing import Any
from datetime import datetime, timedelta


class CacheManager:
    """Manages binary cache files using msgpack."""

    def __init__(self, cache_dir: Path | None = None):
        """
        Initialize the cache manager.

        Args:
            cache_dir: Directory to store cache files.
                      Defaults to ~/.cache/carnage/
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "carnage"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """Get the full path for a cache file."""
        return self.cache_dir / f"{key}.msgpack"

    def _get_metadata_path(self, key: str) -> Path:
        """Get the full path for a cache metadata file."""
        return self.cache_dir / f"{key}.meta"

    def set(self, key: str, data: Any) -> None:
        """
        Store data in cache.

        Args:
            key: Cache key (filename without extension).
            data: Data to cache. Must be msgpack-serializable.
        """
        cache_path: Path = self._get_cache_path(key)
        meta_path: Path = self._get_metadata_path(key)

        # Write data
        packed_data: bytes = msgpack.packb(data, use_bin_type=True)
        with open(cache_path, "wb") as f:
            f.write(packed_data)

        # Write metadata (timestamp)
        with open(meta_path, "w") as f:
            f.write(str(datetime.now().timestamp()))

    def get(self, key: str) -> Any | None:
        """
        Retrieve data from cache.

        Args:
            key: Cache key (filename without extension).

        Returns:
            Cached data if exists, None otherwise.
        """
        cache_path: Path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "rb") as f:
                packed_data: bytes = f.read()
            return msgpack.unpackb(packed_data, raw=False)
        except (msgpack.exceptions.UnpackException, OSError):
            # Corrupted or unreadable cache
            return None

    def exists(self, key: str) -> bool:
        """
        Check if cache entry exists.

        Args:
            key: Cache key (filename without extension).

        Returns:
            True if cache exists, False otherwise.
        """
        return self._get_cache_path(key).exists()

    def get_age(self, key: str) -> timedelta | None:
        """
        Get the age of a cache entry.

        Args:
            key: Cache key (filename without extension).

        Returns:
            Age of the cache as timedelta, or None if doesn't exist.
        """
        meta_path: Path = self._get_metadata_path(key)

        if not meta_path.exists():
            return None

        try:
            with open(meta_path, "r") as f:
                timestamp = float(f.read().strip())

            cached_time: datetime = datetime.fromtimestamp(timestamp)
            return datetime.now() - cached_time
        except (ValueError, OSError):
            return None

    def is_stale(self, key: str, max_age: timedelta) -> bool:
        """
        Check if cache entry is stale (older than max_age).

        Args:
            key: Cache key (filename without extension).
            max_age: Maximum age before considering cache stale.

        Returns:
            True if cache is stale or doesn't exist, False otherwise.
        """
        age: timedelta | None = self.get_age(key)

        if age is None:
            return True

        return age > max_age

    def delete(self, key: str) -> bool:
        """
        Delete a cache entry.

        Args:
            key: Cache key (filename without extension).

        Returns:
            True if deleted, False if didn't exist.
        """
        cache_path: Path = self._get_cache_path(key)
        meta_path: Path = self._get_metadata_path(key)

        deleted = False

        if cache_path.exists():
            cache_path.unlink()
            deleted = True

        if meta_path.exists():
            meta_path.unlink()

        return deleted

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of cache entries deleted.
        """
        count = 0

        for path in self.cache_dir.glob("*.msgpack"):
            path.unlink()
            count += 1

        # Also delete metadata files
        for path in self.cache_dir.glob("*.meta"):
            path.unlink()

        return count

    def list_keys(self) -> list[str]:
        """
        List all cache keys.

        Returns:
            List of cache key names.
        """
        return [
            path.stem
            for path in self.cache_dir.glob("*.msgpack")
        ]