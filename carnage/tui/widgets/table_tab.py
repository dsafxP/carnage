"""Base class for the tabs that pair a loading indicator with a data table."""

from typing import ClassVar

from textual.widget import Widget
from textual.widgets import DataTable, LoadingIndicator


class TableTab(Widget):
    """
    A tab whose content is a loading indicator sitting over a data table.

    Subclasses only name the two widgets. The show/hide helpers live here so
    the "widgets are not thread-safe" rule has a single implementation: both
    are meant to be reached from the event loop, which the workers do through
    call_from_thread.
    """

    TABLE_ID: ClassVar[str]
    LOADING_ID: ClassVar[str]

    @property
    def table(self) -> DataTable:
        """The tab's data table (event loop only)."""
        return self.query_one(f"#{self.TABLE_ID}", DataTable)

    @property
    def loading_widget(self) -> LoadingIndicator:
        """The tab's loading indicator (event loop only)."""
        return self.query_one(f"#{self.LOADING_ID}", LoadingIndicator)

    def _show_loading(self) -> None:
        """Show the loading indicator and hide the table (event loop only)."""
        self.loading_widget.display = True
        self.table.display = False

    def _hide_loading(self) -> None:
        """Hide the loading indicator and show the table (event loop only)."""
        self.loading_widget.display = False
        self.table.display = True
