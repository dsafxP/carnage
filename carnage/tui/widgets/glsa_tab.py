"""GLSAs tab widget for displaying and managing Gentoo Linux Security Advisories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Button, DataTable, LoadingIndicator, Rule, Static, TabbedContent

from carnage.core.config import Configuration, get_config
from carnage.core.formatting import format_glsa_details, format_glsa_header
from carnage.tui.widgets.table import NavigableDataTable
from carnage.tui.widgets.table_tab import TableTab

if TYPE_CHECKING:
    from carnage.core.portage.glsas import GLSA


class GLSATab(TableTab):
    """Widget for displaying and managing Gentoo Linux Security Advisories."""

    TABLE_ID = "glsa-table"
    LOADING_ID = "glsa-loading"

    def __init__(self) -> None:
        super().__init__()
        self.glsa_items: list[GLSA] = []
        self.selected_glsa: GLSA | None = None
        self._loaded = False

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical():
            yield LoadingIndicator(id="glsa-loading")
            yield NavigableDataTable(id="glsa-table", cursor_type="row")

            with Vertical(id="glsa-detail"):
                with VerticalScroll(id="glsa-content-scroll"):
                    yield Static("Select a GLSA to view details", id="glsa-header")
                    yield Rule(line_style="heavy")
                    yield Static(id="glsa-content")

                with Vertical(id="glsa-actions"):
                    yield Button("Apply fixes", id="fix-glsa-btn", variant="primary")

    def on_mount(self) -> None:
        """Set up the table; data loads on first activation."""
        # Park the spinner until a load actually starts: nothing else hides
        # it if activation never reaches ensure_loaded().
        self._hide_loading()

        table: DataTable = self.query_one("#glsa-table", DataTable)

        table.add_columns("ID", "Product", "Title")

        # Nothing is selected yet: park the button instead of showing the
        # compose-time default over an empty table.
        self.update_button_states()

    def ensure_loaded(self) -> None:
        """Start the first load, once, instead of at mount."""
        if self._loaded:
            return

        try:
            self.load_glsas()
        except Exception:
            # Worker never started: stay unloaded so the next activation
            # retries instead of parking the spinner forever.
            return

        self._loaded = True

    @work(exclusive=True, thread=True)
    def load_glsas(self) -> None:
        """Load GLSAs from the system."""
        from carnage.core.portage.glsas import fetch_glsas

        # Widgets are not thread-safe: every DOM touch goes through the loop.
        self.app.call_from_thread(self._show_loading)

        try:
            glsa_items: list[GLSA] = fetch_glsas()

            if glsa_items:
                self.app.call_from_thread(self._warn_if_new_glsas)

            self.app.call_from_thread(self._populate_table, glsa_items)
        except Exception as e:
            # Allow a later activation to retry instead of leaving the tab
            # empty until restart.
            self._loaded = False
            self.app.call_from_thread(self.notify, f"Failed to load GLSAs: {e}", severity="error")
        finally:
            self.app.call_from_thread(self._hide_loading)

    def _warn_if_new_glsas(self) -> None:
        """Ring the bell when advisories exist and their tab is not open."""
        tabbed_content: TabbedContent = self.screen.query_one(TabbedContent)
        config: Configuration = get_config()

        if tabbed_content.active != "glsas" and not config.ignore_warnings:
            self.notify(
                "Found security advisories that affect the system. Please review ASAP!",
                severity="warning",
            )
            self.app.bell()

    def _populate_table(self, glsa_items: list[GLSA]) -> None:
        """Populate the table with GLSA items (runs on main thread)."""
        self.glsa_items = glsa_items
        table: DataTable = self.query_one("#glsa-table", DataTable)

        table.clear()

        for glsa in self.glsa_items:
            table.add_row(glsa.id, glsa.product or "N/A", glsa.title or glsa.synopsis, key=glsa.id)

        self.update_button_states()

    def _reload_glsas(self) -> None:
        """Trigger a GLSAs reload (non-worker wrapper)."""
        self.load_glsas()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the GLSA table."""
        if event.row_key is None:
            return

        # Find the selected GLSA item
        glsa_id: str | None = event.row_key.value
        self.selected_glsa = next((g for g in self.glsa_items if g.id == glsa_id), None)

        if self.selected_glsa is None:
            return

        # Display GLSA details
        self.query_one("#glsa-header", Static).update(format_glsa_header(self.selected_glsa))
        self.query_one("#glsa-content", Static).update(format_glsa_details(self.selected_glsa))

        # Update button states
        self.update_button_states()

    def update_button_states(self) -> None:
        """Update button visibility states."""
        fix_btn: Button = self.query_one("#fix-glsa-btn", Button)

        is_blocked = self.app.blocked  # type: ignore

        # Enable "Apply fixes" only if there are GLSAs affecting the system and no operation running
        has_glsas: bool = len(self.glsa_items) > 0
        fix_btn.disabled = not has_glsas or is_blocked
        fix_btn.display = has_glsas

    def _action_fix_glsas(self) -> None:
        """Apply fixes for all GLSAs affecting the system."""
        fix_btn: Button = self.query_one("#fix-glsa-btn", Button)

        if not self.glsa_items or fix_btn.disabled:
            return

        self.notify("Applying fixes... (don't close until finished!)", severity="warning", timeout=15)

        fix_btn.disabled = True

        fix_btn.label = "Applying..."

        def on_complete(success: bool) -> None:
            if success:
                self.notify("Successfully applied GLSA fixes")
                # Refresh the GLSA list after fixes are applied
                self._reload_glsas()
            else:
                self.notify("Failed to apply GLSA fixes", severity="error")

            fix_btn.label = "Apply fixes"

            self.update_button_states()
            self.app.bell()

        # The tab already holds exactly the vulnerable ids, so hand them over
        # directly instead of re-scanning every advisory first.
        from carnage.core.portage.glsas import fix_glsas_by_ids

        fix_glsas_by_ids(self.app, [glsa.id for glsa in self.glsa_items], on_complete=on_complete)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "fix-glsa-btn":
            self._action_fix_glsas()
