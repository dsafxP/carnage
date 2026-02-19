"""Main Carnage TUI application."""

from pathlib import PurePath
from typing import List

from textual.app import App

from carnage.core.config import Configuration, get_config
from carnage.tui.screens.main_scrn import MainScreen


class CarnageApp(App[None]):
    """TUI front-end for Portage and eix"""

    TITLE = "carnage"

    def __init__(self) -> None:
        """Initialize the application with configuration."""
        css_paths: List[str | PurePath] = ["styles/styles.tcss"]

        self.config: Configuration = get_config()

        if self.config.compact_mode:
            css_paths.append("styles/compact.tcss")

        super().__init__(css_path=css_paths)

    def on_mount(self) -> None:
        """Initialize the application."""
        self.push_screen(MainScreen())
        self.theme = self.config.theme

    def watch_theme(self, theme: str) -> None:
        """Watch for theme changes."""
        self.config.theme = theme


def run() -> None:
    """Run the Carnage TUI application."""
    app: CarnageApp = CarnageApp()
    app.run()