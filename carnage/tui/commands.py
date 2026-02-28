from os import system

from textual.app import App
from textual.screen import Screen

from carnage.core import Configuration, get_config
from carnage.core.cache import get_cache_manager
from carnage.tui.screens.main_scrn import MainScreen


def toggle_compact_mode(screen: Screen) -> None:
    """Toggle compact mode and save it to settings"""

    config: Configuration = get_config()

    compact: bool = not config.compact_mode

    config.compact_mode = compact

    screen.set_class(compact, "compact")

def clear_cache(app: App) -> None:
    """Clear carnage cache"""

    get_cache_manager().clear()

    app.notify("Cache cleared.")

def eix_update(app: App) -> None:
    """Run eix-update and then restart carnage"""
    with app.suspend():
        system("eix-update")

    app.switch_screen(MainScreen())

def eix_remote_update(app: App) -> None:
    """Run eix-remote update and then restart carnage"""
    with app.suspend():
        system("eix-remote update")

    get_cache_manager().clear() # refresh to use new remote data

    app.switch_screen(MainScreen())