"""Tests for the pure package formatting helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from carnage.core.eix.search import Package, PackageVersion
from carnage.core.formatting import format_package_details, package_row_label


def _version(**overrides: Any) -> PackageVersion:
    defaults: dict[str, Any] = {
        "id": "9.0.0",
        "eapi": "8",
        "repository": "gentoo",
        "virtual": False,
        "installed": False,
        "install_date": None,
        "install_eapi": None,
        "src_uri": None,
        "iuse": [],
        "iuse_default": [],
        "required_use": None,
        "depend": None,
        "rdepend": None,
        "bdepend": None,
        "pdepend": None,
        "idepend": None,
        "masks": [],
        "unmasks": [],
        "properties": [],
        "restricts": [],
        "use_enabled": [],
        "use_disabled": [],
    }
    defaults.update(overrides)

    return PackageVersion(**defaults)


def _package(**overrides: Any) -> Package:
    defaults: dict[str, Any] = {
        "category": "app-editors",
        "name": "vim",
        "description": "Vi IMproved",
        "homepage": "https://example.invalid",
        "licenses": ["vim"],
        "versions": [],
    }
    defaults.update(overrides)

    return Package(**defaults)


def test_row_label_marks_installed_packages_green() -> None:
    label = package_row_label(_package(), installed=True, exists=False)

    assert label == "[green]✓[/green] app-editors/[bold]vim[/bold]"


def test_row_label_marks_missing_packages_red() -> None:
    label = package_row_label(_package(), installed=False, exists=False)

    assert label == "[red]✗[/red] app-editors/[bold]vim[/bold]"


def test_row_label_keeps_available_packages_plain() -> None:
    label = package_row_label(_package(), installed=False, exists=True)

    assert label == "  app-editors/[bold]vim[/bold]"


def test_details_include_the_selected_version() -> None:
    details = format_package_details(_package(), _version(id="9.1.2"))

    assert "[/] 9.1.2" in details


def test_details_omit_the_version_when_none_is_selected() -> None:
    details = format_package_details(_package(), None)

    assert details.startswith("[r]app-editors/[b]vim[/][/]\n\n")


def test_details_describe_the_package() -> None:
    details = format_package_details(_package(), None)

    assert "Vi IMproved" in details
    assert "[dim]https://example.invalid[/]" in details
    assert "[dim][b]License(s):[/] vim[/]" in details


def test_details_show_the_install_date_when_known() -> None:
    installed = _version(installed=True, install_date=1700000000)
    details = format_package_details(_package(versions=[installed]), None)

    assert datetime.fromtimestamp(1700000000).strftime("%Y") in details


def test_details_omit_the_install_date_when_unknown() -> None:
    """install_date comes from eix and is not always there."""
    installed = _version(installed=True, install_date=None)
    details = format_package_details(_package(versions=[installed]), None)

    assert "Last installed at" not in details
