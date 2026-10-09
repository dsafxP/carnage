"""Tests for the pure package formatting helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from carnage.core.eix.search import Package, PackageVersion
from carnage.core.formatting import (
    format_glsa_details,
    format_glsa_header,
    format_package_details,
    package_row_label,
)
from carnage.core.portage.glsas import GLSA, AffectedPackage, Resolution


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


def _glsa(**overrides: Any) -> GLSA:
    defaults: dict[str, Any] = {
        "id": "GLSA-2024-0001",
        "title": "A title",
        "synopsis": "A synopsis",
        "product": "app-misc/foo",
        "announced": "2024-01-15",
        "revised": None,
        "revision_count": "01",
        "bugs": ["123456"],
        "access": "remote",
        "background": "Some background",
        "description": "A description",
        "impact": "An impact",
        "impact_type": "normal",
        "workaround": None,
        "resolutions": [],
        "affected_packages": [],
        "references": ["https://example.invalid"],
    }
    defaults.update(overrides)

    return GLSA(**defaults)


def test_glsa_header_shows_the_identifying_fields() -> None:
    header = format_glsa_header(_glsa())

    assert header.startswith("[r]A title[/]")
    assert "[dim][b]ID:[/] GLSA-2024-0001[/]" in header
    assert "[dim][b]Product:[/] app-misc/foo[/]" in header
    assert "[dim][b]Announced:[/] 2024-01-15[/]" in header
    assert "[dim][b]Severity:[/] normal[/]" in header
    assert "[dim][b]Exploitable:[/] remote[/]" in header


def test_glsa_header_falls_back_to_the_synopsis() -> None:
    header = format_glsa_header(_glsa(title=None))

    assert header.startswith("[r]A synopsis[/]")


def test_glsa_details_render_version_conditions_with_symbols() -> None:
    package = AffectedPackage(
        name="app-misc/foo",
        auto="auto",
        arch="amd64",
        unaffected_conditions=[{"range": "lt", "value": "1.0", "slot": None}],
        vulnerable_conditions=[{"range": "ge", "value": "2.0", "slot": "0"}],
    )
    details = format_glsa_details(_glsa(affected_packages=[package]))

    assert "[r]app-misc/foo[/] on [b]amd64[/]" in details
    assert "[red][b]Affected versions:[/] ≥ [bold]2.0:0[/bold][/red]" in details
    assert "[green][b]Unaffected versions:[/] < [bold]1.0[/bold][/green]" in details


def test_glsa_details_render_optional_sections() -> None:
    details = format_glsa_details(
        _glsa(workaround="Do this", resolutions=[Resolution(text="Run that", code="emerge -1 foo")])
    )

    assert "[b]Workaround:[/]\nDo this" in details
    assert "Run that" in details
    assert "[dim]emerge -1 foo[/dim]" in details
    assert "https://bugs.gentoo.org/123456" in details


def test_glsa_details_omit_absent_sections() -> None:
    details = format_glsa_details(_glsa(background=None, workaround=None, references=[]))

    assert "Background" not in details
    assert "Workaround" not in details
    assert "References" not in details
