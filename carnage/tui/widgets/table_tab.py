"""Base class for the tabs that pair a loading indicator with a data table."""

from collections.abc import Callable
from typing import Any, ClassVar

from rich.text import Text
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

    # Maps a plain header label to a sort key function for its column.
    # Subclasses override this; empty means "not sortable".
    _SORT_KEYS: ClassVar[dict[str, Callable[..., Any]]] = {}

    def __init__(self) -> None:
        super().__init__()
        self._sort_column: str | None = None
        self._sort_reverse: bool = False
        self._header_labels: list[str] = []

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

    def _capture_header_labels(self) -> None:
        """Remember the plain header labels for sort markers (call after add_columns)."""
        self._header_labels = [str(column.label) for column in self.table.ordered_columns]

    def _cycle_sort(self, base_label: str | None) -> bool:
        """
        Toggle the sort spec for a header click.

        Returns False when the column is not sortable.
        """
        if base_label is None or base_label not in self._SORT_KEYS:
            return False

        if self._sort_column == base_label:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = base_label
            self._sort_reverse = False

        return True

    def _mark_sorted_column(self) -> None:
        """Show the sort direction on its header (event loop only)."""
        table = self.table

        for index, base in enumerate(self._header_labels):
            if index >= len(table.ordered_columns):
                break

            mark = ""
            if base == self._sort_column:
                mark = " ▼" if self._sort_reverse else " ▲"

            table.ordered_columns[index].label = Text(f"{base}{mark}")
