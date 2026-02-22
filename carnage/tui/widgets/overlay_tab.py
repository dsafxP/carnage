"""Overlays tab widget for managing Gentoo overlays."""

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, DataTable, LoadingIndicator, Static

from carnage.core.cache import CacheManager
from carnage.core.config import get_config
from carnage.core.eix.eix import has_remote_cache, is_found
from carnage.core.portage.overlays import Overlay, clear_cache, get_or_cache
from carnage.tui.widgets.table import NavigableDataTable


class OverlaysTab(Widget):
    """Widget for displaying and managing Gentoo overlays."""

    BINDINGS = [
        Binding("r", "remove", "Remove", show=True),
        Binding("s", "enable_sync", "Enable & Sync", show=True)
    ]

    def __init__(self):
        super().__init__()
        self.overlays: list[Overlay] = []
        self.filtered_overlays: list[Overlay] = []
        self.selected_overlay: Overlay | None = None
        self.cache_manager = CacheManager()
        self._pending_selection: str | None = None
        self._current_filter: str = ""
        self._config = get_config()
        self.should_skip_pkg_count = self._config.skip_package_counting or not is_found()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical():
            yield LoadingIndicator(id="overlays-loading")
            yield NavigableDataTable(id="overlays-table", cursor_type="row")

            with Vertical(id="overlays-detail"):
                with VerticalScroll(id="overlays-content-scroll"):
                    yield Static("Select an overlay to view details", id="overlays-content")

                with Vertical(id="overlays-actions"):
                    yield Button("Enable & Sync", id="enable-sync-btn", variant="primary")
                    yield Button("Remove", id="remove-btn", variant="error")

    def on_mount(self) -> None:
        """Load overlays when widget is mounted."""
        self.load_overlays()

    def apply_filter(self, filter_text: str) -> None:
        """Apply search filter to overlays and update the table."""
        self._current_filter = filter_text.lower().strip()

        if not self._current_filter:
            # No filter, show all overlays
            self.filtered_overlays = self.overlays.copy()
        else:
            # Filter overlays by name and description
            self.filtered_overlays = [
                overlay for overlay in self.overlays
                if (self._current_filter in overlay.name.lower() or
                    (overlay.description and self._current_filter in overlay.description.lower()))
            ]

        # Update the table with filtered results
        self._populate_table()

    def _populate_table(self) -> None:
        """Populate the table with filtered overlays."""
        table: DataTable = self.query_one("#overlays-table", DataTable)

        # Clear current selection when filtering
        self.selected_overlay = None
        content_widget: Static = self.query_one("#overlays-content", Static)
        content_widget.update("Select an overlay to view details")

        table.clear(columns=True)

        # Only show package count column if counting is enabled
        if self.should_skip_pkg_count:
            table.add_columns("Name", "Description")
        else:
            table.add_columns("Name", "Packages", "Description")

        for i, overlay in enumerate(self.filtered_overlays):
            if self.should_skip_pkg_count:
                # Skip package count display
                table.add_row(
                    overlay.name,
                    (overlay.description.strip() if overlay.description else "No description"),
                    key=str(i)
                )
            else:
                # Show package count
                package_count: str = str(overlay.package_count) if overlay.package_count is not None else "0"
                table.add_row(
                    overlay.name,
                    package_count,
                    (overlay.description.strip() if overlay.description else "No description"),
                    key=str(i)
                )

        # Restore selection if there was a pending one and it exists in filtered results
        if self._pending_selection is not None:
            selected_name: str = self._pending_selection

            for i, overlay in enumerate(self.filtered_overlays):
                if overlay.name == selected_name:
                    # Trigger the selection event to update the UI
                    self.selected_overlay = overlay
                    table.move_cursor(row=i)
                    break

            # Clear the pending selection
            self._pending_selection = None

        self.update_button_states()

    @work(exclusive=True, thread=True)
    async def load_overlays(self) -> None:
        """Load overlays from cache or fetch fresh data in a worker thread."""
        loading: LoadingIndicator = self.query_one("#overlays-loading", LoadingIndicator)
        table: DataTable = self.query_one("#overlays-table", DataTable)

        loading.display = True
        table.display = False

        try:
            # Get overlays from cache or fetch fresh with package counts
            overlays: list[Overlay] = get_or_cache(self.cache_manager)

            # Update both full list and filtered list
            self.overlays = overlays
            self.filtered_overlays = overlays.copy()

            # Update UI back on main thread
            self.app.call_from_thread(self._populate_table)

            self.app.call_from_thread(self.check_remote_cache_notification)
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Failed to load overlays: {e}", severity="error")

            self.update_button_states()
        finally:
            self.app.call_from_thread(self._hide_loading)

    def check_remote_cache_notification(self) -> None:
        """Check if we should notify about clearing cache for remote overlays."""
        eix_available: bool = is_found()
        eix_cache_available: bool = has_remote_cache() if eix_available else False

        # Check if remote cache is available and we have loaded overlays
        if eix_cache_available and self.overlays and not self._config.ignore_warnings:
            zero_package_overlays = []
            for overlay in self.overlays:
                if overlay.package_count == 0:
                    zero_package_overlays.append(overlay.name)

            # If we have overlays with 0 packages, suggest clearing cache
            if zero_package_overlays and len(zero_package_overlays) > 5:  # Only notify if significant number
                self.notify(
                    f"Found {len(zero_package_overlays)} overlays with 0 packages. "
                    "Remote cache is available - clear cache to count remote overlays?",
                    severity="warning",
                    timeout=10
                )

    def _hide_loading(self) -> None:
        """Hide loading indicator and show table."""
        loading: LoadingIndicator = self.query_one("#overlays-loading", LoadingIndicator)
        table: DataTable = self.query_one("#overlays-table", DataTable)

        loading.display = False
        table.display = True

    def _reload_overlays(self) -> None:
        """Trigger an overlay reload with cache refresh."""
        # Save the currently selected overlay name before reloading
        selected_name: str | None = self.selected_overlay.name if self.selected_overlay else None

        # Force refresh by clearing cache and reloading
        clear_cache(self.cache_manager)
        self.load_overlays()

        # After reload, we'll need to restore selection in _populate_table
        self._pending_selection = selected_name

    def _update_overlay_installation_status(self, overlay_name: str, installed: bool) -> None:
        """Update the installation status of an overlay locally and in cache."""
        # Update local instance
        for overlay in self.overlays:
            if overlay.name == overlay_name:
                overlay.installed = installed
                break

        # Update filtered overlays if the overlay is in the current filter
        for overlay in self.filtered_overlays:
            if overlay.name == overlay_name:
                overlay.installed = installed
                break

        # Update cache
        cache_data = [overlay.to_dict() for overlay in self.overlays]
        self.cache_manager.set("overlays_data", cache_data)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the overlays table."""
        if event.row_key is None:
            return

        # Find the selected overlay using the row index from filtered overlays
        row_index = int(event.row_key.value) #  type: ignore
        if 0 <= row_index < len(self.filtered_overlays):
            self.selected_overlay = self.filtered_overlays[row_index]
        else:
            self.selected_overlay = None

        if self.selected_overlay is None:
            return

        # Display overlay details
        content_widget: Static = self.query_one("#overlays-content", Static)

        # Format the overlay content
        details: str = f"[bold]{self.selected_overlay.name}[/bold] {'(Installed)' if self.selected_overlay.installed else ''}\n\n"

        if self.selected_overlay.description:
            details += f"{self.selected_overlay.description}\n\n"

        details += f"Status: {self.selected_overlay.status.value.title()}\n"

        # Only show package count if counting is enabled
        if not self.should_skip_pkg_count:
            package_count: int | None = self.selected_overlay.package_count or 0
            details += f"Packages: {package_count}\n"

        if self.selected_overlay.homepage:
            details += f"Homepage: {self.selected_overlay.homepage}\n"

        details += f"Owner: {self.selected_overlay.owner.name} ({self.selected_overlay.owner.email})\n\n"

        # Sources
        if self.selected_overlay.sources:
            details += "Sources:\n"
            for source in self.selected_overlay.sources:
                details += f"  • {source.source_type.value}: {source.url}\n"
            details += "\n"

        # Feeds
        if self.selected_overlay.feeds:
            details += "Feeds:\n"
            for feed in self.selected_overlay.feeds:
                details += f"  • {feed}\n"

        content_widget.update(details)

        # Update button states
        self.update_button_states()

    def update_button_states(self) -> None:
        """Update button visibility states."""
        enable_btn: Button = self.query_one("#enable-sync-btn", Button)
        remove_btn: Button = self.query_one("#remove-btn", Button)

        # Show appropriate button based on installation status
        if self.selected_overlay:
            if self.selected_overlay.installed:
                enable_btn.display = False
                remove_btn.display = True
            else:
                enable_btn.display = True
                remove_btn.display = False
        else:
            enable_btn.display = False
            remove_btn.display = False

        # Sync button states
        enable_btn.disabled = not enable_btn.display
        remove_btn.disabled = not remove_btn.display

    @work(exclusive=True, thread=True)
    async def _action_enable_sync(self) -> None:
        """Enable and sync the selected overlay."""
        if self.selected_overlay is None or self.selected_overlay.installed:
            return

        enable_btn: Button = self.query_one("#enable-sync-btn", Button)

        if enable_btn.disabled:
            return

        self.app.call_from_thread(self.notify, "Enabling and syncing... (don't close until finished!)", severity="warning",
                                  timeout=15)

        try:
            enable_btn.disabled = True

            enable_btn.label = "Adding..."

            overlay: Overlay = self.selected_overlay

            returncode, stdout, stderr = overlay.enable_and_sync()

            if returncode == 0:
                self.app.call_from_thread(self.notify, f"Successfully installed {overlay.name}")

                self._pending_selection = overlay.name

                # Update overlay status and refresh table
                self.app.call_from_thread(self._update_overlay_installation_status, overlay.name, True)
                self.app.call_from_thread(self._populate_table)
            else:
                self.app.call_from_thread(self.notify, f"Failed to enable and sync: {stderr}", severity="error")
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Error enabling and syncing: {e}", severity="error")
        finally:
            enable_btn.disabled = False

            enable_btn.label = "Enable & Sync"

            self.app.bell()

    @work(exclusive=True, thread=True)
    async def _action_remove(self) -> None:
        """Remove the selected overlay."""
        if self.selected_overlay is None or not self.selected_overlay.installed:
            return

        remove_btn: Button = self.query_one("#remove-btn", Button)

        if remove_btn.disabled:
            return

        try:
            remove_btn.disabled = True

            remove_btn.label = "Removing..."

            overlay: Overlay = self.selected_overlay

            returncode, stdout, stderr = overlay.remove()

            if returncode == 0:
                self.app.call_from_thread(self.notify, f"Successfully removed {overlay.name}")

                self._pending_selection = overlay.name

                # Update overlay status and refresh table
                self.app.call_from_thread(self._update_overlay_installation_status, overlay.name, False)
                self.app.call_from_thread(self._populate_table)
            else:
                self.app.call_from_thread(self.notify, f"Failed to remove: {stderr}", severity="error")
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Error removing: {e}", severity="error")
        finally:
            remove_btn.disabled = False

            remove_btn.label = "Remove"

            self.app.bell()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "enable-sync-btn":
            self._action_enable_sync()
        elif event.button.id == "remove-btn":
            self._action_remove()
