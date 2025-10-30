"""Main Carnage TUI application."""

from textual.app import App
from textual.binding import Binding

from ..core.config import Configuration, get_config
from .screens.main import MainScreen


class CarnageApp(App):
    """TUI front-end for Portage and eix"""

    TITLE = "carnage"
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
