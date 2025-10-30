"""Main Carnage TUI application."""

from textual.app import App

from ..core.config import Configuration, get_config
from .screens.main_scrn import MainScreen


class CarnageApp(App[None]):
    """TUI front-end for Portage and eix"""

    TITLE = "carnage"
    CSS_PATH = "styles.tcss"

    def on_mount(self) -> None:
        """Initialize the application."""
        self.push_screen(MainScreen())

        config: Configuration = get_config()

        self.theme = config.theme

    @staticmethod
    def watch_theme(theme: str) -> None:
        config: Configuration = get_config()

        config.theme = theme


def run() -> None:
    """Run the Carnage TUI application."""
    app: CarnageApp = CarnageApp()
    app.run()
