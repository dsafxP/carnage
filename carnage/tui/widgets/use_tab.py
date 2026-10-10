"""USE flags tab widget for browsing Gentoo USE flags."""

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.timer import Timer
from textual.widgets import DataTable, LoadingIndicator, Static

from carnage.core.cache import get_cache_manager
from carnage.core.config import Configuration, get_config
from carnage.core.eix.search import Package, fetch_packages_by_query
from carnage.core.portage.use import UseFlag, get_or_cache_useflags
from carnage.tui.widgets.table import NavigableDataTable
from carnage.tui.widgets.table_tab import TableTab


class UseFlagsTab(TableTab):
    """Widget for browsing Gentoo USE flags."""

    TABLE_ID = "useflags-table"
    LOADING_ID = "useflags-loading"

    def __init__(self) -> None:
        super().__init__()
        self.useflags: list[UseFlag] = []
        self.filtered_useflags: list[UseFlag] = []
        self.selected_useflag: UseFlag | None = None
        self.cache_manager = get_cache_manager()
        self._current_search: str = ""
        self._pending_selection: str | None = None
        self._cancel_search: bool = False
        self._search_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical():
            yield LoadingIndicator(id="useflags-loading")
            yield NavigableDataTable(id="useflags-table", cursor_type="row")

            with VerticalScroll(id="useflags-content-scroll"):
                yield Static("Select a USE flag to view details", id="useflags-content")
                yield LoadingIndicator(id="useflags-detail-loading")

    def on_mount(self) -> None:
        """Initialize the USE flags tab."""
        self._hide_loading()
        self._hide_detail_loading()

        table: DataTable = self.query_one("#useflags-table", DataTable)

        table.add_columns("USE Flag", "Description")

    def search_useflags(self, query: str) -> None:
        """Debounced USE flag search — called by the parent on input changes."""
        config: Configuration = get_config()

        # Drop any debounce still pending: clearing the box has to cancel the
        # search scheduled for what was typed before it.
        self._stop_pending_search()

        if not query.strip() or len(query.strip()) < config.use_minimum_characters:
            # Clear table when search is empty or too short
            self._clear_table()
            return

        self._current_search = query

        self._search_timer = self.set_timer(0.3, lambda: self._perform_search(query))

    def _stop_pending_search(self) -> None:
        """Drop a search that has been scheduled but has not started yet."""
        if self._search_timer is not None:
            self._search_timer.stop()
            self._search_timer = None

    @work(exclusive=True, thread=True)
    async def _perform_search(self, query: str) -> None:
        """Perform USE flag search in a worker thread."""
        if query != self._current_search:
            # The box changed while this search's debounce timer was pending.
            return

        self._cancel_search = False

        # Widgets are not thread-safe: every DOM touch goes through the loop.
        self.app.call_from_thread(self._show_loading)

        try:
            # Load USE flags from cache or fetch fresh
            useflags: list[UseFlag] = get_or_cache_useflags(self.cache_manager)

            # Filter USE flags based on search query
            filtered: list[UseFlag] = self._filter_useflags(useflags, query)

            # Update UI with results on main thread
            if not self._cancel_search and self._current_search == query:
                self.app.call_from_thread(self._populate_table, filtered)
        except Exception as e:
            if not self._cancel_search:
                self.app.call_from_thread(self.notify, f"Search failed: {e}", severity="error")
        finally:
            # Hide only while this is still the live query: a newer search owns
            # the indicator then, and a cleared box hides it in _clear_table.
            # Unconditionally skipping this used to leave the spinner running
            # forever whenever _cancel_search had been set meanwhile.
            if self._current_search == query:
                self.app.call_from_thread(self._hide_loading)

    @staticmethod
    def _filter_useflags(useflags: list[UseFlag], query: str) -> list[UseFlag]:
        """Filter USE flags by name and description."""
        query_lower: str = query.lower().strip()

        return [
            useflag
            for useflag in useflags
            if (
                query_lower in useflag.name.lower()
                or (useflag.description and query_lower in useflag.description.lower())
            )
        ]

    def _clear_table(self) -> None:
        """Clear the USE flags table."""
        # Nothing will populate the table now: drop the pending search, forget
        # the live query and put the loading indicator away ourselves, since
        # the in-flight worker will no longer consider itself the current one.
        self._stop_pending_search()
        self._cancel_search = True
        self._current_search = ""
        self._hide_loading()

        table: DataTable = self.query_one("#useflags-table", DataTable)
        table.clear()
        self.filtered_useflags = []
        self.selected_useflag = None

        content_widget: Static = self.query_one("#useflags-content", Static)
        content_widget.update("Select a USE flag to view details")
        self._hide_detail_loading()

    def _populate_table(self, useflags: list[UseFlag]) -> None:
        """Populate the table with USE flag search results."""
        self.filtered_useflags = useflags

        table: DataTable = self.query_one("#useflags-table", DataTable)

        table.clear()

        for i, useflag in enumerate(self.filtered_useflags):
            description: str = useflag.description or "Unknown"

            table.add_row(f"[bold]{useflag.name}[/bold]", description, key=str(i))

        # Restore selection if there was a pending one
        if self._pending_selection is not None:
            selected_name: str = self._pending_selection

            for i, useflag in enumerate(self.filtered_useflags):
                if useflag.name == selected_name:
                    # Trigger the selection event to update the UI
                    self.selected_useflag = useflag
                    table.move_cursor(row=i)
                    self._load_useflag_details(useflag)
                    break

            # Clear the pending selection
            self._pending_selection = None

    def _show_detail_loading(self) -> None:
        """Show loading indicator for details."""
        content_widget: Static = self.query_one("#useflags-content", Static)
        detail_loading: LoadingIndicator = self.query_one("#useflags-detail-loading", LoadingIndicator)

        content_widget.display = False
        detail_loading.display = True

    def _hide_detail_loading(self) -> None:
        """Hide loading indicator for details."""
        content_widget: Static = self.query_one("#useflags-content", Static)
        detail_loading: LoadingIndicator = self.query_one("#useflags-detail-loading", LoadingIndicator)

        content_widget.display = True
        detail_loading.display = False

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the USE flags table."""
        if event.row_key is None or event.data_table.id != "useflags-table":
            return

        # Find the selected USE flag using the row index
        row_index = int(event.row_key.value)  # type: ignore
        if 0 <= row_index < len(self.filtered_useflags):
            self.selected_useflag = self.filtered_useflags[row_index]
        else:
            self.selected_useflag = None

        if self.selected_useflag is None:
            return

        # Load details in a worker thread to avoid freezing
        self._load_useflag_details(self.selected_useflag)

    def _load_useflag_details(self, useflag: UseFlag) -> None:
        """Load USE flag details in a worker thread."""
        self._show_detail_loading()
        self._load_useflag_details_worker(useflag)

    @work(exclusive=True, thread=True)
    async def _load_useflag_details_worker(self, useflag: UseFlag) -> None:
        """Worker thread to load USE flag details."""
        try:
            # One eix scan: the count is the length of the list shown below.
            # A separate `--format 1` count query used to re-scan the whole
            # cache for the same fact.
            packages: list[Package] = fetch_packages_by_query(["--use", useflag.name], False)
            package_count: int = len(packages)

            # Format details on main thread
            self.app.call_from_thread(self._display_useflag_details, useflag, package_count, packages)
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Failed to load USE flag details: {e}", severity="error")
            self.app.call_from_thread(self._hide_detail_loading)

    def _display_useflag_details(self, useflag: UseFlag, package_count: int, packages: list[Package]) -> None:
        """Display USE flag details on the main thread."""
        details: str = self._format_useflag_details(useflag, package_count, packages)

        content_widget: Static = self.query_one("#useflags-content", Static)
        content_widget.update(details)
        self._hide_detail_loading()

    @staticmethod
    def _format_useflag_details(useflag: UseFlag, package_count: int, packages: list[Package]) -> str:
        """Format detailed USE flag information for display."""
        parts: list[str] = [f"[r]{useflag.name}[/]\n\n"]

        if useflag.description:
            parts.append(f"{useflag.description}\n\n")

        parts.append(f"[b]Packages:[/] {package_count}\n")

        # Show packages that use this flag
        if packages:
            parts.append("[b]Packages with this flag:[/]\n")
            parts.extend(f"  • {package.full_name}\n" for package in packages)
        else:
            parts.append("[red]No packages found with this flag[/]\n")

        return "".join(parts)
