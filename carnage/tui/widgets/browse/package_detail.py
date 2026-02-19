"""Package detail widget with tabbed views for the Browse tab."""

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, DataTable, Static, TabbedContent, TabPane

from carnage.core.eix import Package, PackageVersion
from carnage.core.eix.search import Package, PackageVersion
from carnage.tui.widgets.table import NavigableDataTable


class PackageDetailWidget(Widget):
    """
    Tabbed detail view for a single Gentoo package.

    Displays Details, Versions, USE Flags, Ebuild, Dependencies, and
    Installed Files. Actions (emerge, depclean, etc.) live on the Details
    tab.
    """

    def __init__(self, package: Package, in_world_file: bool | None = None) -> None:
        super().__init__()
        self.package = package
        self.in_world_file = in_world_file

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("Details", id="tab-details"):
                with Vertical():
                    with VerticalScroll(id="pkg-detail-scroll"):
                        yield Static(self._format_details(), id="pkg-detail-content")
                    with Vertical(id="pkg-detail-actions"):
                        yield Button("Emerge", id="emerge-btn", variant="primary")
                        yield Button("Depclean", id="depclean-btn", variant="error")
                        yield Button("Deselect", id="deselect-btn", variant="warning")
                        yield Button("Noreplace", id="noreplace-btn", variant="success")

            with TabPane("Versions", id="tab-versions"):
                yield NavigableDataTable(id="pkg-versions-table", cursor_type="row")

            with TabPane("USE Flags", id="tab-use"):
                yield Static(
                    "[dim]USE flag editor — coming soon.[/dim]",
                    id="pkg-dummy-content",
                )

            with TabPane("Ebuild", id="tab-ebuild"):
                yield Static(
                    "[dim]Ebuild viewer — coming soon.[/dim]",
                    id="pkg-dummy-content",
                )

            with TabPane("Dependencies", id="tab-deps"):
                yield Static(
                    "[dim]Dependency graph — coming soon.[/dim]",
                    id="pkg-dummy-content",
                )

            with TabPane("Installed Files", id="tab-files"):
                yield Static(
                    "[dim]Installed files — coming soon.[/dim]",
                    id="pkg-dummy-content",
                )

    def on_mount(self) -> None:
        self._populate_versions_table()
        self.update_buttons()

    def _format_details(self) -> str:
        """Format the top-level package details block."""
        pkg: Package = self.package

        # Installed version label for the header, if any
        installed = pkg.installed_version()
        version_label: str = f" {installed.id}" if installed else ""
        details: str = f"[bold]{pkg.category}/{pkg.name}[/bold]{version_label}\n\n"

        if pkg.description:
            details += f"{pkg.description}\n\n"

        if pkg.homepage:
            details += f"{pkg.homepage}\n\n"

        if pkg.licenses:
            details += f"[dim]License(s): {', '.join(pkg.licenses)}[/dim]\n"

        return details.rstrip()

    def update_buttons(self, in_world_file: bool | None = None) -> None:
        """Show/hide action buttons based on package and world file state."""
        if in_world_file is not None:
            self.in_world_file = in_world_file

        emerge_btn: Button = self.query_one("#emerge-btn", Button)
        depclean_btn: Button = self.query_one("#depclean-btn", Button)
        deselect_btn: Button = self.query_one("#deselect-btn", Button)
        noreplace_btn: Button = self.query_one("#noreplace-btn", Button)

        is_installed: bool = self.package.is_installed()

        if is_installed:
            emerge_btn.display = False
            depclean_btn.display = True
            if self.in_world_file:
                deselect_btn.display = True
                noreplace_btn.display = False
            elif self.in_world_file is False:
                deselect_btn.display = False
                noreplace_btn.display = True
            else:
                # Still loading world file status
                deselect_btn.display = False
                noreplace_btn.display = False
        else:
            emerge_btn.display = self.package.can_emerge()
            depclean_btn.display = False
            deselect_btn.display = False
            noreplace_btn.display = False

        emerge_btn.disabled = not emerge_btn.display
        depclean_btn.disabled = not depclean_btn.display
        deselect_btn.disabled = not deselect_btn.display
        noreplace_btn.disabled = not noreplace_btn.display

    def _populate_versions_table(self) -> None:
        """Fill the versions DataTable."""
        table = self.query_one("#pkg-versions-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Version", "Overlay")

        for i, version in enumerate(self.package.versions):
            label: str = self._version_label(version)
            overlay: str = version.repository or "gentoo"
            table.add_row(label, overlay, key=f"{version.id}-{i}")

    @staticmethod
    def _version_label(version: PackageVersion) -> str:
        """Format a version row label with install/unavailable indicator."""

        suffix = " (Virtual)" if version.virtual else ""

        if version.installed:
            return f"[green]✓[/green] {version.id}{suffix}"
        if version.masks:
            return f"[red]✗[/red] {version.id}{suffix}"
        return f"  {version.id}{suffix}"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is None or event.data_table.id != "pkg-versions-table":
            return

        version_id = event.row_key.value.rsplit("-", 1)[0] # type: ignore

        version: PackageVersion | None = next((v for v in self.package.versions if v.id == version_id), None)
        
        if version is None:
            return

        if version.masks:
            self.notify(f"{self.package.full_name}-{version_id} is unavailable", severity="warning")
        else:
            self.notify(f"{self.package.full_name}-{version_id} selected")