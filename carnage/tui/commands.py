from textual.screen import Screen

from carnage.core import Configuration, get_config


def toggle_compact_mode(screen: Screen) -> None:
    """Toggle compact mode and save it to settings."""

    config: Configuration = get_config()

    compact: bool = not config.compact_mode

    config.compact_mode = compact

    screen.set_class(compact, "compact")