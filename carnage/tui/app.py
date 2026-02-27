"""Main Carnage TUI application."""

from pathlib import PurePath
from typing import Iterable, List

from textual.app import App, SystemCommand
from textual.screen import Screen

from carnage.core.args import css_path as arg_custom_css_path
from carnage.core.config import Configuration, get_config
from carnage.tui.commands import clear_cache, toggle_compact_mode
from carnage.tui.screens.main_scrn import MainScreen


class CarnageApp(App):
    """TUI front-end for Portage and eix"""

    TITLE = "carnage"

    def __init__(self) -> None:
        """Initialize the application with configuration."""
        css_paths: List[str | PurePath] = ["styles.tcss"]

        self.config: Configuration = get_config()

        if arg_custom_css_path.exists():
            css_paths.append(arg_custom_css_path)

        super().__init__(css_path=css_paths)

    def on_mount(self) -> None:
        """Initialize the application."""
        self.push_screen(MainScreen())
        self.theme = self.config.theme

    def watch_theme(self, theme: str) -> None:
        """Watch for theme changes."""
        self.config.theme = theme

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)

        # Toggle compact mode
        yield SystemCommand("Toggle compact mode", toggle_compact_mode.__doc__ or "",
                            lambda: toggle_compact_mode(self.screen))
        # Clear cache
        yield SystemCommand("Clear cache", clear_cache.__doc__ or "",
                            lambda: clear_cache(self))


def run() -> None:
    """Run the Carnage TUI application."""
    app: CarnageApp = CarnageApp()
    app.run()