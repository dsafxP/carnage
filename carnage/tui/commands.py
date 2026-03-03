from os import system

from textual import work
from textual.app import App
from textual.screen import Screen

from carnage.core import Configuration, get_config
from carnage.core.cache import get_cache_manager
from carnage.core.gentoolkit.eclean import eclean_dist, eclean_pkg
from carnage.tui.screens.main_screen import MainScreen


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

@work(thread=True)
async def _run_eclean_dist(app: App) -> None:
    """Worker: run eclean-dist in a thread."""
    returncode, _, stderr = eclean_dist()

    if returncode == 0:
        app.call_from_thread(app.notify, "eclean-dist finished!")
    else:
        app.call_from_thread(
            app.notify,
            f"eclean-dist failed: {stderr.strip()}",
            severity="error",
        )

    app.call_from_thread(app.bell)

@work(thread=True)
async def _run_eclean_pkg(app: App) -> None:
    """Worker: run eclean-pkg in a thread."""
    returncode, _, stderr = eclean_pkg()

    if returncode == 0:
        app.call_from_thread(app.notify, "eclean-pkg finished!")
    else:
        app.call_from_thread(
            app.notify,
            f"eclean-pkg failed: {stderr.strip()}",
            severity="error",
        )

    app.call_from_thread(app.bell)

def run_eclean_dist(app: App) -> None:
    """Clean obsolete distfiles with eclean distfiles"""
    app.notify("Running eclean-dist...", severity="warning", timeout=15)
    _run_eclean_dist(app)

def run_eclean_pkg(app: App) -> None:
    """Clean obsolete binary packages with eclean packages"""
    app.notify("Running eclean-pkg...", severity="warning", timeout=15)
    _run_eclean_pkg(app)