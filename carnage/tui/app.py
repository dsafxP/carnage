"""Main Carnage TUI application."""

from collections.abc import Iterable
from pathlib import PurePath

from textual.app import App, SystemCommand
from textual.reactive import reactive
from textual.screen import Screen

from carnage.core.args import css_path as arg_custom_css_path
from carnage.core.commands import (
    clear_cache,
    eix_remote_update,
    eix_update,
    run_eclean_dist,
    run_eclean_pkg,
    sync,
    toggle_compact_mode,
)
from carnage.core.config import Configuration, get_config
from carnage.core.eix.eix import is_found
from carnage.tui.screens.main_screen import MainScreen


class CarnageApp(App):
    """TUI front-end for Portage and eix"""

    TITLE = "carnage"

    SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    blocked: reactive[bool] = reactive(False)
    __config: Configuration

    def __init__(self) -> None:
        """Initialize the application."""
        self.__config: Configuration = get_config()

        css_paths: list[str | PurePath] = ["styles.tcss"]

        if arg_custom_css_path.exists():
            css_paths.append(arg_custom_css_path)

        super().__init__(css_path=css_paths)

        self.blocked = False

    def _tick(self) -> None:
        if self.blocked:
            self.sub_title = self.SPINNER[self._frame % len(self.SPINNER)]
            self._frame += 1
        else:
            self.sub_title = ""
            self._frame = 0

    def on_mount(self) -> None:
        """Initialize the application."""
        self.push_screen(MainScreen())
        self.theme = self.__config.theme

        self._frame = 0
        self.set_interval(0.4, self._tick)

    def watch_theme(self, theme: str) -> None:
        """Watch for theme changes."""
        self.__config.theme = theme

    def watch_blocked(self, value: bool) -> None:
        """Watch for block status changes."""
        if not value:
            self.sub_title = ""
            self._frame = 0

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)

        # Toggle compact mode
        yield SystemCommand(
            "Toggle compact mode", toggle_compact_mode.__doc__ or "", lambda: toggle_compact_mode(self.screen)
        )
        # Clear cache
        yield SystemCommand("Clear cache", clear_cache.__doc__ or "", lambda: clear_cache(self))
        # eclean-dist
        yield SystemCommand("Clean distfiles", run_eclean_dist.__doc__ or "", lambda: run_eclean_dist(self))
        # eclean-pkg
        yield SystemCommand("Clean packages", run_eclean_pkg.__doc__ or "", lambda: run_eclean_pkg(self))
        # Sync
        yield SystemCommand("Sync", sync.__doc__ or "", lambda: sync(self))

        # eix
        if is_found():
            # eix-update
            yield SystemCommand("eix update", eix_update.__doc__ or "", lambda: eix_update(self))
            # eix-remote update
            yield SystemCommand("eix remote update", eix_remote_update.__doc__ or "", lambda: eix_remote_update(self))

        # Toggle log pane
        yield SystemCommand(
            "Toggle log view pane",
            "Display or hide the logging output view pane",
            lambda: self.screen._action_toggle_operation_log(),  # type: ignore
        )
