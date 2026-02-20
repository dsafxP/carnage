"""Package detail widget with tabbed views for the Browse tab."""

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import (Button, DataTable, Static, TabbedContent, TabPane,
                             Tree)
from textual.widgets._tree import TreeNode

from carnage.core import Configuration, get_config
from carnage.core.eix.search import Package, PackageVersion
from carnage.core.gentoolkit.package import GentoolkitPackage
from carnage.core.portage.emerge import (emerge_deselect, emerge_install,
                                         emerge_noreplace, emerge_uninstall)
from carnage.tui.widgets.table import NavigableDataTable


def _default_version(package: Package) -> PackageVersion | None:
    """
    Select the default version to highlight for a package.

    Priority:
      1. Installed version (if any)
      2. Latest non-9999 version
      3. First version available
    """
    installed = package.installed_version()
    if installed is not None:
        return installed

    non_live = [v for v in package.versions if v.id != "9999"]
    if non_live:
        return non_live[-1]  # versions are ordered oldest→newest by eix

    return package.versions[0] if package.versions else None


def _build_file_tree(node: TreeNode[str], prefix: str, contents: dict) -> None:
    """Recursively build a Textual Tree from a flat CONTENTS path dict."""
    seen: set[str] = set()
    for path in sorted(contents):
        if not path.startswith(prefix + "/"):
            continue
        remainder = path[len(prefix) + 1:]
        child_name = remainder.split("/")[0]
        if child_name in seen:
            continue
        seen.add(child_name)

        child_path: str = f"{prefix}/{child_name}"
        entry_type = contents.get(child_path, [None])[0]
        is_dir = entry_type == "dir" or any(
            p.startswith(child_path + "/") for p in contents
        )

        config: Configuration = get_config()

        if is_dir:
            branch = node.add(f"📂 {child_name}", expand=config.expand)
            _build_file_tree(branch, child_path, contents)
        elif entry_type == "sym":
            node.add_leaf(f"🔗 {child_name}")
        else:
            node.add_leaf(f"📄 {child_name}")


