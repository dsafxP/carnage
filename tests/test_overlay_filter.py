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


def _overlay(
    name: str, *, installed: bool, package_count: int | None = 3, status: OverlayStatus = OverlayStatus.UNOFFICIAL
) -> Overlay:
    return Overlay(
        name=name,
        description="A test overlay",
        homepage=None,
        owner=Owner(name="Alice", email="a@example.invalid", owner_type="person"),
        sources=[Source(source_type=SourceType.GIT, url="https://example.invalid/repo")],
        feeds=[],
        quality=OverlayQuality.CORE,
        status=status,
        installed=installed,
        package_count=package_count,
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
        monkeypatch.setattr(tab, "notify", lambda message, *args, **kwargs: notices.append(str(message)))

        tab._maybe_notify_remote_cache(True)
        assert len(notices) == 1

        tab._maybe_notify_remote_cache(False)
        assert len(notices) == 1


def _names(tab: OverlaysTab) -> list[str]:
    return [overlay.name for overlay in tab.filtered_overlays]


def _first_cells(tab: OverlaysTab) -> list[str]:
    table = tab.table
    return [str(table.get_cell_at(Coordinate(row, 0))) for row in range(table.row_count)]


async def test_empty_overlays_sink_stably_to_the_bottom() -> None:
    app = _Harness()
    async with app.run_test():
        tab = app.query_one(OverlaysTab)
        tab.overlays = [
            _overlay("zero-a", installed=False, package_count=0),
            _overlay("five", installed=True, package_count=5),
            _overlay("zero-b", installed=False, package_count=0),
            _overlay("two", installed=False, package_count=2),
        ]
        tab.filtered_overlays = list(tab.overlays)
        tab._populate_table()

        assert _names(tab) == ["five", "two", "zero-a", "zero-b"]

        cells = _first_cells(tab)
        assert "[dim]" not in cells[0]
        assert "[dim]" not in cells[1]
        assert "[dim]" in cells[2]
        assert "[dim]" in cells[3]


async def test_unknown_counts_sink_like_zero() -> None:
    app = _Harness()
    async with app.run_test():
        tab = app.query_one(OverlaysTab)
        tab.overlays = [
            _overlay("known", installed=False, package_count=4),
            _overlay("unknown", installed=False, package_count=None),
        ]
        tab.filtered_overlays = list(tab.overlays)
        tab._populate_table()

        assert _names(tab) == ["known", "unknown"]
        assert "[dim]" in _first_cells(tab)[1]


async def test_official_styling_survives_dimming() -> None:
    app = _Harness()
    async with app.run_test():
        tab = app.query_one(OverlaysTab)
        tab.overlays = [_overlay("gentoo", installed=True, package_count=0, status=OverlayStatus.OFFICIAL)]
        tab.filtered_overlays = list(tab.overlays)
        tab._populate_table()

        (cell,) = _first_cells(tab)
        assert "[dim]" in cell and "[italic]" in cell


@pytest.mark.parametrize(
    ("total", "zeros", "warns"),
    [
        (100, 20, False),  # below the quarter threshold
        (100, 30, True),  # above it
        (400, 100, False),  # ~100 zeros on a full list is still fine
        (400, 101, True),
        (20, 8, False),  # floor holds for tiny lists
        (20, 9, True),
    ],
)
async def test_stale_cache_warning_scales_with_list_size(
    monkeypatch: pytest.MonkeyPatch, total: int, zeros: int, warns: bool
) -> None:
    app = _Harness()
    async with app.run_test():
        tab = app.query_one(OverlaysTab)
        monkeypatch.setattr(tab._config, "ignore_warnings", False)
        tab.overlays = [
            _overlay(f"overlay-{i}", installed=False, package_count=0 if i < zeros else 5) for i in range(total)
        ]

        notices: list[str] = []
        monkeypatch.setattr(tab, "notify", lambda *args, **kwargs: notices.append(str(args[0])))

        tab._maybe_notify_remote_cache(True)

        assert (len(notices) == 1) is warns


async def test_no_remote_cache_never_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _Harness()
    async with app.run_test():
        tab = app.query_one(OverlaysTab)
        monkeypatch.setattr(tab._config, "ignore_warnings", False)
        tab.overlays = [_overlay(f"overlay-{i}", installed=False, package_count=0) for i in range(50)]

        notices: list[str] = []
        monkeypatch.setattr(tab, "notify", lambda *args, **kwargs: notices.append(str(args[0])))

        tab._maybe_notify_remote_cache(False)

        assert notices == []
