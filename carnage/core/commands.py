"""App-level commands invokable from the command palette and keybindings."""

from textual.app import App
from textual.screen import Screen

from carnage.core import Configuration, get_config
from carnage.core.cache import get_cache_manager
from carnage.core.eix.eix import has_cache, has_remote_cache, invalidate_cache, invalidate_remote_cache
from carnage.core.operation import start_operation
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
    """Run eix-update and reload the main screen"""

    def on_complete(success: bool) -> None:
        if success:
            # The probe is memoized: without this, a freshly built cache
            # would stay reported as missing until the app is restarted.
            invalidate_cache()
            app.switch_screen(MainScreen())

        app.bell()

    start_operation(app, "eix.update", default_privilege=not has_cache(), on_complete=on_complete)


def eix_remote_update(app: App) -> None:
    """Run eix-remote update and reload the main screen"""

    def on_complete(success: bool) -> None:
        if success:
            # The probe result is memoized for the process lifetime; without
            # this, search and USE queries keep using non -R eix commands
            # (hiding remote-only packages) until the app is restarted.
            invalidate_remote_cache()
            get_cache_manager().clear()
            app.switch_screen(MainScreen())

        app.bell()

    start_operation(app, "eix.remote-update", default_privilege=not has_remote_cache(), on_complete=on_complete)


def run_eclean_dist(app: App) -> None:
    """Clean obsolete distfiles with eclean-dist"""
    app.notify("Running eclean-dist...", severity="warning", timeout=15)

    start_operation(app, "eclean.dist", default_privilege=True, on_complete=lambda _success: app.bell())


def run_eclean_pkg(app: App) -> None:
    """Clean obsolete binary packages with eclean-pkg"""
    app.notify("Running eclean-pkg...", severity="warning", timeout=15)

    start_operation(app, "eclean.pkg", default_privilege=True, on_complete=lambda _success: app.bell())


def sync(app: App) -> None:
    """Run emerge --sync and reload the main screen"""

    def on_complete(success: bool) -> None:
        if success:
            app.switch_screen(MainScreen())

        app.bell()

    start_operation(app, "emerge.sync", default_privilege=True, on_complete=on_complete)
