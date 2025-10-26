"""Main Carnage TUI application."""

from textual.app import App
from textual.binding import Binding

from .screens.main import MainScreen
from ..core.config import get_config, Configuration


class CarnageApp(App):
    """A TUI front-end for Gentoo package management."""

    TITLE = "Carnage"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def on_mount(self) -> None:
        """Initialize the application."""
        self.push_screen(MainScreen())

        config: Configuration = get_config()

        self.theme = config.theme

    @staticmethod
    def watch_theme(theme: str) -> None:
        config: Configuration = get_config()

        config.theme = theme

    async def action_quit(self) -> None:
        """Quit the application."""
        self.exit()


def run() -> None:
    """Run the Carnage TUI application."""
    app = CarnageApp()
    app.run()