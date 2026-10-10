"""Tests for workers outliving the detail widget."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.worker import WorkerState

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


async def test_post_to_loop_reports_detach() -> None:
    """From a worker thread: True while mounted, False once detached."""
    import asyncio

    async def call_in_executor(widget: PackageDetailWidget) -> bool:
        """Run the helper the way Textual thread workers do: no context."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, widget._post_to_loop, lambda: None)

    app = _Harness(_package())
    async with app.run_test() as pilot:
        widget = app.query_one(PackageDetailWidget)

        assert await call_in_executor(widget) is True

        await widget.remove()
        await pilot.pause(0.3)

        assert await call_in_executor(widget) is False


async def test_detached_versions_worker_completes_without_error() -> None:
    """The emerge-time crash: rows done, widget gone, app must survive."""
    app = _Harness(_package())
    async with app.run_test() as pilot:
        widget = app.query_one(PackageDetailWidget)
        await pilot.pause(0.5)

        await widget.remove()
        await pilot.pause(0.3)

        worker = widget._fetch_versions_table()
        await pilot.pause(2.0)

        assert worker.state == WorkerState.SUCCESS

        # The app is still alive and usable.
        assert app.is_running
