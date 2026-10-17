"""Tests for the asynchronously loaded detail panes."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import DataTable, SelectionList

from carnage.core.eix.search import Package, PackageVersion
from carnage.tui.widgets.browse.package_detail import PackageDetailWidget


def _version(version_id: str, *, installed: bool = False) -> PackageVersion:
    return PackageVersion(
        id=version_id,
        eapi="8",
        repository="gentoo",
        virtual=False,
        installed=installed,
        install_date=None,
        install_eapi=None,
        src_uri=None,
        iuse=["gui"],
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
        description="Vi IMproved",
        homepage=None,
        licenses=[],
        versions=[_version("9.0.0"), _version("9.1.0", installed=True)],
    )


class _Harness(App[None]):
    blocked = False

    def __init__(self, package: Package) -> None:
        super().__init__()
        self._package = package

    def compose(self) -> ComposeResult:
        yield PackageDetailWidget(self._package)


async def test_versions_table_fills_in_after_mount() -> None:
    app = _Harness(_package())

    async with app.run_test() as pilot:
        widget = app.query_one(PackageDetailWidget)
        await pilot.pause(1.0)

        table = widget.query_one("#pkg-versions-table", DataTable)
        assert table.row_count == 2


async def test_stale_version_results_are_dropped() -> None:
    app = _Harness(_package())

    async with app.run_test() as pilot:
        widget = app.query_one(PackageDetailWidget)
        await pilot.pause(1.0)

        # A worker that finished after the selection moved on must not paint.
        widget.selected_version = widget.package.versions[0]
        before = dict(widget._use_flag_originals)
        widget._show_use_flags("9.1.0", "gentoo", ["gui"], {"gui"})
        assert widget._use_flag_originals == before

        widget._show_use_flags("9.0.0", "gentoo", ["gui"], {"gui"})
        assert widget._use_flag_originals == {"gui": True}

        use_list = widget.query_one("#pkg-use-list", SelectionList)
        assert use_list.option_count >= 1
