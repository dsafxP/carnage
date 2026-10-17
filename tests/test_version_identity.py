"""Tests for (id, repository) version identity across overlays."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from carnage.core.eix.search import Package, PackageVersion
from carnage.core.formatting import version_display
from carnage.tui.widgets.browse.package_detail import (
    PackageDetailWidget,
    find_version,
    version_identity,
    version_key,
)


def _version(version_id: str, repository: str | None) -> PackageVersion:
    return PackageVersion(
        id=version_id,
        eapi="8",
        repository=repository,
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
        versions=[
            _version("1.0", "gentoo"),
            _version("1.0", "guru"),
            _version("2.0", "gentoo"),
        ],
    )


def test_keys_distinguish_same_id_across_overlays() -> None:
    package = _package()
    keys = [version_key(v, i) for i, v in enumerate(package.versions)]

    assert len(set(keys)) == 3
    assert find_version(package, keys[1]) is package.versions[1]


def test_find_version_rejects_unknown_keys() -> None:
    package = _package()

    assert find_version(package, "bogus") is None
    assert find_version(package, "1.0::missing::9") is None
    assert find_version(package, "9.9::gentoo::0") is None


def test_identity_pairs_id_with_repo() -> None:
    assert version_identity(_version("1.0", "guru")) == ("1.0", "guru")
    assert version_identity(_version("1.0", None)) == ("1.0", None)


def test_version_display_qualifies_non_gentoo() -> None:
    assert version_display(_version("1.0", None)) == "1.0"
    assert version_display(_version("1.0", "gentoo")) == "1.0"
    assert version_display(_version("1.0", "guru")) == "1.0::guru"


class _Harness(App[None]):
    blocked = False

    def __init__(self, package: Package) -> None:
        super().__init__()
        self._package = package

    def compose(self) -> ComposeResult:
        yield PackageDetailWidget(self._package)


def _cell(widget: PackageDetailWidget, row: int) -> str:
    table = widget.query_one("#pkg-versions-table", DataTable)
    return str(table.get_cell_at(Coordinate(row, 0)))


async def test_selecting_same_id_from_another_overlay_switches_object() -> None:
    """Same version id in two overlays: each row selects its own object."""
    app = _Harness(_package())

    async with app.run_test() as pilot:
        widget = app.query_one(PackageDetailWidget)
        await pilot.pause(1.5)

        table = widget.query_one("#pkg-versions-table", DataTable)
        assert table.row_count == 3

        guru_key = table._row_locations.get_key(1)
        assert guru_key is not None
        widget.on_data_table_row_selected(DataTable.RowSelected(data_table=table, cursor_row=1, row_key=guru_key))
        await pilot.pause(0.3)

        assert widget.selected_version is widget.package.versions[1]
        assert widget.selected_version is not None
        assert widget.selected_version.repository == "guru"

        marked = [i for i in range(3) if "[reverse]" in _cell(widget, i)]
        assert marked == [1]

        gentoo_key = table._row_locations.get_key(0)
        assert gentoo_key is not None
        widget.on_data_table_row_selected(DataTable.RowSelected(data_table=table, cursor_row=0, row_key=gentoo_key))
        await pilot.pause(0.3)

        assert widget.selected_version is widget.package.versions[0]
        marked = [i for i in range(3) if "[reverse]" in _cell(widget, i)]
        assert marked == [0]
