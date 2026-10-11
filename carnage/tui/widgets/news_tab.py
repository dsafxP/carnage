"""News tab widget for displaying Gentoo repository news."""

from collections.abc import Callable
from typing import Any, ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.coordinate import Coordinate
from textual.widgets import Button, DataTable, LoadingIndicator, Rule, Static

from carnage.core import News, get_news, mark_all_news_read, mark_news_read, purge_read_news
from carnage.core.gentoolkit import portage_lock
from carnage.tui.widgets.table import NavigableDataTable, row_key_value
from carnage.tui.widgets.table_tab import TableTab


class NewsTab(TableTab):
    """Widget for displaying and managing Gentoo news."""

    TABLE_ID = "news-table"
    LOADING_ID = "news-loading"

    _SORT_KEYS: ClassVar[dict[str, Callable[[News], Any]]] = {
        "Status": lambda news: news.read,
        "Date": lambda news: news.date,
        "Title": lambda news: news.title.lower(),
    }

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("r", "mark_read", "Mark Read", show=True),
        Binding("a", "mark_all_read", "Mark All Read", show=True),
        Binding("p", "purge", "Purge Read", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.news_items: list[News] = []
        self.selected_news: News | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical():
            yield LoadingIndicator(id="news-loading")
            yield NavigableDataTable(id="news-table", cursor_type="row")

            with Vertical(id="news-detail"):
                with VerticalScroll(id="news-content-scroll"):
                    yield Static("Select a news item to view details", id="news-header")
                    yield Rule(line_style="heavy")
                    yield Static(id="news-content")

                with Vertical(id="news-actions"):
                    yield Button("Mark as Read", id="mark-read-btn", variant="primary")
                    yield Button("Mark all as Read", id="mark-all-read-btn")
                    yield Button("Purge Read", id="purge-btn", variant="error")

    def on_mount(self) -> None:
        """Load news when widget is mounted."""
        self.load_news()

        table: DataTable = self.query_one("#news-table", DataTable)

        table.add_columns("Status", "Date", "Title")
        self._capture_header_labels()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Sort by the clicked column; repeat clicks toggle direction."""
        index = event.column_index
        if not 0 <= index < len(self._header_labels):
            return

        if not self._cycle_sort(self._header_labels[index]):
            return

        self._populate_table(self.news_items)
        self._mark_sorted_column()

    def _apply_sort(self) -> None:
        """Order the displayed items by the active sort spec."""
        if self._sort_column is None:
            return

        self.news_items.sort(key=self._SORT_KEYS[self._sort_column], reverse=self._sort_reverse)

    @work(exclusive=True, thread=True)
    def load_news(self) -> None:
        """Load news items from the system in a worker thread."""
        # Widgets are not thread-safe: every DOM touch goes through the loop.
        self.app.call_from_thread(self._show_loading)

        try:
            # This runs in a thread, so it won't block the UI. Portage is not
            # thread-safe: serialize against the other workers initializing
            # the same trees.
            with portage_lock:
                news_items: list[News] = get_news()

            # Update UI back on main thread
            self.app.call_from_thread(self._populate_table, news_items)
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Failed to load news: {e}", severity="error")
        finally:
            self.app.call_from_thread(self._hide_loading)

    def _populate_table(self, news_items: list[News]) -> None:
        """Populate the table with news items (runs on main thread)."""
        self.news_items = news_items
        self._apply_sort()

        table: DataTable = self.query_one("#news-table", DataTable)

        table.clear()

        for news in self.news_items:
            status: str = "[dim]Read[/]" if news.read else "[green]New[/]"
            table.add_row(status, news.date, news.title, key=str(news.index))

        self.update_button_states()

    def _update_single_row(self, news_index: int) -> None:
        """Update a single row in the table when news is marked as read."""
        table: DataTable = self.query_one("#news-table", DataTable)

        # Find the row index by matching news index in our data
        for i, news in enumerate(self.news_items):
            if news.index == news_index:
                # Update the specific row (add 1 because cursor_row is 0-based but we need the actual row)
                table.update_cell_at(Coordinate(i, 0), "[dim]Read[/]")
                break

        self.update_button_states()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the news table."""
        key_value = row_key_value(event)
        if key_value is None:
            return

        # Find the selected news item
        news_index = int(key_value)
        self.selected_news = next((n for n in self.news_items if n.index == news_index), None)

        if self.selected_news is None:
            return

        # Display news details
        header_widget: Static = self.query_one("#news-header", Static)
        content_widget: Static = self.query_one("#news-content", Static)

        header: str = f"[r]{self.selected_news.title}[/]\n\n"
        header += f"[dim][b]Posted:[/] {self.selected_news.posted or self.selected_news.date}[/]\n"

        if self.selected_news.author:
            header += f"[dim][b]Author:[/] {self.selected_news.author}[/]"

        header_widget.update(header)
        content_widget.update(self.selected_news.content or "[red]No content available[/]")

        # Update button states
        self.update_button_states()

    def update_button_states(self) -> None:
        """Update button visibility and enabled states."""
        mark_read_btn: Button = self.query_one("#mark-read-btn", Button)
        mark_all_btn: Button = self.query_one("#mark-all-read-btn", Button)
        purge_btn: Button = self.query_one("#purge-btn", Button)

        # Check if an operation is running
        is_blocked = self.app.blocked  # type: ignore

        # Enable "Mark all as Read" only if there are unread items and isn't blocked
        has_unread: bool = any(not n.read for n in self.news_items)
        mark_all_btn.disabled = not has_unread or is_blocked
        mark_all_btn.display = has_unread

        # Enable "Mark as Read" only if a news item is selected, unread, and isn't blocked
        can_mark_single: bool = self.selected_news is not None and not self.selected_news.read
        mark_read_btn.disabled = not can_mark_single or is_blocked
        mark_read_btn.display = can_mark_single

        # Enable "Purge Read" only if there are read items and isn't blocked
        has_read: bool = any(n.read for n in self.news_items)
        purge_btn.disabled = not has_read or is_blocked
        purge_btn.display = has_read

    def _action_mark_read(self) -> None:
        """Mark the selected news item as read."""
        mark_read_btn: Button = self.query_one("#mark-read-btn", Button)

        if self.selected_news is None or self.selected_news.read or mark_read_btn.disabled:
            return

        news_index: int = self.selected_news.index
        news_name: str = self.selected_news.name

        mark_read_btn.label = "Marking..."

        def on_complete(success: bool) -> None:
            if success:
                # Update the data
                for news in self.news_items:
                    if news.index == news_index:
                        news.read = True
                        break

                self._update_single_row(news_index)
                self.notify(f"Marked news {news_index} as read")
            else:
                self.notify(f"Failed to mark news {news_index} as read", severity="error")

            mark_read_btn.label = "Mark as Read"

            self.update_button_states()
            self.app.bell()

        mark_news_read(self.app, news_name, on_complete=on_complete)
        self.update_button_states()

    def _action_mark_all_read(self) -> None:
        """Mark all news items as read."""
        mark_all_btn: Button = self.query_one("#mark-all-read-btn", Button)

        if not self.news_items or mark_all_btn.disabled:
            return

        mark_all_btn.label = "Marking..."

        def on_complete(success: bool) -> None:
            if success:
                # Update all items
                for news in self.news_items:
                    news.read = True

                self._populate_table(self.news_items)
                self.notify("Marked all news as read")
            else:
                self.notify("Failed to mark all news as read", severity="error")

            mark_all_btn.label = "Mark all as Read"

            self.update_button_states()
            self.app.bell()

        mark_all_news_read(self.app, on_complete=on_complete)
        self.update_button_states()

    def _action_purge(self) -> None:
        """Purge all read news items."""
        purge_btn: Button = self.query_one("#purge-btn", Button)

        if not self.news_items or purge_btn.disabled:
            return

        purge_btn.label = "Purging..."

        def on_complete(success: bool) -> None:
            if success:
                # Remove read items from our data
                self.news_items = [news for news in self.news_items if not news.read]
                self._populate_table(self.news_items)
                self.notify("Purged all read news")
            else:
                self.notify("Failed to purge read news", severity="error")

            purge_btn.label = "Purge Read"

            self.update_button_states()
            self.app.bell()

        purge_read_news(self.app, on_complete=on_complete)
        self.update_button_states()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "mark-read-btn":
            self._action_mark_read()
        elif event.button.id == "mark-all-read-btn":
            self._action_mark_all_read()
        elif event.button.id == "purge-btn":
            self._action_purge()
