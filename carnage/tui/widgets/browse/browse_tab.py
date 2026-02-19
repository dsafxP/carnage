"""Browse tab widget for searching and managing Gentoo packages."""

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Button, DataTable, LoadingIndicator

from carnage.core.config import Configuration, get_config
from carnage.core.eix.search import Package, search_packages
from carnage.core.portage.emerge import (emerge_deselect, emerge_install,
                                         emerge_noreplace, emerge_uninstall)
from carnage.tui.widgets.browse.package_detail import PackageDetailWidget
from carnage.tui.widgets.table import NavigableDataTable


class BrowseTab(Widget):
    """Widget for browsing and managing Gentoo packages."""

    BINDINGS = [
        Binding("e", "emerge", "Emerge", show=True),
        Binding("c", "depclean", "Depclean", show=True),
        Binding("w", "deselect", "Deselect", show=True),
        Binding("n", "noreplace", "Noreplace", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.packages: list[Package] = []
        self.selected_package: Package | None = None
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
        self.selected_package = None
        self._remove_detail_widget()

    def _populate_table(self, packages: list[Package]) -> None:
        self.packages = packages
        table: DataTable = self.query_one("#browse-table", DataTable)

        table.clear(columns=True)
        table.add_columns("Package", "Overlay", "Description")

        for i, package in enumerate(packages):
            overlay = "?"
            if package.versions:
                repo = package.versions[0].repository
                if repo:
                    overlay = repo
                    if repo != "gentoo" and any(
                        v.repository == "gentoo" for v in package.versions[1:]
                    ):
                        overlay = f"{repo} / gentoo"

            description = package.description or "No description"
            if len(description) > 80:
                description = description[:77] + "..."

            table.add_row(
                f"{package.category}/[bold]{package.name}[/bold]",
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

    def _update_detail_buttons(self, package: Package, in_world_file: bool) -> None:
        """Forward world file status to the detail widget if it's still current."""
        if self.selected_package != package:
            return
        for widget in self.query(PackageDetailWidget):
            widget.update_buttons(in_world_file=in_world_file)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is None or event.data_table.id != "browse-table":
            return

        row_index = int(event.row_key.value)  # type: ignore
        if not (0 <= row_index < len(self.packages)):
            return

        self.selected_package = self.packages[row_index]
        self._mount_detail_widget(self.selected_package)
        self._load_world_file_status(self.selected_package)

    @work(exclusive=True, thread=True)
    def _load_world_file_status(self, package: Package) -> None:
        """Check world file membership in a thread and forward to the detail widget."""
        try:
            in_world_file: bool = package.is_in_world_file()
        except:
            in_world_file = False
        self.app.call_from_thread(self._update_detail_buttons, package, in_world_file)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "emerge-btn":
            self.action_emerge()
        elif event.button.id == "depclean-btn":
            self.action_depclean()
        elif event.button.id == "deselect-btn":
            self.action_deselect()
        elif event.button.id == "noreplace-btn":
            self.action_noreplace()

    @work(exclusive=True, thread=True)
    def action_emerge(self) -> None:
        if self.selected_package is None or self.selected_package.is_installed():
            return

        package_atom = self.selected_package.full_name
        self.app.call_from_thread(
            self.notify,
            f"Installing {package_atom}... (don't close until finished!)",
            severity="warning",
            timeout=15,
        )

        try:
            returncode, _, stderr = emerge_install(package_atom)
            if returncode == 0:
                self.app.call_from_thread(
                    self.notify, f"Successfully installed {package_atom}"
                )
                self.selected_package = None
                self.app.call_from_thread(self._refresh_search)
            else:
                self.app.call_from_thread(
                    self.notify, f"Failed to install: {stderr}", severity="error"
                )
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Error installing: {e}", severity="error"
            )

    @work(exclusive=True, thread=True)
    def action_depclean(self) -> None:
        if self.selected_package is None or not self.selected_package.is_installed():
            return

        package_atom = self.selected_package.full_name
        self.app.call_from_thread(
            self.notify,
            f"Removing {package_atom}... (don't close until finished!)",
            severity="warning",
            timeout=15,
        )

        try:
            returncode, _, stderr = emerge_uninstall(package_atom)
            if returncode == 0:
                self.app.call_from_thread(
                    self.notify, f"Successfully removed {package_atom}"
                )
                self.selected_package = None
                self.app.call_from_thread(self._refresh_search)
            else:
                self.app.call_from_thread(
                    self.notify, f"Failed to remove: {stderr}", severity="error"
                )
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Error removing: {e}", severity="error"
            )

    @work(exclusive=True, thread=True)
    def action_deselect(self) -> None:
        if self.selected_package is None:
            return

        package_atom = self.selected_package.full_name
        self.app.call_from_thread(
            self.notify,
            f"Removing {package_atom} from world file...",
            severity="warning",
            timeout=10,
        )

        try:
            returncode, _, stderr = emerge_deselect(package_atom)
            if returncode == 0:
                self.app.call_from_thread(
                    self.notify,
                    f"Successfully removed {package_atom} from world file",
                )
                if self.selected_package:
                    self._load_world_file_status(self.selected_package)
            else:
                self.app.call_from_thread(
                    self.notify,
                    f"Failed to remove from world file: {stderr}",
                    severity="error",
                )
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Error removing from world file: {e}", severity="error"
            )

    @work(exclusive=True, thread=True)
    def action_noreplace(self) -> None:
        if self.selected_package is None:
            return

        package_atom = self.selected_package.full_name
        self.app.call_from_thread(
            self.notify,
            f"Adding {package_atom} to world file...",
            severity="warning",
            timeout=10,
        )

        try:
            returncode, _, stderr = emerge_noreplace(package_atom)
            if returncode == 0:
                self.app.call_from_thread(
                    self.notify,
                    f"Successfully added {package_atom} to world file",
                )
                if self.selected_package:
                    self._load_world_file_status(self.selected_package)
            else:
                self.app.call_from_thread(
                    self.notify,
                    f"Failed to add to world file: {stderr}",
                    severity="error",
                )
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Error adding to world file: {e}", severity="error"
            )

    def _refresh_search(self) -> None:
        if self._current_search:
            self.search_packages(self._current_search)