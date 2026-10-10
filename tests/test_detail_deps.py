"""Tests for the dependencies pane surviving mount and reselection."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Tree

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
        depend="sys-libs/ncurses",
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


def _labels(tree: Tree) -> list[str]:
    found: list[str] = []

    def walk(node) -> None:
        for child in node.children:
            found.append(str(child.label))
            walk(child)

    walk(tree.root)
    return found


async def test_mount_populates_dependencies_without_selection() -> None:
    """The mount-time deps worker used to be cancelled by the world worker."""
    app = _Harness(_package())
    async with app.run_test() as pilot:
        widget = app.query_one(PackageDetailWidget)
        await pilot.pause(1.5)

        assert _labels(widget.query_one("#pkg-deps-tree", Tree)) != []


async def test_dependencies_survive_reselection() -> None:
    app = _Harness(_package())
    async with app.run_test() as pilot:
        widget = app.query_one(PackageDetailWidget)
        await pilot.pause(1.5)

        table = widget.query_one("#pkg-versions-table", DataTable)
        key = table._row_locations.get_key(0)
        assert key is not None
        event = DataTable.RowSelected(data_table=table, cursor_row=0, row_key=key)

        widget.on_data_table_row_selected(event)
        await pilot.pause(1.5)
        first = _labels(widget.query_one("#pkg-deps-tree", Tree))

        widget.on_data_table_row_selected(event)
        await pilot.pause(1.5)
        second = _labels(widget.query_one("#pkg-deps-tree", Tree))

        assert first != []
        assert second == first
