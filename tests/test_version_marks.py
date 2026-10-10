"""Tests for the selected-version highlight in the versions table."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from carnage.core.eix.search import Package, PackageVersion
from carnage.tui.widgets.browse.package_detail import PackageDetailWidget


def _version(version_id: str) -> PackageVersion:
    return PackageVersion(
        id=version_id,
        eapi="8",
        repository="gentoo",
        virtual=False,
        installed=False,
        install_date=None,
        install_eapi=None,
        src_uri=None,
        iuse=[],
        iuse_default=[],
        required_use=None,
        depend=None,
        rdepend=None,
        bdepend=None,
        pdepend=None,
        idepend=None,
        masks=[],
        unmasks=[],
        properties=[],
        restricts=[],
        use_enabled=[],
        use_disabled=[],
    )


def _package() -> Package:
    return Package(
        category="app-editors",
        name="vim",
        description="d",
        homepage=None,
        licenses=[],
        versions=[_version("9.0.0"), _version("9.1.0")],
    )


class _Harness(App[None]):
    blocked = False

    def __init__(self, package: Package) -> None:
        super().__init__()
        self._package = package

    def compose(self) -> ComposeResult:
        yield PackageDetailWidget(self._package)


def _cell(tab_widget: PackageDetailWidget, row: int) -> str:
    table = tab_widget.query_one("#pkg-versions-table", DataTable)
    return str(table.get_cell_at(Coordinate(row, 0)))


async def test_default_selection_is_highlighted() -> None:
    app = _Harness(_package())
    async with app.run_test() as pilot:
        widget = app.query_one(PackageDetailWidget)
        await pilot.pause(1.5)

        selected = widget.selected_version
        assert selected is not None

        marked = [i for i in range(2) if "[reverse]" in _cell(widget, i)]
        assert len(marked) == 1
        assert selected.id in _cell(widget, marked[0])


async def test_highlight_follows_selection() -> None:
    app = _Harness(_package())
    async with app.run_test() as pilot:
        widget = app.query_one(PackageDetailWidget)
        await pilot.pause(1.5)

        table = widget.query_one("#pkg-versions-table", DataTable)
        key = table._row_locations.get_key(0)
        assert key is not None
        widget.on_data_table_row_selected(DataTable.RowSelected(data_table=table, cursor_row=0, row_key=key))
        await pilot.pause(0.3)

        assert widget.selected_version is not None
        assert widget.selected_version.id == "9.0.0"
        assert "[reverse]" in _cell(widget, 0)
        assert "[reverse]" not in _cell(widget, 1)
        # The status area itself is never reversed.
        assert not _cell(widget, 0).startswith("[reverse]")


def test_mark_selected_skips_the_status_area() -> None:
    """The tick/space prefix keeps its own styling; only the version reverses."""
    mark = PackageDetailWidget._mark_selected

    assert mark("[green]✓[/green] 9.2.1152") == "[green]✓[/green] [reverse]9.2.1152[/]"
    assert mark("[red]✗[/red] 9999 (Virtual)") == "[red]✗[/red] [reverse]9999 (Virtual)[/]"
    assert mark("  9.0.0") == "  [reverse]9.0.0[/]"


def test_mark_selected_falls_back_to_the_whole_label() -> None:
    assert PackageDetailWidget._mark_selected("9.0.0") == "[reverse]9.0.0[/]"


async def test_reselecting_the_same_version_is_a_noop() -> None:
    """Clicking the displayed version again restarts nothing and notifies nothing."""
    app = _Harness(_package())
    async with app.run_test() as pilot:
        widget = app.query_one(PackageDetailWidget)
        await pilot.pause(1.5)

        table = widget.query_one("#pkg-versions-table", DataTable)
        key = table._row_locations.get_key(0)
        assert key is not None

        def select() -> None:
            widget.on_data_table_row_selected(DataTable.RowSelected(data_table=table, cursor_row=0, row_key=key))

        select()
        await pilot.pause(0.5)

        calls: list[str] = []
        notes: list[str] = []
        widget._load_use_flags = lambda: calls.append("use")  # type: ignore[method-assign]
        widget._load_deps = lambda: calls.append("deps")  # type: ignore[method-assign]
        widget._load_ebuild = lambda: calls.append("ebuild")  # type: ignore[method-assign]
        widget.notify = lambda *args, **kwargs: notes.append(str(args[0]))  # type: ignore[method-assign]

        select()
        await pilot.pause(0.5)

        assert calls == []
        assert notes == []
