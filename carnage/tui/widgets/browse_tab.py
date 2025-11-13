"""Browse tab widget for searching and managing Gentoo packages."""
import asyncio

import textual.markup
from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Button, DataTable, LoadingIndicator, Static

from carnage.core.config import Configuration, get_config
from carnage.core.eix.search import Package, search_packages
from carnage.core.portage.emerge import (emerge_deselect, emerge_install,
                                         emerge_noreplace, emerge_uninstall)
from carnage.tui.widgets.table import NavigableDataTable


class BrowseTab(Widget):
    """Widget for browsing and managing Gentoo packages."""

    def __init__(self):
        super().__init__()
        self.packages: list[Package] = []
        self.selected_package: Package | None = None
        self._current_search: str = ""
        self._cancel_search: bool = False
        self._search_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical():
            yield LoadingIndicator(id="browse-loading")
            yield NavigableDataTable(id="browse-table", cursor_type="row")

            with Vertical(id="browse-detail"):
                with VerticalScroll(id="browse-content-scroll"):
                    yield Static("Search for packages to view details", id="browse-content")

                with Vertical(id="browse-actions"):
                    yield Button("Emerge", id="emerge-btn", variant="primary")
                    yield Button("Depclean", id="depclean-btn", variant="error")
                    yield Button("Deselect", id="deselect-btn", variant="warning")
                    yield Button("Noreplace", id="noreplace-btn", variant="success")

    def on_mount(self) -> None:
        """Initialize the browse tab."""
        self._hide_loading()
        self.update_button_states()

    def search_packages(self, query: str) -> None:
        """Search for packages using eix and update the table."""
        config: Configuration = get_config()

        if not query.strip() or len(query.strip()) < config.browse_minimum_characters:
            # Clear table when search is empty or too short
            self._clear_table()
            return

        self._current_search = query

        # Cancel any pending search timer
        if self._search_timer:
            self._search_timer.stop()

        # Schedule search after a short delay (debouncing)
        self._search_timer = self.set_timer(0.3, lambda: self._perform_search(query))

    @work(exclusive=True, thread=True)
    async def _perform_search(self, query: str) -> None:
        """Perform package search in a worker thread."""
        # Cancel previous search
        self._cancel_search = True

        # Small delay to ensure cancellation is processed
        await asyncio.sleep(0.1)

        loading: LoadingIndicator = self.query_one("#browse-loading", LoadingIndicator)
        table: DataTable = self.query_one("#browse-table", DataTable)

        # Show loading indicator
        loading.display = True
        table.display = False

        # Reset cancellation flag for this search
        self._cancel_search = False

        packages: list[Package] = []

        try:
            # Perform search using eix
            packages = search_packages(query)

            # Only update if this search hasn't been cancelled
            if not self._cancel_search and self._current_search == query:
                # Update UI with results on main thread
                self.app.call_from_thread(self._populate_table, packages)
        except Exception as e:
            if not self._cancel_search:
                self.app.call_from_thread(self.notify, f"Search failed: {e}", severity="error")
        finally:
            if not self._cancel_search:
                self.app.call_from_thread(self._hide_loading)
            # Explicit cleanup
            if 'packages' in locals():
                del packages

    def _clear_table(self) -> None:
        """Clear the package table."""
        table: DataTable = self.query_one("#browse-table", DataTable)
        table.clear(columns=True)
        self.packages = []
        self.selected_package = None

        content_widget: Static = self.query_one("#browse-content", Static)
        content_widget.update("Search for packages to view details")

        self.update_button_states()

    def _populate_table(self, packages: list[Package]) -> None:
        """Populate the table with package search results."""
        self.packages = packages
        table: DataTable = self.query_one("#browse-table", DataTable)

        table.clear(columns=True)
        table.add_columns("Package", "Overlay", "Description")

        for i, package in enumerate(self.packages):
            # Get the primary repository (overlay) from the first version
            overlay: str = "gentoo"  # Default to gentoo
            if package.versions:
                repo: str | None = package.versions[0].repository
                if repo and repo != "gentoo":
                    overlay = repo

            # Truncate description for table display
            description: str = package.description or "No description"
            if len(description) > 80:
                description = description[:77] + "..."

            table.add_row(
                f"{package.category}/[bold]{package.name}[/bold]",
                overlay,
                description,
                key=str(i)
            )

        self.update_button_states()

    def _hide_loading(self) -> None:
        """Hide loading indicator and show table."""
        loading: LoadingIndicator = self.query_one("#browse-loading", LoadingIndicator)
        table: DataTable = self.query_one("#browse-table", DataTable)

        loading.display = False
        table.display = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the package table."""
        if event.row_key is None:
            return

        # Find the selected package using the row index
        row_index = int(event.row_key.value)  # type: ignore
        if 0 <= row_index < len(self.packages):
            self.selected_package = self.packages[row_index]
        else:
            self.selected_package = None

        if self.selected_package is None:
            return

        # Display package details immediately
        content_widget: Static = self.query_one("#browse-content", Static)
        details: str = self._format_package_details(self.selected_package)
        content_widget.update(details)

        # Update button states initially (hide deselect/noreplace until we know world file status)
        self.update_button_states()

        # Load world file status in background
        self._load_world_file_status(self.selected_package)

    def _load_world_file_status(self, package: Package) -> None:
        """Load world file status in a worker thread."""
        self._load_world_file_status_worker(package)

    @work(exclusive=True, thread=True)
    async def _load_world_file_status_worker(self, package: Package) -> None:
        """Worker thread to check world file status."""
        try:
            # Check if package is in world file
            in_world_file: bool = package.is_in_world_file()

            # Update button states on main thread
            self.app.call_from_thread(self._update_buttons_with_world_status, package, in_world_file)
        except:
            # On error, just keep buttons hidden
            self.app.call_from_thread(self._update_buttons_with_world_status, package, False)

    def _update_buttons_with_world_status(self, package: Package, in_world_file: bool) -> None:
        """Update buttons with world file status on main thread."""
        # Only update if this is still the selected package
        if self.selected_package != package:
            return

        # Update the package's world file status (we'll store it for future use)
        # For now, we just update the button states
        emerge_btn: Button = self.query_one("#emerge-btn", Button)
        depclean_btn: Button = self.query_one("#depclean-btn", Button)
        deselect_btn: Button = self.query_one("#deselect-btn", Button)
        noreplace_btn: Button = self.query_one("#noreplace-btn", Button)

        is_installed: bool = package.is_installed()

        # Show emerge/depclean based on installation status
        if is_installed:
            emerge_btn.display = False
            depclean_btn.display = True

            # Show deselect/noreplace based on world file status
            if in_world_file:
                deselect_btn.display = True
                noreplace_btn.display = False
            else:
                deselect_btn.display = False
                noreplace_btn.display = True
        else:
            emerge_btn.display = True
            depclean_btn.display = False
            deselect_btn.display = False
            noreplace_btn.display = False

    @staticmethod
    def _format_package_details(package: Package) -> str:
        """Format detailed package information for display."""
        details: str = f"{package.category}/[bold]{package.name}[/bold]\n\n"

        if package.description:
            details += f"[dim]{package.description}[/dim]\n\n"

        if package.homepage:
            details += f"{package.homepage}\n\n"

        if package.licenses:
            details += f"License(s): {', '.join(package.licenses)}\n\n"

        # Show versions
        for version in package.versions:
            details += f"[bold]{version.id}[/bold]{" (Virtual)" if version.virtual else ""}\n"

            # Show repository/overlay
            repo: str = version.repository or "gentoo"

            # Show installation status
            if version.installed:
                details += "[green]✓ Installed[/green]\n"

            details += f"Overlay: {repo}\n"

            # Show runtime dependencies
            if version.rdepend:
                details += f"Runtime: {textual.markup.escape(version.rdepend)}\n"

            # Show USE flags
            if version.iuse:
                details += f"USE flags: {' '.join(version.iuse)}\n"

            details += "\n"

        return details

    def update_button_states(self) -> None:
        """Update button enabled/disabled states."""
        emerge_btn: Button = self.query_one("#emerge-btn", Button)
        depclean_btn: Button = self.query_one("#depclean-btn", Button)
        deselect_btn: Button = self.query_one("#deselect-btn", Button)
        noreplace_btn: Button = self.query_one("#noreplace-btn", Button)

        # Show appropriate buttons based on installation and world file status
        if self.selected_package:
            is_installed: bool = self.selected_package.is_installed()

            # Show emerge/depclean based on installation status
            if is_installed:
                emerge_btn.display = False
                depclean_btn.display = True

                # Initially hide deselect/noreplace until world file status is loaded
                deselect_btn.display = False
                noreplace_btn.display = False
            else:
                emerge_btn.display = True
                depclean_btn.display = False
                deselect_btn.display = False
                noreplace_btn.display = False
        else:
            # No package selected, hide all action buttons
            emerge_btn.display = False
            depclean_btn.display = False
            deselect_btn.display = False
            noreplace_btn.display = False

    @work(exclusive=True, thread=True)
    async def action_emerge(self) -> None:
        """Install the selected package."""
        if self.selected_package is None or self.selected_package.is_installed():
            return

        emerge_btn: Button = self.query_one("#emerge-btn", Button)
        package_atom: str = self.selected_package.full_name

        self.app.call_from_thread(self.notify, f"Installing {package_atom}... (don't close until finished!)",
                                  severity="warning", timeout=15)

        try:
            emerge_btn.disabled = True

            returncode, stdout, stderr = emerge_install(package_atom)

            if returncode == 0:
                self.app.call_from_thread(self.notify, f"Successfully installed {package_atom}")
                # Refresh search to update installation status
                self.app.call_from_thread(self._refresh_search)

                self.selected_package = None # Lazy solution
            else:
                self.app.call_from_thread(self.notify, f"Failed to install: {stderr}", severity="error")
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Error installing: {e}", severity="error")

        emerge_btn.disabled = False

    @work(exclusive=True, thread=True)
    async def action_depclean(self) -> None:
        """Uninstall the selected package."""
        if self.selected_package is None or not self.selected_package.is_installed():
            return

        depclean_btn: Button = self.query_one("#depclean-btn", Button)
        package_atom: str = self.selected_package.full_name

        self.app.call_from_thread(self.notify, f"Removing {package_atom}... (don't close until finished!)",
                                  severity="warning", timeout=15)

        try:
            depclean_btn.disabled = True

            returncode, stdout, stderr = emerge_uninstall(package_atom)

            if returncode == 0:
                self.app.call_from_thread(self.notify, f"Successfully removed {package_atom}")
                # Refresh search to update installation status
                self.app.call_from_thread(self._refresh_search)

                self.selected_package = None  # Lazy solution
            else:
                self.app.call_from_thread(self.notify, f"Failed to remove: {stderr}", severity="error")
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Error removing: {e}", severity="error")

        depclean_btn.disabled = False

    @work(exclusive=True, thread=True)
    async def action_deselect(self) -> None:
        """Remove package from world file."""
        if self.selected_package is None:
            return

        deselect_btn: Button = self.query_one("#deselect-btn", Button)
        package_atom: str = self.selected_package.full_name

        self.app.call_from_thread(self.notify, f"Removing {package_atom} from world file...",
                                  severity="warning", timeout=10)

        try:
            deselect_btn.disabled = True

            returncode, stdout, stderr = emerge_deselect(package_atom)

            if returncode == 0:
                self.app.call_from_thread(self.notify, f"Successfully removed {package_atom} from world file")
                # Refresh world file status
                if self.selected_package:
                    self._load_world_file_status(self.selected_package)
            else:
                self.app.call_from_thread(self.notify, f"Failed to remove from world file: {stderr}", severity="error")
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Error removing from world file: {e}", severity="error")

        deselect_btn.disabled = False

    @work(exclusive=True, thread=True)
    async def action_noreplace(self) -> None:
        """Add package to world file."""
        if self.selected_package is None:
            return

        noreplace_btn: Button = self.query_one("#noreplace-btn", Button)
        package_atom: str = self.selected_package.full_name

        self.app.call_from_thread(self.notify, f"Adding {package_atom} to world file...",
                                  severity="warning", timeout=10)

        try:
            noreplace_btn.disabled = True

            returncode, stdout, stderr = emerge_noreplace(package_atom)

            if returncode == 0:
                self.app.call_from_thread(self.notify, f"Successfully added {package_atom} to world file")
                # Refresh world file status
                if self.selected_package:
                    self._load_world_file_status(self.selected_package)
            else:
                self.app.call_from_thread(self.notify, f"Failed to add to world file: {stderr}", severity="error")
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Error adding to world file: {e}", severity="error")

        noreplace_btn.disabled = False

    def _refresh_search(self) -> None:
        """Refresh the current search to update installation status."""
        if self._current_search:
            self.search_packages(self._current_search)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "emerge-btn":
            self.action_emerge()
        elif event.button.id == "depclean-btn":
            self.action_depclean()
        elif event.button.id == "deselect-btn":
            self.action_deselect()
        elif event.button.id == "noreplace-btn":
            self.action_noreplace()