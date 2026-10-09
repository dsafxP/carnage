"""Browse tab widget for searching and managing Gentoo packages."""

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.timer import Timer
from textual.widgets import DataTable, LoadingIndicator

from carnage.core.config import Configuration, get_config
from carnage.core.eix.search import Package, search_packages
from carnage.core.formatting import package_row_label
from carnage.tui.widgets.browse.package_detail import PackageDetailWidget, default_version
from carnage.tui.widgets.table import NavigableDataTable
from carnage.tui.widgets.table_tab import TableTab


def _exists_in_repo(package: Package) -> bool:
    """
    Whether eix can find the package in a repo.

    Runs a portage query, so it belongs in a worker rather than in the row
    loop of a widget update.
    """
    version = default_version(package)

    if version is None:
        return False

    return version.to_gentoolkit(package.category, package.name).exists_f


class BrowseTab(TableTab):
    """Widget for browsing Gentoo packages. Handles search and table only."""

    TABLE_ID = "browse-table"
    LOADING_ID = "browse-loading"

    def __init__(self) -> None:
        super().__init__()
        self.packages: list[Package] = []
        self._missing_packages: frozenset[str] = frozenset()
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

        table: DataTable = self.query_one("#browse-table", DataTable)

        table.clear()
        table.add_columns("Package", "Overlay", "Description")

    def search_packages(self, query: str) -> None:
        """Debounced package search — called by the parent on input changes."""
        config: Configuration = get_config()

        # Drop any debounce still pending: clearing the box has to cancel the
        # search scheduled for what was typed before it.
        self._stop_pending_search()

        if not query.strip() or len(query.strip()) < config.browse_minimum_characters:
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
    def _perform_search(self, query: str) -> None:
        """Perform package search in a worker thread."""
        if query != self._current_search:
            # The box changed while this search's debounce timer was pending.
            return

        self._cancel_search = False

        # Widgets are not thread-safe: every DOM touch goes through the loop.
        self.app.call_from_thread(self._show_loading)

        try:
            packages = search_packages(query)

            # Resolve the "missing from every repo" mark here: it runs a
            # portage query per row, which would stall the UI in the
            # populate call below.
            missing = frozenset(
                package.full_name for package in packages if not package.is_installed() and not _exists_in_repo(package)
            )

            if not self._cancel_search and self._current_search == query:
                self.app.call_from_thread(self._populate_table, packages, missing)
        except Exception as e:
            if not self._cancel_search:
                self.app.call_from_thread(self.notify, f"Search failed: {e}", severity="error")
        finally:
            # Hide only while this is still the live query: a newer search owns
            # the indicator then, and a cleared box hides it in _clear_table.
            if self._current_search == query:
                self.app.call_from_thread(self._hide_loading)

    def _clear_table(self) -> None:
        # Nothing will populate the table now: drop the pending search, mark
        # the in-flight one obsolete and put the loading indicator away.
        self._stop_pending_search()
        self._cancel_search = True
        self._current_search = ""
        self._hide_loading()

        table: DataTable = self.query_one("#browse-table", DataTable)
        table.clear()
        self.packages = []
        self._remove_detail_widget()

    def _populate_table(self, packages: list[Package], missing: frozenset[str] | None = None) -> None:
        self.packages = packages

        if missing is not None:
            self._missing_packages = missing

        table: DataTable = self.query_one("#browse-table", DataTable)

        table.clear()

        for i, package in enumerate(packages):
            overlay: str = "?"
            if package.versions:
                repo = package.versions[0].repository
                if repo:
                    overlay = repo
                    if repo != "gentoo" and any(v.repository == "gentoo" for v in package.versions[1:]):
                        overlay = f"{repo} / gentoo"

            description: str = package.description or "No description"

            if len(description) > 80:
                description = description[:77] + "..."

            name_cell: str = package_row_label(
                package,
                installed=package.is_installed(),
                exists=package.full_name not in self._missing_packages,
            )

            table.add_row(
                name_cell,
                overlay,
                description,
                key=str(i),
            )

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

    def update_package_installation_status(self, package_name: str, installed: bool) -> None:
        """Update the installation status of a package by searching for its name."""
        # Find current row for this package
        row_key = None
        for i, pkg in enumerate(self.packages):
            if pkg.full_name == package_name:
                row_key = i
                break

        if row_key is None:
            return

        # Now update using the found row
        table = self.query_one("#browse-table", DataTable)
        package = self.packages[row_key]

        # Update the package's installed status
        installed_version = package.installed_version()
        for v in package.versions:
            v.installed = v.id == installed_version.id if installed_version and installed else False

        name_cell = (
            f"[green]✓[/green] {package.category}/[bold]{package.name}[/bold]"
            if installed
            else f"  {package.category}/[bold]{package.name}[/bold]"
        )

        try:
            from textual.coordinate import Coordinate

            table.update_cell_at(Coordinate(row_key, 0), name_cell)
        except Exception:
            self._populate_table(self.packages)
