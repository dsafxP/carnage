"""GLSAs tab widget for displaying and managing Gentoo Linux Security Advisories."""


from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, DataTable, LoadingIndicator, Static

from carnage.core.glsas import GLSA, fetch_glsas, fix_glsas


class GLSATab(Widget):
    """Widget for displaying and managing Gentoo Linux Security Advisories."""

    BINDINGS = [
        Binding("f", "fix_glsas", "Apply Fixes"),
    ]

    def __init__(self):
        super().__init__()
        self.glsa_items: list[GLSA] = []
        self.selected_glsa: GLSA | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical():
            yield LoadingIndicator(id="glsa-loading")
            yield DataTable(id="glsa-table", cursor_type="row")

            with Vertical(id="glsa-detail"):
                with VerticalScroll(id="glsa-content-scroll"):
                    yield Static("Select a GLSA to view details", id="glsa-content")

                with Vertical(id="glsa-actions"):
                    yield Button("Apply fixes", id="fix-glsa-btn", variant="primary")

    def on_mount(self) -> None:
        """Load GLSAs when widget is mounted."""
        self.load_glsas()

    @work(exclusive=True, thread=True)
    async def load_glsas(self) -> None:
        """Load GLSAs from the system in a worker thread."""
        loading: LoadingIndicator = self.query_one("#glsa-loading", LoadingIndicator)
        table: DataTable = self.query_one("#glsa-table", DataTable)

        loading.display = True
        table.display = False

        try:
            # This runs in a thread, so it won't block the UI
            glsa_items: list[GLSA] = fetch_glsas()

            # Update UI back on main thread
            self.app.call_from_thread(self._populate_table, glsa_items)
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Failed to load GLSAs: {e}", severity="error")
        finally:
            self.app.call_from_thread(self._hide_loading)

    def _populate_table(self, glsa_items: list[GLSA]) -> None:
        """Populate the table with GLSA items (runs on main thread)."""
        self.glsa_items = glsa_items
        table: DataTable = self.query_one("#glsa-table", DataTable)

        table.clear(columns=True)
        table.add_columns("ID", "Product", "Title")

        for glsa in self.glsa_items:
            table.add_row(glsa.id, glsa.product or "N/A", glsa.title or glsa.synopsis, key=glsa.id)

        self.update_button_states()

    def _hide_loading(self) -> None:
        """Hide loading indicator and show table."""
        loading: LoadingIndicator = self.query_one("#glsa-loading", LoadingIndicator)
        table: DataTable = self.query_one("#glsa-table", DataTable)

        loading.display = False
        table.display = True

    def _reload_glsas(self) -> None:
        """Trigger a GLSAs reload (non-worker wrapper)."""
        self.load_glsas()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the GLSA table."""
        if event.row_key is None:
            return

        # Find the selected GLSA item
        glsa_id: str | None = event.row_key.value
        self.selected_glsa = next(
            (g for g in self.glsa_items if g.id == glsa_id),
            None
        )

        if self.selected_glsa is None:
            return

        # Display GLSA details
        content_widget: Static = self.query_one("#glsa-content", Static)

        # Format the GLSA content
        details: str = f"[bold]{self.selected_glsa.title or self.selected_glsa.synopsis}[/bold]\n\n"

        if self.selected_glsa.product:
            details += f"[dim]Product: {self.selected_glsa.product}\n[/dim]"

        details += f"[dim]ID: {self.selected_glsa.id}[/dim]\n"

        if self.selected_glsa.announced:
            details += f"[dim]Announced: {self.selected_glsa.announced}[/dim]\n"

        #if self.selected_glsa.revised:
        #   details += f"Revised: {self.selected_glsa.revised} (revision {self.selected_glsa.revision_count})\n"

        if self.selected_glsa.impact_type:
            details += f"[dim]Severity: {self.selected_glsa.impact_type}[/dim]\n"
            
        if self.selected_glsa.access:
            details += f"[dim]Exploitable: {self.selected_glsa.access}[/dim]\n"

        details += "\n" + "-" * 60 + "\n\n"

        # Render affected packages
        if self.selected_glsa.affected_packages:
            details += f"\n[underline]Affected Packages:[/underline]\n\n"

            for package in self.selected_glsa.affected_packages:
                details += f"[dim]Package: [bold]{package.name}[/bold] on [bold]{package.arch}[/bold][/dim]\n"

                # Render vulnerable versions (affected)
                if package.vulnerable_conditions:
                    affected_versions: list[str] = []
                    for condition in package.vulnerable_conditions:
                        range_symbol = _get_range_symbol(condition["range"])
                        slot_info: str = f":{condition['slot']}" if condition["slot"] else ""
                        affected_versions.append(f"{range_symbol} [bold]{condition['value']}{slot_info}[/bold]")

                    details += f"[red]Affected versions: {', '.join(affected_versions)}[/red]\n"

                # Render unaffected versions
                if package.unaffected_conditions:
                    unaffected_versions: list[str] = []
                    for condition in package.unaffected_conditions:
                        range_symbol: str = _get_range_symbol(condition["range"])
                        slot_info = f":{condition['slot']}" if condition["slot"] else ""
                        unaffected_versions.append(f"{range_symbol} [bold]{condition['value']}{slot_info}[/bold]")

                    details += f"[green]Unaffected versions: {', '.join(unaffected_versions)}[/green]\n"

                details += "\n"  # Add spacing between packages

        if self.selected_glsa.background:
            details += f"[underline]Background:[/underline]\n{self.selected_glsa.background}\n\n"

        if self.selected_glsa.description:
            details += f"[underline]Description:[/underline]\n{self.selected_glsa.description}\n\n"

        if self.selected_glsa.impact:
            details += f"[underline]Impact:[/underline]\n{self.selected_glsa.impact}\n\n"

        if self.selected_glsa.workaround:
            details += f"[underline]Workaround:[/underline]\n{self.selected_glsa.workaround}\n\n"

        # Render resolutions
        if self.selected_glsa.resolutions:
            details += f"[underline]Resolution:[/underline]\n"

            for i, resolution in enumerate(self.selected_glsa.resolutions, 1):
                if resolution.text:
                    details += f"{resolution.text}\n"

                if resolution.code:
                    details += f"[dim]{resolution.code}[/dim]\n"

                # Add spacing between multiple resolutions, but not after the last one
                if i < len(self.selected_glsa.resolutions):
                    details += "\n"

        if self.selected_glsa.references:
            details += f"[underline]References:[/underline]\n"
            for ref in self.selected_glsa.references:
                details += f"  • {ref}\n"
            details += "\n"

        if self.selected_glsa.bugs:
            details += f"[underline]Bugzilla entries:[/underline]\n"
            for bug in self.selected_glsa.bugs:
                details += f"  • {bug}\n"

        content_widget.update(details)

        # Update button states
        self.update_button_states()

    def update_button_states(self) -> None:
        """Update button enabled/disabled states."""
        fix_btn: Button = self.query_one("#fix-glsa-btn", Button)

        # Enable "Apply fixes" only if there are GLSAs affecting the system
        has_glsas: bool = len(self.glsa_items) > 0
        fix_btn.disabled = not has_glsas

    @work(exclusive=True, thread=True)
    async def action_fix_glsas(self) -> None:
        """Apply fixes for all GLSAs affecting the system."""
        if not self.glsa_items:
            self.notify("No GLSAs to fix", severity="warning")
            return
        
        self.app.call_from_thread(self.notify, "Applying fixes... (don't close until finished!)", severity="warning", timeout=15)

        fix_btn: Button = self.query_one("#fix-glsa-btn", Button)

        try:
            fix_btn.disabled = True
            
            returncode, stdout, stderr = fix_glsas()

            if returncode == 0:
                self.app.call_from_thread(self.notify, "Successfully applied GLSA fixes")
                # Refresh the GLSA list after fixes are applied
                self.app.call_from_thread(self._reload_glsas)
            else:
                self.app.call_from_thread(self.notify, f"Failed to apply fixes: {stderr}", severity="error")

                fix_btn.disabled = False
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Error applying fixes: {e}", severity="error")

            fix_btn.disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "fix-glsa-btn":
            self.action_fix_glsas()


_symbols: dict[str, str] = {
    "lt": "<",
    "le": "<=",
    "eq": "=",
    "ge": "≥",
    "gt": ">"
}

def _get_range_symbol(range_str: str) -> str:
    """Convert range operator to symbol."""
    return _symbols.get(range_str, range_str)
