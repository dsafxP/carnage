"""News tab widget for displaying Gentoo repository news."""

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import DataTable, Static, Button
from textual.binding import Binding

from ...core import get_news, mark_news_read, mark_all_news_read, News, purge_read_news


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

    def load_news(self) -> None:
        """Load news items from the system."""
        table: DataTable = self.query_one("#news-table", DataTable)

        # Clear existing data
        table.clear(columns=True)

        # Set up columns
        table.add_columns("Status", "Date", "Title")

        # Load news
        try:
            self.news_items = get_news()
        except Exception as e:
            self.notify(f"Failed to load news: {e}", severity="error")
            return

        # Populate table
        for news in self.news_items:
            status: str = "Read" if news.read else "New"
            table.add_row(status, news.date, news.title, key=str(news.index))

        # Update button states
        self.update_button_states()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the news table."""
        if event.row_key is None:
            return

        # Find the selected news item
        news_index = int(event.row_key.value) #  type: ignore
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


        # Enable "Mark All as Read" only if there are unread items
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

    def action_mark_read(self) -> None:
        """Mark the selected news item as read."""
        if self.selected_news is None or self.selected_news.read:
            return

        try:
            returncode, _, stderr = mark_news_read(self.selected_news.index)

            if returncode == 0:
                self.notify(f"Marked news {self.selected_news.index} as read")
                # Reload news to update status
                self.load_news()
            else:
                self.notify(f"Failed to mark as read: {stderr}", severity="error")
        except Exception as e:
            self.notify(f"Error marking as read: {e}", severity="error")

    def action_mark_all_read(self) -> None:
        """Mark all news items as read."""
        if not self.news_items:
            return

        try:
            returncode, _, stderr = mark_all_news_read()

            if returncode == 0:
                self.notify("Marked all news as read")
                # Reload news to update status
                self.load_news()
            else:
                self.notify(f"Failed to mark all as read: {stderr}", severity="error")
        except Exception as e:
            self.notify(f"Error marking all as read: {e}", severity="error")

    def action_purge(self) -> None:
        """Purge all (read) news items."""
        if not self.news_items:
            return

        try:
            returncode, _, stderr = purge_read_news()

            if returncode == 0:
                self.notify("Purged all read news.")
                # Reload news to update status
                self.load_news()
            else:
                self.notify(f"Failed to purge: {stderr}", severity="error")
        except Exception as e:
            self.notify(f"Error purging: {e}", severity="error")
        

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "mark-read-btn":
            self.action_mark_read()
        elif event.button.id == "mark-all-read-btn":
            self.action_mark_all_read()
        elif event.button.id == "purge-btn":
            self.action_purge()