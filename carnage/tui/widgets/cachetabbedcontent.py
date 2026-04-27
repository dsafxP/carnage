"""Cached tabbed content that remembers the last selected tab."""

from typing import Any

from textual.widgets import Tab, TabbedContent

from carnage.core.cache import get_cache_manager


class CachedTabbedContent(TabbedContent):
    """
    TabbedContent that caches the last selected tab across sessions.

    The tab selection is saved to the cache when changed and restored
    when the widget is mounted.

    Args:
        cache_key: Unique key for storing tab selection in cache.
        initial: Initial tab to show if no cached value exists.
        *args: Additional positional arguments for TabbedContent.
        **kwargs: Additional keyword arguments for TabbedContent.
    """

    def __init__(
        self,
        cache_key: str,
        initial: str = "",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(initial, *args, **kwargs)
        self._cache_key = cache_key
        self._cache_manager = get_cache_manager()
        self._initial_tab = initial

    def on_mount(self) -> None:
        """Restore the last selected tab from cache when mounted."""
        self.call_later(self._restore_tab)

    def on_unmount(self) -> None:
        """Save the current tab selection when widget is being destroyed."""
        try:
            current_tab = self.active

            if current_tab:
                self._cache_manager.set(self._cache_key, current_tab)
        except Exception:
            pass

    def _save_tab(self, tab_id: str) -> None:
        """Save the current tab ID to cache."""
        try:
            self._cache_manager.set(self._cache_key, tab_id)
        except Exception:
            # Fail silently - cache is non-critical
            pass

    def _restore_tab(self) -> None:
        """Restore the last selected tab from cache."""
        try:
            cached_tab: str | None = self._cache_manager.get(self._cache_key)

            if cached_tab:
                to_tab: Tab = self.get_tab(cached_tab)

                if not to_tab.disabled:
                    self.active = cached_tab
        except Exception:
            pass

    def reset_cache(self) -> None:
        """Clear the cached tab selection."""
        try:
            self._cache_manager.delete(self._cache_key)
        except Exception:
            pass
