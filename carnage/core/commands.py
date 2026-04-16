"""App-level commands invokable from the command palette and keybindings."""

from textual.app import App
from textual.screen import Screen

from carnage.core import Configuration, get_config
from carnage.core.cache import get_cache_manager
from carnage.core.eix.eix import has_cache, has_remote_cache
from carnage.core.operation import Operation
from carnage.tui.screens.main_screen import MainScreen


def toggle_compact_mode(screen: Screen) -> None:
    """Toggle compact mode and save it to settings."""
    config: Configuration = get_config()

    compact: bool = not config.compact_mode
    config.compact_mode = compact

    screen.set_class(compact, "compact")


def clear_cache(app: App) -> None:
    """Clear carnage cache."""
    get_cache_manager().clear()
    app.notify("Cache cleared.")


def eix_update(app: App) -> None:
    """Run eix-update and reload the main screen."""
    op = Operation(["eix-update"], privilege=not has_cache())

    def on_complete(success: bool) -> None:
        if success:
            app.switch_screen(MainScreen())

        app.bell()

    op.start_in_app(app, on_complete=on_complete)


def eix_remote_update(app: App) -> None:
    """Run eix-remote update and reload the main screen."""
    op = Operation(["eix-remote", "update"], privilege=not has_remote_cache())

    def on_complete(success: bool) -> None:
        if success:
            get_cache_manager().clear()
            app.switch_screen(MainScreen())

        app.bell()

    op.start_in_app(app, on_complete=on_complete)


def run_eclean_dist(app: App) -> None:
    """Clean obsolete distfiles with eclean-dist."""
    app.notify("Running eclean-dist...", severity="warning", timeout=15)

    op = Operation(["eclean-dist"], privilege=True)

    def on_complete(success: bool) -> None:
        app.bell()

    op.start_in_app(app, on_complete=on_complete)


def run_eclean_pkg(app: App) -> None:
    """Clean obsolete binary packages with eclean-pkg."""
    app.notify("Running eclean-pkg...", severity="warning", timeout=15)

    op = Operation(["eclean-pkg"], privilege=True)

    def on_complete(success: bool) -> None:
        app.bell()

    op.start_in_app(app, on_complete=on_complete)


def sync(app: App) -> None:
    """Run emerge --sync and reload the main screen."""
    op = Operation(["emerge", "--sync"], privilege=True)

    def on_complete(success: bool) -> None:
        if success:
            app.switch_screen(MainScreen())

        app.bell()

    op.start_in_app(app, on_complete=on_complete)