class PackageDetailWidget(Widget):
    """
    Tabbed detail view for a single Gentoo package.

    Owns: version selection, world file status, and all package actions.
    """

    BINDINGS = [
        Binding("e", "emerge", "Emerge", show=True),
        Binding("c", "depclean", "Depclean", show=True),
        Binding("w", "deselect", "Deselect", show=True),
        Binding("n", "noreplace", "Noreplace", show=True),
    ]

    def __init__(self, package: Package) -> None:
        super().__init__()
        self.package = package
        self.selected_version: PackageVersion | None = _default_version(package)
        self._in_world_file: bool | None = None  # None = not yet loaded

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
                with VerticalScroll(id="pkg-ebuild-scroll"):
                    yield Static("", id="pkg-ebuild-content")

            with TabPane("Dependencies", id="tab-deps"):
                yield Static(
                    "[dim]Dependency graph — coming soon.[/dim]",
                    id="pkg-dummy-content",
                )

            with TabPane("Installed Files", id="tab-files",
                         disabled=not self.package.is_installed()):
                yield Tree("/", id="pkg-files-tree")

    def on_mount(self) -> None:
        self._populate_versions_table()
        self._load_ebuild()
        self._load_installed_files()
        self._load_world_file_status()
        # Buttons will be refreshed once world file status arrives; show
        # what we can immediately in the meantime.
        self._update_buttons()


    def _format_details(self) -> str:
        """Format the top-level package details block."""
        pkg: Package = self.package
        version_label: str = f" {self.selected_version.id}" if self.selected_version else ""
        details: str = f"[bold]{pkg.category}/{pkg.name}[/bold]{version_label}\n\n"

        if pkg.description:
            details += f"{pkg.description}\n\n"

        if pkg.homepage:
            details += f"{pkg.homepage}\n\n"

        if pkg.licenses:
            details += f"[dim]License(s): {', '.join(pkg.licenses)}[/dim]\n"

        return details.rstrip()

    def _load_ebuild(self) -> None:
        """Populate the Ebuild tab for the currently selected version."""
        from rich.console import Group
        from rich.syntax import Syntax
        from rich.text import Text

        ebuild_widget: Static = self.query_one("#pkg-ebuild-content", Static)

        if self.selected_version is None:
            ebuild_widget.update(Text.from_markup("[red]No version selected.[/red]"))
            return

        gt_pkg: GentoolkitPackage = self.selected_version.to_gentoolkit(
            self.package.category, self.package.name
        )
        path_str: str | None = gt_pkg.ebuild_path()

        if not path_str:
            ebuild_widget.update(Text.from_markup(
                f"[red]{self.package.category}/{self.package.name} ebuild path not found.[/red]"
            ))
            return

        path = Path(path_str)
        header: Text = Text.from_markup(f"[dim]{path}[/dim]\n")

        if not path.exists():
            ebuild_widget.update(Group(header, Text.from_markup(f"[red]{path} does not exist.[/red]")))
            return

        content: str = path.read_text(encoding="utf-8", errors="replace").strip()

        if not content:
            ebuild_widget.update(Group(header, Text.from_markup(f"[red]{path} is empty.[/red]")))
            return

        config: Configuration = get_config()

        ebuild_widget.update(
            Group(
                header,
                Syntax(
                    content,
                    "bash",
                    theme=config.syntax_style,
                    line_numbers=True,
                    word_wrap=False
                )
            )
        )

    def _load_installed_files(self) -> None:
        """Populate the Installed Files tab. Loaded once on mount; version-agnostic."""
        tree: Tree[str] = self.query_one("#pkg-files-tree", Tree)

        installed = self.package.installed_version()
        if installed is None:
            return  # Tab is disabled; nothing to do

        from gentoolkit.cpv import CPV

        cpv_str: str = f"{self.package.category}/{self.package.name}-{installed.id}"
        gt_pkg = GentoolkitPackage(CPV(cpv_str))

        try:
            contents: dict = gt_pkg.parsed_contents()
        except:
            contents = {}

        if not contents:
            tree.root.add_leaf("[dim]No installed files found.[/dim]")
            tree.root.expand()
            return

        _build_file_tree(tree.root, "", contents)
        tree.root.expand()

    def _populate_versions_table(self) -> None:
        table = self.query_one("#pkg-versions-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Version", "Overlay")

        for i, version in enumerate(self.package.versions):
            label: str = self._version_label(version, self.package)
            overlay: str = version.repository or "gentoo"
            table.add_row(label, overlay, key=f"{version.id}-{i}")

    @staticmethod
    def _version_label(version: PackageVersion, pkg: Package) -> str:
        suffix = " (Virtual)" if version.virtual else ""
        if version.installed:
            return f"[green]✓[/green] {version.id}{suffix}"
        gt_pkg: GentoolkitPackage = version.to_gentoolkit(pkg.category, pkg.name)
        if not gt_pkg.available:
            return f"[red]✗[/red] {version.id}{suffix}"
        return f"  {version.id}{suffix}"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is None or event.data_table.id != "pkg-versions-table":
            return

        version_id = event.row_key.value.rsplit("-", 1)[0]  # type: ignore
        version = next(
            (v for v in self.package.versions if v.id == version_id), None
        )
        if version is None:
            return

        self.selected_version = version
        self._load_ebuild()
        self._update_buttons()

        gt_pkg: GentoolkitPackage = version.to_gentoolkit(
            self.package.category, self.package.name
        )
        if gt_pkg.available:
            self.notify(f"{self.package.full_name}-{version_id} selected")
        else:
            self.notify(
                f"{self.package.full_name}-{version_id} is unavailable",
                severity="warning",
            )


    @work(exclusive=True, thread=True)
    def _load_world_file_status(self) -> None:
        """Check world file membership in a thread then refresh buttons."""
        self._in_world_file = self.package.is_in_world_file()
        self.app.call_from_thread(self._update_buttons)


    def _update_buttons(self) -> None:
        """Synchronise button visibility with selected_version and world file state."""
        emerge_btn: Button = self.query_one("#emerge-btn", Button)
        depclean_btn: Button = self.query_one("#depclean-btn", Button)
        deselect_btn: Button = self.query_one("#deselect-btn", Button)
        noreplace_btn: Button = self.query_one("#noreplace-btn", Button)

        is_installed: bool = self.package.is_installed()

        if is_installed:
            emerge_btn.display = False
            depclean_btn.display = True
            # World file buttons depend on async status — hide until known
            if self._in_world_file:
                deselect_btn.display = True
                noreplace_btn.display = False
            elif self._in_world_file is False:
                deselect_btn.display = False
                noreplace_btn.display = True
            else:
                deselect_btn.display = False
                noreplace_btn.display = False
        else:
            # Emerge availability is version-specific
            if self.selected_version is not None:
                gt_pkg: GentoolkitPackage = self.selected_version.to_gentoolkit(
                    self.package.category, self.package.name
                )
                emerge_btn.display = gt_pkg.available
            else:
                emerge_btn.display = False
            depclean_btn.display = False
            deselect_btn.display = False
            noreplace_btn.display = False

        emerge_btn.disabled = not emerge_btn.display
        depclean_btn.disabled = not depclean_btn.display
        deselect_btn.disabled = not deselect_btn.display
        noreplace_btn.disabled = not noreplace_btn.display

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.disabled:
            return

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
        emerge_btn: Button = self.query_one("#emerge-btn", Button)
        
        if self.selected_version is None or self.package.is_installed() or emerge_btn.disabled:
            return

        atom: str = f"={self.package.full_name}-{self.selected_version.id}"

        try:
            emerge_btn.disabled = True
            self.app.call_from_thread(
                self.notify,
                f"Installing {atom}... (don't close until finished!)",
                severity="warning",
                timeout=15,
            )
            returncode, _, stderr = emerge_install(atom)
            if returncode == 0:
                self.app.call_from_thread(self.notify, f"Successfully installed {atom}")
            else:
                self.app.call_from_thread(
                    self.notify, f"Failed to install: {stderr}", severity="error"
                )
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Error installing: {e}", severity="error"
            )
        finally:
            emerge_btn.disabled = False

    @work(exclusive=True, thread=True)
    def action_depclean(self) -> None:
        depclean_btn: Button = self.query_one("#depclean-btn", Button)

        if not self.package.is_installed() or depclean_btn.disabled:
            return

        atom: str = self.package.full_name

        try:
            depclean_btn.disabled = True
            self.app.call_from_thread(
                self.notify,
                f"Removing {atom}... (don't close until finished!)",
                severity="warning",
                timeout=15,
            )
            returncode, _, stderr = emerge_uninstall(atom)
            if returncode == 0:
                self.app.call_from_thread(self.notify, f"Successfully removed {atom}")
            else:
                self.app.call_from_thread(
                    self.notify, f"Failed to remove: {stderr}", severity="error"
                )
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Error removing: {e}", severity="error"
            )
        finally:
            depclean_btn.disabled = False

    @work(exclusive=True, thread=True)
    def action_deselect(self) -> None:
        deselect_btn: Button = self.query_one("#deselect-btn", Button)
        if deselect_btn.disabled:
            return

        atom: str = self.package.full_name

        try:
            deselect_btn.disabled = True
            self.app.call_from_thread(
                self.notify,
                f"Removing {atom} from world file...",
                severity="warning",
                timeout=10,
            )
            returncode, _, stderr = emerge_deselect(atom)
            if returncode == 0:
                self.app.call_from_thread(
                    self.notify, f"Successfully removed {atom} from world file"
                )
                self._load_world_file_status()
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
        finally:
            deselect_btn.disabled = False

    @work(exclusive=True, thread=True)
    def action_noreplace(self) -> None:
        noreplace_btn: Button = self.query_one("#noreplace-btn", Button)
        if noreplace_btn.disabled:
            return

        atom: str = self.package.full_name

        try:
            noreplace_btn.disabled = True
            self.app.call_from_thread(
                self.notify,
                f"Adding {atom} to world file...",
                severity="warning",
                timeout=10,
            )
            returncode, _, stderr = emerge_noreplace(atom)
            if returncode == 0:
                self.app.call_from_thread(
                    self.notify, f"Successfully added {atom} to world file"
                )
                self._load_world_file_status()
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
        finally:
            noreplace_btn.disabled = False