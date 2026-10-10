"""Tests for the overlays tab filter debounce and row marks."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate

import carnage.tui.widgets.overlay_tab as overlay_tab_module
from carnage.core.cache import CacheManager
from carnage.core.portage.overlays import (
    Overlay,
    OverlayQuality,
    OverlayStatus,
    Owner,
    Source,
    SourceType,
)
from carnage.tui.widgets.overlay_tab import OverlaysTab


class _Config:
    skip_package_counting = True
    ignore_warnings = True


def _overlay(name: str, *, installed: bool) -> Overlay:
    return Overlay(
        name=name,
        description="A test overlay",
        homepage=None,
        owner=Owner(name="Alice", email="a@example.invalid", owner_type="person"),
        sources=[Source(source_type=SourceType.GIT, url="https://example.invalid/repo")],
        feeds=[],
        quality=OverlayQuality.CORE,
        status=OverlayStatus.UNOFFICIAL,
        installed=installed,
        package_count=3,
    )


class _Harness(App[None]):
    blocked = False

    def compose(self) -> ComposeResult:
        yield OverlaysTab()


@pytest.fixture(autouse=True)
def isolated_overlay_tab(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(overlay_tab_module, "get_config", lambda: _Config())
    monkeypatch.setattr(overlay_tab_module, "get_cache_manager", lambda: CacheManager(tmp_path / "cache"))
    monkeypatch.setattr(overlay_tab_module, "is_found", lambda: False)
    monkeypatch.setattr(OverlaysTab, "load_overlays", lambda self: None)


async def test_filter_is_debounced_and_clearing_is_immediate() -> None:
    app = _Harness()

    async with app.run_test() as pilot:
        tab = app.query_one(OverlaysTab)
        tab.overlays = [_overlay("alpha", installed=False), _overlay("beta", installed=False)]
        tab.filtered_overlays = list(tab.overlays)

        tab.apply_filter("alpha")
        assert tab._filter_timer is not None
        # Not applied yet: still showing everything.
        assert [o.name for o in tab.filtered_overlays] == ["alpha", "beta"]

        await pilot.pause(0.5)

        assert [o.name for o in tab.filtered_overlays] == ["alpha"]

        # Clearing the box applies at once instead of waiting out a debounce.
        tab.apply_filter("")
        assert tab._filter_timer is None
        assert [o.name for o in tab.filtered_overlays] == ["alpha", "beta"]


async def test_rows_use_the_stored_installed_flag() -> None:
    (
        """No filesystem stat: a name that exists nowhere must still get its mark."""
        """No filesystem stat: a name that exists nowhere must still get its mark."""
    )
    app = _Harness()

    async with app.run_test():
        tab = app.query_one(OverlaysTab)
        tab.overlays = [
            _overlay("definitely-not-on-disk-xyz", installed=True),
            _overlay("other-not-on-disk-xyz", installed=False),
        ]
        tab.filtered_overlays = list(tab.overlays)

        tab._populate_table()

        table = tab.table
        assert table.row_count == 2
        assert "✓" in str(table.get_cell_at(Coordinate(0, 0)))
        assert "✓" not in str(table.get_cell_at(Coordinate(1, 0)))


async def test_remote_cache_notification_needs_no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """The probe result is handed in, so notifying never touches the loop."""
    app = _Harness()

    async with app.run_test():
        tab = app.query_one(OverlaysTab)
        monkeypatch.setattr(tab._config, "ignore_warnings", False)
        tab.overlays = [_overlay(f"overlay-{i}", installed=False) for i in range(9)]
        for overlay in tab.overlays:
            overlay.package_count = 0

        notices: list[str] = []
        tab.notify = lambda message, *args, **kwargs: notices.append(str(message))  # type: ignore

        tab._maybe_notify_remote_cache(True)
        assert len(notices) == 1

        tab._maybe_notify_remote_cache(False)
        assert len(notices) == 1
