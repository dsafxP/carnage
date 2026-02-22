"""Browse tab widget for searching and managing Gentoo packages."""

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import DataTable, LoadingIndicator

from carnage.core.config import Configuration, get_config
from carnage.core.eix.search import Package, search_packages
from carnage.tui.widgets.browse.package_detail import PackageDetailWidget
from carnage.tui.widgets.table import NavigableDataTable


class BrowseTab(Widget):
    """Widget for browsing Gentoo packages. Handles search and table only."""

    def __init__(self) -> None:
        super().__init__()
        self.packages: list[Package] = []
        self._current_search: str = ""
        self._cancel_search: bool = False
        self._search_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield LoadingIndicator(id="browse-loading")
            yield NavigableDataTable(id="browse-table", cursor_type="row")
            yield Vertical(id="browse-detail")

    def on_mount(self) -> None:
        self._hide_loading()

    def search_packages(self, query: str) -> None:
        """Debounced package search — called by the parent on input changes."""
        config: Configuration = get_config()

        if not query.strip() or len(query.strip()) < config.browse_minimum_characters:
            self._clear_table()
            return

        self._current_search = query

        if self._search_timer:
            self._search_timer.stop()

        self._search_timer = self.set_timer(0.3, lambda: self._perform_search(query))

    @work(exclusive=True, thread=True)
    def _perform_search(self, query: str) -> None:
        """Perform package search in a worker thread."""
        self._cancel_search = True

        loading: LoadingIndicator = self.query_one("#browse-loading", LoadingIndicator)
        table: DataTable = self.query_one("#browse-table", DataTable)

        loading.display = True
        table.display = False

        self._cancel_search = False

        try:
            packages = search_packages(query)
            if not self._cancel_search and self._current_search == query:
                self.app.call_from_thread(self._populate_table, packages)
        except Exception as e:
            if not self._cancel_search:
                self.app.call_from_thread(
                    self.notify, f"Search failed: {e}", severity="error"
                )
        finally:
            if not self._cancel_search:
                self.app.call_from_thread(self._hide_loading)

    def _clear_table(self) -> None:
        table: DataTable = self.query_one("#browse-table", DataTable)
        table.clear(columns=True)
        self.packages = []
        self._remove_detail_widget()

    def _populate_table(self, packages: list[Package]) -> None:
        self.packages = packages
        table: DataTable = self.query_one("#browse-table", DataTable)

        table.clear(columns=True)
        table.add_columns("Package", "Overlay", "Description")

        for i, package in enumerate(packages):
            overlay: str = "?"
            if package.versions:
                repo = package.versions[0].repository
                if repo:
                    overlay = repo
                    if repo != "gentoo" and any(
                        v.repository == "gentoo" for v in package.versions[1:]
                    ):
                        overlay = f"{repo} / gentoo"

            description: str = package.description or "No description"

            if len(description) > 80:
                description = description[:77] + "..."

            installed: bool = package.is_installed()
            name_cell: str = (
                f"[green]✓[/green] {package.category}/[bold]{package.name}[/bold]"
                if installed else
                f"  {package.category}/[bold]{package.name}[/bold]"
            )

            table.add_row(
                name_cell,
                overlay,
                description,
                key=str(i),
            )

    def _hide_loading(self) -> None:
        loading: LoadingIndicator = self.query_one("#browse-loading", LoadingIndicator)
        table: DataTable = self.query_one("#browse-table", DataTable)
        loading.display = False
        table.display = True

    def _remove_detail_widget(self) -> None:
        for widget in self.query(PackageDetailWidget):
            widget.remove()

    def _mount_detail_widget(self, package: Package) -> None:
        self._remove_detail_widget()
        self.query_one("#browse-detail").mount(PackageDetailWidget(package))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is None or event.data_table.id != "browse-table":
            return

        row_index = int(event.row_key.value)  # type: ignore
        if not (0 <= row_index < len(self.packages)):
            return

        package = self.packages[row_index]

        # Don't remount if the same package is already displayed
        existing = self.query(PackageDetailWidget)
        if existing and existing.first().package.full_name == package.full_name:
            return

        self._mount_detail_widget(package)