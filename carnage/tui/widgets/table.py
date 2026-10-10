from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.widgets import DataTable


class NavigableDataTable(DataTable):
    """DataTable with vim-like navigation bindings."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("ctrl+d", "page_down", "Page Down", show=False),
        Binding("ctrl+u", "page_up", "Page Up", show=False),
    ]


def row_key_value(event: DataTable.RowSelected) -> str | None:
    """
    String value of the selected row key, if it has one.

    RowKey.value is typed Optional, and every selection handler dereferences
    it - centralize the None check here instead of ignoring it per site.
    """
    if event.row_key is None or event.row_key.value is None:
        return None
    return event.row_key.value
