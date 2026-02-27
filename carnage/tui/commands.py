from textual.app import App
from textual.screen import Screen

from carnage.core import Configuration, get_config
from carnage.core.cache import get_cache_manager


def toggle_compact_mode(screen: Screen) -> None:
    """Toggle compact mode and save it to settings"""

    config: Configuration = get_config()

    compact: bool = not config.compact_mode

    config.compact_mode = compact

    screen.set_class(compact, "compact")

def clear_cache(app: App | None) -> None:
    """Clear carnage cache"""

    get_cache_manager().clear()

    if app:
        app.notify("Cache cleared.")