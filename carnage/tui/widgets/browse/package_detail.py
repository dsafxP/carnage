"""Package detail widget with tabbed views for the Browse tab."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual._context import NoActiveAppError
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.coordinate import Coordinate
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Button, DataTable, SelectionList, Static, TabPane, Tree
from textual.widgets._selection_list import Selection
from textual.widgets._tree import TreeNode

from carnage.core import Configuration, get_config
from carnage.core.eix.search import Package, PackageVersion
from carnage.core.formatting import format_package_details
from carnage.core.gentoolkit import portage_lock
from carnage.core.gentoolkit.euse import euse_disable, euse_enable
from carnage.core.portage.emerge import (
    emerge_deselect,
    emerge_install,
    emerge_noreplace,
    emerge_uninstall,
)
from carnage.tui.widgets.cachetabbedcontent import CachedTabbedContent
from carnage.tui.widgets.table import NavigableDataTable

if TYPE_CHECKING:
    from rich.console import RenderableType

    from carnage.core.gentoolkit.package import GentoolkitPackage


def default_version(package: Package) -> PackageVersion | None:
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

    non_live: list[PackageVersion] = [v for v in package.versions if v.id != "9999"]

    non_live_local: list[PackageVersion] = [v for v in non_live if not v.virtual]

    if non_live_local:
        return non_live_local[-1]

    if non_live:
        return non_live[-1]

    return package.versions[0] if package.versions else None


def _dep_label(pkg) -> str:
    """Label one dependency: pkg is either a gentoolkit Package or a bare atom."""
    if isinstance(pkg, str):
        category, _, name = pkg.partition("/")
        return f"{category}/[bold]{name}[/bold]"

    return f"{pkg.category}/[bold]{pkg.name}[/bold]-{pkg.version}"


def _build_dep_tree(node: TreeNode[str], deps: list, index: int = 0, depth: int = 1) -> int:
    """
    Build a Textual Tree from graph_depends() flat DFS results.

    Returns the index of the first entry this call did not consume. graph_depends
    emits parents before their children, contiguously, so walking with a cursor
    keeps each subtree attached to its own node: testing depths against the whole
    list gave every sibling the children of the first one.

    Args:
        node: Tree node to populate.
        deps: Flat [(depth, pkg), ...] results from graph_depends().
        index: Where this subtree starts in ``deps``.
        depth: Depth of the entries this level consumes.

    Returns:
        Index of the first entry belonging to an enclosing level.
    """
    config: Configuration = get_config()
    position = index

    while position < len(deps):
        dep_depth, pkg = deps[position]

        if dep_depth < depth:
            # Back at an enclosing level: these entries are siblings of ours.
            break

        position += 1
        label = _dep_label(pkg)

        # Children, if any, follow the parent immediately at depth + 1.
        if position < len(deps) and deps[position][0] == depth + 1:
            child: TreeNode[str] = node.add(label, expand=config.expand)
            position = _build_dep_tree(child, deps, position, depth + 1)
        else:
            node.add_leaf(label)

    return position


def _build_file_tree(node: TreeNode[str], prefix: str, contents: dict) -> None:
    """Recursively build a Textual Tree from a flat CONTENTS path dict."""
    from rich.markup import escape
    from rich.text import Text

    config: Configuration = get_config()

    # Group once: parent path -> child names, plus every directory that owns
    # at least one entry. The old code re-sorted the whole dict and re-scanned
    # every path at every directory node, which is O(dirs x files). Intermediate
    # directories are usually not entries themselves, so synthesize the links.
    children: dict[str, list[str]] = {}
    dir_paths: set[str] = set()

    for path in contents:
        stripped = path.strip("/")

        if not stripped:
            continue

        parts = stripped.split("/")

        for i, name in enumerate(parts):
            parent = "" if i == 0 else "/" + "/".join(parts[:i])
            children.setdefault(parent, []).append(name)

            if i < len(parts) - 1:
                dir_paths.add(f"{parent}/{name}" if parent else f"/{name}")

    def _add_children(node: TreeNode[str], prefix: str) -> None:
        for child_name in sorted(set(children.get(prefix, []))):
            child_path: str = f"{prefix}/{child_name}"
            entry_type = contents.get(child_path, [None])[0]
            is_dir = entry_type == "dir" or child_path in dir_paths

            if is_dir:
                label = Text("📂 ", style="dim")
                label.append(escape(child_name), style=f"bold magenta link file://{child_path}")
                branch: TreeNode[str] = node.add(label, expand=config.expand)
                _add_children(branch, child_path)
            elif entry_type == "sym":
                label = Text("🔗 ", style="")
                label.append(escape(child_name), style=f"cyan link file://{child_path}")
                node.add_leaf(label)
            else:
                label = Text("📄 ", style="")
                label.append(escape(child_name), style=f"green link file://{child_path}")
                label.highlight_regex(r"\.[^/]+$", "bold red")
                node.add_leaf(label)

    _add_children(node, prefix)


class PackageDetailWidget(Widget):
    """
    Tabbed detail view for a single Gentoo package.

    Owns: version selection, world file status, and all package actions.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("e", "emerge", "Emerge", show=True),
        Binding("c", "depclean", "Depclean", show=True),
        Binding("w", "deselect", "Deselect", show=True),
        Binding("n", "noreplace", "Noreplace", show=True),
    ]

    def __init__(self, package: Package) -> None:
        super().__init__()
        self.package = package
        self.selected_version: PackageVersion | None = default_version(package)
        self._in_world_file: bool | None = None  # None = not yet loaded
        self._use_flag_originals: dict[str, bool] = {}  # flag -> enabled at load time
        self._version_rows: list[tuple[str, str, str]] = []  # (key, label, overlay) without selection marks

    def _post_to_loop(self, callback: Callable[..., object], *args: object, **kwargs: object) -> bool:
        """
        Hand a callback to the event loop, tolerating a detached widget.

        Workers outlive the widget whenever the user selects another package
        (or clears the search) mid-load: the DOM is gone and self.app no
        longer resolves. Dropping the update is correct; raising out of the
        worker kills the app through exit_on_error, so never do that.
        """
        try:
            self.app.call_from_thread(callback, *args, **kwargs)
        except (NoActiveAppError, RuntimeError):
            return False
        return True

    def compose(self) -> ComposeResult:
        with CachedTabbedContent(cache_key="package_tabs"):
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
                yield Static(id="pkg-use-version")
                with VerticalScroll(id="pkg-use-scroll"):
                    yield SelectionList(id="pkg-use-list")
                with Vertical(id="pkg-use-actions"):
                    yield Button(
                        "Apply changes",
                        id="use-apply-btn",
                        variant="warning",
                        disabled=True,
                    )

            with TabPane("Ebuild", id="tab-ebuild"):
                with VerticalScroll(id="pkg-ebuild-scroll"):
                    yield Static(id="pkg-ebuild-content")

            with TabPane("Dependencies", id="tab-deps"):
                yield Tree(f"{self.package.full_name}", id="pkg-deps-tree")

            with TabPane("Installed Files", id="tab-files", disabled=not self.package.is_installed()):
                yield Tree("/", id="pkg-files-tree")

    def on_mount(self) -> None:
        table = self.query_one("#pkg-versions-table", DataTable)
        table.add_columns("Version", "Overlay")

        # The loads below all block on portage or the disk, so each runs in
        # its own worker and fills its pane when done. Workers never cancel
        # each other (separate groups); a worker whose version is no longer
        # selected drops its result instead of painting stale data.
        self._load_versions_table()

        self._load_use_flags()
        self._load_deps()
        self._load_ebuild()
        self._load_installed_files()
        self._load_world_file_status()
        # Buttons will be refreshed once world file status arrives; show
        # what we can immediately in the meantime.
        self._update_buttons()

    def _format_details(self) -> str:
        """Format the top-level package details block."""
        return format_package_details(self.package, self.selected_version)

    def _load_ebuild(self) -> None:
        """Populate the Ebuild tab for the currently selected version."""
        if self.selected_version is None:
            from rich.text import Text

            self.query_one("#pkg-ebuild-content", Static).update(Text.from_markup("[red]No version selected.[/]"))
            return

        self._fetch_ebuild(self.selected_version.id)

    @work(thread=True, group="pkg-ebuild")
    def _fetch_ebuild(self, version_id: str) -> None:
        """Read and highlight the ebuild off the event loop."""
        from rich.console import Group
        from rich.syntax import Syntax
        from rich.text import Text

        try:
            version = next((v for v in self.package.versions if v.id == version_id), None)

            if version is None:
                return

            # Portage is not thread-safe: serialize against the other workers.
            with portage_lock:
                gt_pkg: GentoolkitPackage = version.to_gentoolkit(self.package.category, self.package.name)
                path_str: str | None = gt_pkg.ebuild_path()

            if not path_str:
                renderable = Text.from_markup(
                    f"[red]{self.package.category}/{self.package.name} ebuild path not found.[/]"
                )
            else:
                path = Path(path_str)
                header: Text = Text.from_markup(f"[dim][link=file://{path}]{path}[/][/]\n")

                if not path.exists():
                    renderable = Group(header, Text.from_markup(f"[red]{path} does not exist.[/]"))
                else:
                    content: str = path.read_text(encoding="utf-8", errors="replace").strip()

                    if not content:
                        renderable = Group(header, Text.from_markup(f"[red]{path} is empty.[/]"))
                    else:
                        config: Configuration = get_config()
                        renderable = Group(
                            header,
                            Syntax(content, "bash", theme=config.syntax_style, line_numbers=True, word_wrap=False),
                        )

            self._post_to_loop(self._show_ebuild, version_id, renderable)
        except Exception as e:
            self._post_to_loop(self.notify, f"Failed to load ebuild: {e}", severity="error")

    def _show_ebuild(self, version_id: str, renderable: "RenderableType") -> None:
        """Display a fetched ebuild unless the selection moved on (event loop only)."""
        if self.selected_version is None or self.selected_version.id != version_id:
            return

        try:
            self.query_one("#pkg-ebuild-content", Static).update(renderable)
        except NoMatches:
            # The widget was removed while the worker was reading.
            pass

    def _load_use_flags(self) -> None:
        """Populate the USE Flags tab for the currently selected version."""
        version_label: Static = self.query_one("#pkg-use-version", Static)
        use_list: SelectionList = self.query_one("#pkg-use-list", SelectionList)
        apply_btn: Button = self.query_one("#use-apply-btn", Button)

        use_list.clear_options()
        use_list.disabled = False

        apply_btn.disabled = True
        self._use_flag_originals = {}

        if self.selected_version is None:
            version_label.update("[dim]No version selected.[/dim]")

            use_list.disabled = True
            return

        version_label.update(f"[dim]{self.package.full_name}-{self.selected_version.id}[/dim]")

        flags: set[str] = set(self.selected_version.iuse)
        if not flags:
            use_list.add_option(("[red]No USE flags found.[/red]", "__none__"))
            apply_btn.display = False
            use_list.disabled = True
            return

        # euse fails on a virtual version
        if self.selected_version.virtual:
            apply_btn.display = False
            use_list.disabled = True
            self._show_use_flags(self.selected_version.id, sorted(flags), set())
            return

        self._fetch_use_flags(self.selected_version.id, sorted(flags))

    @work(thread=True, group="pkg-use-flags")
    def _fetch_use_flags(self, version_id: str, flags: list[str]) -> None:
        """Ask portage which flags are enabled, off the event loop."""
        from carnage.core.gentoolkit.flag import get_all_cpv_usef

        try:
            cpv_str: str = f"{self.package.category}/{self.package.name}-{version_id}"

            # Portage is not thread-safe: serialize against the other workers.
            with portage_lock:
                portage_enabled = set(get_all_cpv_usef(cpv_str)[0])

            self._post_to_loop(self._show_use_flags, version_id, flags, portage_enabled)
        except Exception as e:
            self._post_to_loop(self.notify, f"Failed to load USE flags: {e}", severity="error")

    def _show_use_flags(self, version_id: str, flags: list[str], portage_enabled: set[str]) -> None:
        """Fill the checklist unless the selection moved on (event loop only)."""
        if self.selected_version is None or self.selected_version.id != version_id:
            return

        try:
            use_list: SelectionList = self.query_one("#pkg-use-list", SelectionList)
        except NoMatches:
            # The widget was removed while portage was answering.
            return

        # Only consider flags eix knows about
        enabled_set: set[str] = portage_enabled & set(flags)

        for flag in flags:
            enabled: bool = flag in enabled_set
            self._use_flag_originals[flag] = enabled
            use_list.add_option(Selection(flag, flag, initial_state=enabled))

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        """Show/hide the Apply button when the selection drifts from the original."""
        if event.selection_list.id != "pkg-use-list":
            return

        apply_btn: Button = self.query_one("#use-apply-btn", Button)

        current_enabled: set[str] = set(event.selection_list.selected)
        changed: bool = any(
            (flag in current_enabled) != original for flag, original in self._use_flag_originals.items()
        )

        apply_btn.disabled = not changed

    def _commit_use_flag_changes(self, to_enable: list[str], to_disable: list[str]) -> None:
        """Update the baseline after a successful apply without re-querying portage."""
        for flag in to_enable:
            self._use_flag_originals[flag] = True
        for flag in to_disable:
            self._use_flag_originals[flag] = False

        # Re-evaluate the apply button against the new baseline
        use_list: SelectionList = self.query_one("#pkg-use-list", SelectionList)
        current_enabled: set[str] = set(use_list.selected)  # type: ignore[arg-type]
        changed: bool = any(
            (flag in current_enabled) != original for flag, original in self._use_flag_originals.items()
        )
        self.query_one("#use-apply-btn", Button).disabled = not changed

    @work(exclusive=True, thread=True, group="pkg-deps")
    def _load_deps(self) -> None:
        """Populate the Dependencies tab for the selected version."""
        if self.selected_version is None:
            return

        from gentoolkit.dependencies import Dependencies

        cpv_str: str = f"{self.package.category}/{self.package.name}-{self.selected_version.id}"
        dep = Dependencies(cpv_str)

        config: Configuration = get_config()

        try:
            # Portage is not thread-safe: serialize against the other workers.
            with portage_lock:
                results = dep.graph_depends(max_depth=config.depth)
        except Exception:
            results = []

        if not results:
            results = [(1, atom) for atom in self.selected_version.all_deps()]

        self._post_to_loop(self._populate_dep_tree, results)

    def _populate_dep_tree(self, results: list) -> None:
        """Update the dep tree widget on the main thread."""
        tree: Tree = self.query_one("#pkg-deps-tree", Tree)
        tree.clear()

        if self.selected_version:
            tree.root.label = f"{self.package.category}/[bold]{self.package.name}[/bold]-{self.selected_version.id}"

        tree.root.expand()

        if not results:
            tree.root.add_leaf("[dim]No dependencies found.[/dim]")
            return

        _build_dep_tree(tree.root, results)

    def _load_installed_files(self) -> None:
        """Populate the Installed Files tab. Loaded once on mount; version-agnostic."""
        installed = self.package.installed_version()
        if installed is None:
            return  # Tab is disabled; nothing to do

        self._fetch_installed_files(installed.id)

    @work(thread=True, group="pkg-installed-files")
    def _fetch_installed_files(self, version_id: str) -> None:
        """Read CONTENTS off the event loop; the tree itself builds on it."""
        from gentoolkit.cpv import CPV

        from carnage.core.gentoolkit.package import GentoolkitPackage

        try:
            cpv_str: str = f"{self.package.category}/{self.package.name}-{version_id}"
            gt_pkg = GentoolkitPackage(CPV(cpv_str))

            # Portage is not thread-safe: serialize against the other workers.
            with portage_lock:
                try:
                    contents: dict = gt_pkg.parsed_contents()
                except Exception:
                    contents = {}

            self._post_to_loop(self._show_installed_files, version_id, contents)
        except Exception as e:
            self._post_to_loop(self.notify, f"Failed to load installed files: {e}", severity="error")

    def _show_installed_files(self, version_id: str, contents: dict) -> None:
        """Fill the files tree unless the install state moved on (event loop only)."""
        installed = self.package.installed_version()

        if installed is None or installed.id != version_id:
            return

        try:
            tree: Tree[str] = self.query_one("#pkg-files-tree", Tree)
        except NoMatches:
            # The widget was removed while portage was answering.
            return

        if not contents:
            tree.root.add_leaf("[dim]No installed files found.[/dim]")
            tree.root.expand()
            return

        _build_file_tree(tree.root, "", contents)
        tree.root.expand()

    def _load_versions_table(self) -> None:
        """Fill the versions table without blocking the event loop."""
        self._fetch_versions_table()

    @work(thread=True, group="pkg-versions")
    def _fetch_versions_table(self) -> None:
        """Resolve every row's availability mark off the event loop."""
        try:
            rows: list[tuple[str, str, str]] = []

            non_virtual_ids: set[str] = {v.id for v in self.package.versions if not v.virtual}

            # Portage is not thread-safe: serialize against the other workers.
            with portage_lock:
                for i, version in enumerate(self.package.versions):
                    if version.virtual and version.id in non_virtual_ids:
                        continue
                    rows.append(
                        (
                            f"{version.id}-{i}",
                            self._version_label(version, self.package),
                            version.repository or "gentoo",
                        )
                    )

            self._post_to_loop(self._show_versions_table, rows)
        except Exception as e:
            self._post_to_loop(self.notify, f"Failed to load versions: {e}", severity="error")

    def _show_versions_table(self, rows: list[tuple[str, str, str]]) -> None:
        """Replace the versions table content (event loop only)."""
        try:
            table = self.query_one("#pkg-versions-table", DataTable)
        except NoMatches:
            # The widget was removed while portage was answering.
            return

        self._version_rows = rows

        table.clear()

        for key, label, overlay in rows:
            table.add_row(label, overlay, key=key)

        self._apply_version_selection_marks()

    def _apply_version_selection_marks(self) -> None:
        """Highlight the selected version's rows with reverse video (event loop only)."""
        if not self._version_rows:
            return

        try:
            table = self.query_one("#pkg-versions-table", DataTable)
        except NoMatches:
            return

        selected_id = self.selected_version.id if self.selected_version else None

        for row, (key, label, _overlay) in enumerate(self._version_rows):
            marked = key.rsplit("-", 1)[0] == selected_id
            cell = PackageDetailWidget._mark_selected(label) if marked else label
            table.update_cell_at(Coordinate(row, 0), cell)

    @staticmethod
    def _version_label(version: PackageVersion, pkg: Package) -> str:
        suffix = " (Virtual)" if version.virtual else ""
        if version.installed:
            return f"[green]✓[/green] {version.id}{suffix}"
        gt_pkg: GentoolkitPackage = version.to_gentoolkit(pkg.category, pkg.name)
        if not gt_pkg.available:
            return f"[red]✗[/red] {version.id}{suffix}"
        return f"  {version.id}{suffix}"

    @staticmethod
    def _mark_selected(label: str) -> str:
        """Wrap everything after the status area in reverse video.

        Labels always start with a two-character status area: a marked glyph
        plus a space ("[green]✓[/green] ...") or two literal spaces. Only the
        version text is highlighted; the status mark keeps its own color.
        """
        if label.startswith("  "):
            return f"  [reverse]{label[2:]}[/]"

        split = label.find("] ")

        if split < 0:
            return f"[reverse]{label}[/]"

        split += 2
        return f"{label[:split]}[reverse]{label[split:]}[/]"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is None or event.data_table.id != "pkg-versions-table":
            return

        version_id = event.row_key.value.rsplit("-", 1)[0]  # type: ignore
        version = next((v for v in self.package.versions if v.id == version_id), None)
        if version is None:
            return

        self.selected_version = version
        self._apply_version_selection_marks()
        self._load_use_flags()
        self._load_deps()
        self._load_ebuild()
        self._update_buttons()

        gt_pkg: GentoolkitPackage = version.to_gentoolkit(self.package.category, self.package.name)
        if gt_pkg.available:
            self.notify(f"{self.package.full_name}-{version_id} selected")
        else:
            self.notify(
                f"{self.package.full_name}-{version_id} is unavailable",
                severity="warning",
            )

    @work(exclusive=True, thread=True, group="pkg-world")
    def _load_world_file_status(self) -> None:
        """Check world file membership in a thread then refresh buttons."""
        self._in_world_file = self.package.is_in_world_file()

        self._post_to_loop(self._update_buttons)

    def _update_buttons(self) -> None:
        """Synchronise button visibility with selected_version and world file state."""
        emerge_btn: Button = self.query_one("#emerge-btn", Button)
        depclean_btn: Button = self.query_one("#depclean-btn", Button)
        deselect_btn: Button = self.query_one("#deselect-btn", Button)
        noreplace_btn: Button = self.query_one("#noreplace-btn", Button)

        is_blocked = self.app.blocked  # type: ignore

        is_installed: bool = self.package.is_installed()

        if is_installed:
            emerge_btn.variant = "default"

            depclean_btn.display = True
            # World file buttons depend on async status - hide until known
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

            emerge_btn.variant = "primary"

            depclean_btn.display = False
            deselect_btn.display = False
            noreplace_btn.display = False

        emerge_btn.disabled = not emerge_btn.display or is_blocked
        depclean_btn.disabled = not depclean_btn.display or is_blocked
        deselect_btn.disabled = not deselect_btn.display or is_blocked
        noreplace_btn.disabled = not noreplace_btn.display or is_blocked

    def _mark_installed(self, version_id: str, saved_package_name: str) -> None:
        """Update the Package instance to reflect a successful emerge."""
        # Notify the browse tab to update the checkmark
        browse_tab = self.app.screen.query_one("BrowseTab")

        browse_tab.update_package_installation_status(saved_package_name, True)  # type: ignore

        for v in self.package.versions:
            v.installed = v.id == version_id
        self._load_world_file_status()
        self._load_installed_files()
        self._load_versions_table()
        # Re-enable the files tab
        self.query_one("#tab-files").disabled = False

    def _mark_uninstalled(self, saved_package_name: str) -> None:
        """Update the Package instance to reflect a successful depclean."""
        # Notify the browse tab to update the checkmark
        browse_tab = self.app.screen.query_one("BrowseTab")

        browse_tab.update_package_installation_status(saved_package_name, False)  # type: ignore

        for v in self.package.versions:
            v.installed = False
        self._in_world_file = None
        self._update_buttons()
        self._load_versions_table()
        # Disable the files tab since nothing is installed anymore
        self.query_one("#tab-files").disabled = True

    def _action_apply_use_flags(self) -> None:
        """Diff the checklist against originals and run euse for each change."""
        apply_btn: Button = self.query_one("#use-apply-btn", Button)

        if apply_btn.disabled:
            return

        use_list: SelectionList = self.query_one("#pkg-use-list", SelectionList)
        atom: str = self.package.full_name

        currently_enabled: set[str] = set(use_list.selected)

        to_enable: list[str] = [f for f, was in self._use_flag_originals.items() if not was and f in currently_enabled]
        to_disable: list[str] = [f for f, was in self._use_flag_originals.items() if was and f not in currently_enabled]

        if not to_enable and not to_disable:
            self.notify("No changes to apply", severity="information")
            return

        errors: list[str] = []

        def on_complete(success: bool) -> None:
            if success:
                self._commit_use_flag_changes(to_enable, to_disable)
                self.notify(f"USE flags updated for {atom}")
            else:
                self.notify("Failed to apply some USE flags", severity="error")

            apply_btn.label = "Apply changes"

            self._update_buttons()
            self.app.bell()

        # Disable button and start operations
        apply_btn.disabled = True
        apply_btn.label = "Applying..."

        # We need to chain operations or run them sequentially
        def run_next_operation(idx: int = 0) -> None:
            if idx >= len(operations):
                on_complete(True)
                return

            op_type, flags = operations[idx]

            def op_callback(success: bool) -> None:
                if not success:
                    errors.append(f"{op_type} {flags}: operation failed")
                    on_complete(False)
                else:
                    run_next_operation(idx + 1)

            if op_type == "enable":
                euse_enable(self.app, flags, atom, on_complete=op_callback)
            else:
                euse_disable(self.app, flags, atom, on_complete=op_callback)

        operations = []
        if to_enable:
            operations.append(("enable", to_enable))
        if to_disable:
            operations.append(("disable", to_disable))

        run_next_operation()

    def _action_emerge(self) -> None:
        """Install the selected package version."""
        emerge_btn: Button = self.query_one("#emerge-btn", Button)

        if self.selected_version is None or emerge_btn.disabled:
            return

        emerge_btn.label = "Emerging..."

        atom: str = f"={self.package.full_name}-{self.selected_version.id}"

        saved_package_name = self.package.full_name
        installed: bool = self.package.is_installed()

        self.notify(f"Installing {atom}... (don't close until finished!)", severity="warning", timeout=15)

        def on_complete(success: bool) -> None:
            if success:
                self.notify(f"Successfully installed {atom}")
                try:
                    if not installed:
                        self._mark_installed(self.selected_version.id, saved_package_name)
                    else:
                        for v in self.package.versions:
                            v.installed = v.id == self.selected_version.id

                        self._load_versions_table()
                except NoMatches:
                    # Selected version no longer exists in the updated package data
                    pass
            else:
                self.notify(f"Failed to install {atom}", severity="error")

            try:
                emerge_btn.label = "Emerge"
                self._update_buttons()
            except NoMatches:
                # Widget state changed or package no longer exists
                pass

            self.app.bell()

        emerge_install(self.app, atom, on_complete=on_complete)
        self._update_buttons()

    def _action_depclean(self) -> None:
        """Uninstall the selected package."""
        depclean_btn: Button = self.query_one("#depclean-btn", Button)

        if not self.package.is_installed() or depclean_btn.disabled:
            return

        depclean_btn.label = "Cleaning..."

        atom: str = self.package.full_name

        saved_package_name = self.package.full_name

        self.notify(f"Removing {atom}... (don't close until finished!)", severity="warning", timeout=15)

        def on_complete(success: bool) -> None:
            if success:
                self.notify(f"Successfully removed {atom}")
                try:
                    self._mark_uninstalled(saved_package_name)
                except NoMatches:
                    # Selected version no longer exists in the updated package data
                    pass
            else:
                self.notify(f"Failed to remove {atom}", severity="error")

            try:
                depclean_btn.label = "Depclean"
                self._update_buttons()
            except NoMatches:
                # Widget state changed or package no longer exists
                pass

            self.app.bell()

        emerge_uninstall(self.app, atom, on_complete=on_complete)
        self._update_buttons()

    def _action_deselect(self) -> None:
        """Remove package from world file."""
        deselect_btn: Button = self.query_one("#deselect-btn", Button)

        if deselect_btn.disabled:
            return

        deselect_btn.label = "Deselecting..."

        atom: str = self.package.full_name

        self.notify(f"Removing {atom} from world file...", severity="warning", timeout=10)

        def on_complete(success: bool) -> None:
            if success:
                self.notify(f"Successfully removed {atom} from world file")
                self._load_world_file_status()
            else:
                self.notify(f"Failed to remove from world file: {atom}", severity="error")

            deselect_btn.label = "Deselect"

            self._update_buttons()
            self.app.bell()

        emerge_deselect(self.app, atom, on_complete=on_complete)
        self._update_buttons()

    def _action_noreplace(self) -> None:
        """Add package to world file."""
        noreplace_btn: Button = self.query_one("#noreplace-btn", Button)

        if noreplace_btn.disabled:
            return

        noreplace_btn.label = "Noreplacing..."

        atom: str = self.package.full_name

        self.notify(f"Adding {atom} to world file...", severity="warning", timeout=10)

        def on_complete(success: bool) -> None:
            if success:
                self.notify(f"Successfully added {atom} to world file")
                self._load_world_file_status()
            else:
                self.notify(f"Failed to add to world file: {atom}", severity="error")

            noreplace_btn.label = "Noreplace"

            self._update_buttons()
            self.app.bell()

        emerge_noreplace(self.app, atom, on_complete=on_complete)
        self._update_buttons()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.disabled:
            return

        if event.button.id == "use-apply-btn":
            self._action_apply_use_flags()
        elif event.button.id == "emerge-btn":
            self._action_emerge()
        elif event.button.id == "depclean-btn":
            self._action_depclean()
        elif event.button.id == "deselect-btn":
            self._action_deselect()
        elif event.button.id == "noreplace-btn":
            self._action_noreplace()
