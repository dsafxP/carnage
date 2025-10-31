"""News tab widget for displaying Gentoo repository news."""

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.coordinate import Coordinate
from textual.widget import Widget
from textual.widgets import Button, DataTable, LoadingIndicator, Static

from carnage.core import (News, get_news, mark_all_news_read, mark_news_read,
                          purge_read_news)


class NewsTab(Widget):
    """Widget for displaying and managing Gentoo news."""

    BINDINGS = [
        Binding("r", "mark_read", "Mark as Read"),
        Binding("a", "mark_all_read", "Mark all Read"),
        Binding("p", "purge", "Purge Read"),
    ]

    def __init__(self):
        super().__init__()
        self.news_items: list[News] = []
        self.selected_news: News | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical():
            yield LoadingIndicator(id="news-loading")
            yield DataTable(id="news-table", cursor_type="row")

            with Vertical(id="news-detail"):
                with VerticalScroll(id="news-content-scroll"):
                    yield Static("Select a news item to view details", id="news-content")

                with Vertical(id="news-actions"):
                    yield Button("Mark as Read", id="mark-read-btn", variant="primary")
                    yield Button("Mark all as Read", id="mark-all-read-btn")
                    yield Button("Purge Read", id="purge-btn", variant="error")

    def on_mount(self) -> None:
        """Load news when widget is mounted."""
        self.load_news()

    @work(exclusive=True, thread=True)
    async def load_news(self) -> None:
        """Load news items from the system in a worker thread."""
        loading: LoadingIndicator = self.query_one("#news-loading", LoadingIndicator)
        table: DataTable = self.query_one("#news-table", DataTable)

        loading.display = True
        table.display = False

        try:
            # This runs in a thread, so it won't block the UI
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
        table: DataTable = self.query_one("#news-table", DataTable)

        table.clear(columns=True)
        table.add_columns("Status", "Date", "Title")

        for news in self.news_items:
            status: str = "Read" if news.read else "New"
            table.add_row(status, news.date, news.title, key=str(news.index))

        self.update_button_states()

    def _update_single_row(self, news_index: int) -> None:
        """Update a single row in the table when news is marked as read."""
        table: DataTable = self.query_one("#news-table", DataTable)

        # Find the row index by matching news index in our data
        for i, news in enumerate(self.news_items):
            if news.index == news_index:
                # Update the specific row (add 1 because cursor_row is 0-based but we need the actual row)
                table.update_cell_at(Coordinate(i, 0), "Read")
                break

        self.update_button_states()

    def _remove_read_rows(self) -> None:
        """Remove all read news from the table and data."""
        table: DataTable = self.query_one("#news-table", DataTable)
        
        # Remove read items from our data
        self.news_items = [news for news in self.news_items if not news.read]
        
        # Clear and repopulate table with remaining items
        table.clear(columns=True)
        table.add_columns("Status", "Date", "Title")

        for news in self.news_items:
            status: str = "Read" if news.read else "New"
            table.add_row(status, news.date, news.title, key=str(news.index))

        # Clear selection if the selected news was purged
        if self.selected_news and self.selected_news.read:
            self.selected_news = None
            content_widget: Static = self.query_one("#news-content", Static)
            content_widget.update("Select a news item to view details")

        self.update_button_states()

    def _hide_loading(self) -> None:
        """Hide loading indicator and show table."""
        loading: LoadingIndicator = self.query_one("#news-loading", LoadingIndicator)
        table: DataTable = self.query_one("#news-table", DataTable)

        loading.display = False
        table.display = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the news table."""
        if event.row_key is None:
            return

        # Find the selected news item
        news_index = int(event.row_key.value)  # type: ignore
        self.selected_news = next(
            (n for n in self.news_items if n.index == news_index),
            None
        )

        if self.selected_news is None:
            return

        # Display news details
        content_widget: Static = self.query_one("#news-content", Static)

        # Format the news content
        details: str = f"[bold]{self.selected_news.title}[/bold]\n\n"
        details += f"[dim]Posted: {self.selected_news.posted or self.selected_news.date}[/dim]\n"

        if self.selected_news.author:
            details += f"[dim]Author: {self.selected_news.author}[/dim]\n"

        details += "\n" + "-" * 60 + "\n\n"

        if self.selected_news.content:
            details += self.selected_news.content
        else:
            details += "[dim]No content available[/dim]"

        content_widget.update(details)

        # Update button states
        self.update_button_states()

    def update_button_states(self) -> None:
        """Update button enabled/disabled states."""
        mark_read_btn: Button = self.query_one("#mark-read-btn", Button)
        mark_all_btn: Button = self.query_one("#mark-all-read-btn", Button)
        purge_btn: Button = self.query_one("#purge-btn", Button)

        # Enable "Mark all as Read" only if there are unread items
        has_unread: bool = any(not n.read for n in self.news_items)
        mark_all_btn.disabled = not has_unread

        # Enable "Mark as Read" only if a news item is selected and unread
        if has_unread and self.selected_news and not self.selected_news.read:
            mark_read_btn.disabled = False
        else:
            mark_read_btn.disabled = True

        # Enable "Purge Read" only if there are read items
        has_read: bool = any(n.read for n in self.news_items)
        purge_btn.disabled = not has_read

    @work(exclusive=True, thread=True)
    async def action_mark_read(self) -> None:
        """Mark the selected news item as read."""
        if self.selected_news is None or self.selected_news.read:
            return

        news_index: int = self.selected_news.index

        try:
            returncode, _, stderr = mark_news_read(news_index)

            if returncode == 0:
                self.app.call_from_thread(self.notify, f"Marked news {news_index} as read")

                # Update the data and refresh just that row
                for news in self.news_items:
                    if news.index == news_index:
                        news.read = True
                        break

                self.app.call_from_thread(self._update_single_row, news_index)
            else:
                self.app.call_from_thread(self.notify, f"Failed to mark as read: {stderr}", severity="error")
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Error marking as read: {e}", severity="error")

    @work(exclusive=True, thread=True)
    async def action_mark_all_read(self) -> None:
        """Mark all news items as read."""
        if not self.news_items:
            return

        try:
            returncode, _, stderr = mark_all_news_read()

            if returncode == 0:
                self.app.call_from_thread(self.notify, "Marked all news as read")
                # Update all items in data and refresh table
                for news in self.news_items:
                    news.read = True
                self.app.call_from_thread(self._populate_table, self.news_items)
            else:
                self.app.call_from_thread(self.notify, f"Failed to mark all as read: {stderr}", severity="error")
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Error marking all as read: {e}", severity="error")

    @work(exclusive=True, thread=True)
    async def action_purge(self) -> None:
        """Purge all read news items."""
        if not self.news_items:
            return

        try:
            returncode, _, stderr = purge_read_news()

            if returncode == 0:
                self.app.call_from_thread(self.notify, "Purged all read news.")
                # Just remove read items from our data and table
                self.app.call_from_thread(self._remove_read_rows)
            else:
                self.app.call_from_thread(self.notify, f"Failed to purge: {stderr}", severity="error")
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Error purging: {e}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "mark-read-btn":
            self.action_mark_read()
        elif event.button.id == "mark-all-read-btn":
            self.action_mark_all_read()
        elif event.button.id == "purge-btn":
            self.action_purge()
