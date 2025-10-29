"""USE flags tab widget for browsing Gentoo USE flags."""


from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import DataTable, LoadingIndicator, Static

from ...core.cache import CacheManager
from ...core.config import Configuration, get_config
from ...core.eix import Package, get_packages_with_useflag
from ...core.eix.use import get_package_count_for_useflag
from ...core.use import UseFlag, get_or_cache_useflags


class UseFlagsTab(Widget):
    """Widget for browsing Gentoo USE flags."""

    def __init__(self):
        super().__init__()
        self.useflags: list[UseFlag] = []
        self.filtered_useflags: list[UseFlag] = []
        self.selected_useflag: UseFlag | None = None
        self.cache_manager = CacheManager()
        self._current_search: str = ""
        self._pending_selection: str | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical():
            yield LoadingIndicator(id="useflags-loading")
            yield DataTable(id="useflags-table", cursor_type="row")

            with Vertical(id="useflags-detail"):
                with VerticalScroll(id="useflags-content-scroll"):
                    yield Static("Select a USE flag to view details", id="useflags-content")
                    yield LoadingIndicator(id="useflags-detail-loading")

    def on_mount(self) -> None:
        """Initialize the USE flags tab."""
        self._hide_loading()
        self._hide_detail_loading()

    def search_useflags(self, query: str) -> None:
        """Search for USE flags and update the table."""
        config: Configuration = get_config()

        if not query.strip() or len(query.strip()) < config.use_minimum_characters:
            # Clear table when search is empty or too short
            self._clear_table()
            return

        self._current_search = query
        self._perform_search(query)

    @work(exclusive=True, thread=True)
    async def _perform_search(self, query: str) -> None:
        """Perform USE flag search in a worker thread."""
        loading: LoadingIndicator = self.query_one("#useflags-loading", LoadingIndicator)
        table: DataTable = self.query_one("#useflags-table", DataTable)

        # Show loading indicator
        loading.display = True
        table.display = False

        try:
            # Load USE flags from cache or fetch fresh
            useflags: list[UseFlag] = get_or_cache_useflags(self.cache_manager)

            # Filter USE flags based on search query
            filtered: list[UseFlag] = self._filter_useflags(useflags, query)

            # Update UI with results on main thread
            self.app.call_from_thread(self._populate_table, filtered)
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Search failed: {e}", severity="error")
        finally:
            self.app.call_from_thread(self._hide_loading)

    @staticmethod
    def _filter_useflags(useflags: list[UseFlag], query: str) -> list[UseFlag]:
        """Filter USE flags by name and description."""
        query_lower: str = query.lower().strip()

        return [
            useflag for useflag in useflags
            if (query_lower in useflag.name.lower() or
                (useflag.description and query_lower in useflag.description.lower()))
        ]

    def _clear_table(self) -> None:
        """Clear the USE flags table."""
        table: DataTable = self.query_one("#useflags-table", DataTable)
        table.clear(columns=True)
        self.filtered_useflags = []
        self.selected_useflag = None

        content_widget: Static = self.query_one("#useflags-content", Static)
        content_widget.update("Search for USE flags to view details")
        self._hide_detail_loading()

    def _populate_table(self, useflags: list[UseFlag]) -> None:
        """Populate the table with USE flag search results."""
        self.filtered_useflags = useflags
        table: DataTable = self.query_one("#useflags-table", DataTable)

        table.clear(columns=True)
        table.add_columns("USE Flag", "Description")

        for i, useflag in enumerate(self.filtered_useflags):
            description: str = useflag.description or "Unknown"

            table.add_row(
                f"[bold]{useflag.name}[/bold]",
                description,
                key=str(i)
            )

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

    def _hide_loading(self) -> None:
        """Hide loading indicator and show table."""
        loading: LoadingIndicator = self.query_one("#useflags-loading", LoadingIndicator)
        table: DataTable = self.query_one("#useflags-table", DataTable)

        loading.display = False
        table.display = True

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
        if event.row_key is None:
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
            # Get package count and packages for this USE flag
            package_count: int = get_package_count_for_useflag(useflag.name)
            packages: list[Package] = get_packages_with_useflag(useflag.name)

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
        details: str = f"[bold]{useflag.name}[/bold]\n\n"

        if useflag.description:
            details += f"[dim]{useflag.description}[/dim]\n\n"

        details += f"Packages: {package_count}\n"

        # Show packages that use this flag
        if packages:
            details += "Packages with this flag:\n"
            for package in packages:
                details += f"  • {package.full_name}"
                details += "\n"
        else:
            details += "No packages found with this flag\n"

        return details
