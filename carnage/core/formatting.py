"""Pure formatting helpers for the package views.

These build Rich markup strings from parsed eix data only, so they live away
from the widgets and can be tested without a running app.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from carnage.core.eix.search import Package, PackageVersion

if TYPE_CHECKING:
    from carnage.core.portage.glsas import GLSA


def format_package_details(package: Package, selected_version: PackageVersion | None) -> str:
    """
    Format the top-level package details block of the browse detail pane.

    Args:
        package: Package to describe
        selected_version: Version currently selected, if any

    Returns:
        Markup string ready for a Textual Static
    """
    version_label: str = f" {selected_version.id}" if selected_version else ""
    details: str = f"[r]{package.category}/[b]{package.name}[/][/]{version_label}\n\n"

    if package.description:
        details += f"{package.description}\n\n"

    installed = package.installed_version()

    if installed is not None and installed.install_date is not None:
        details += f"[green]Last installed at [b]{datetime.fromtimestamp(installed.install_date)}[/][/]\n\n"

    if package.homepage:
        details += f"[dim]{package.homepage}[/]\n\n"

    if package.licenses:
        details += f"[dim][b]License(s):[/] {', '.join(package.licenses)}[/]\n"

    return details.rstrip()


def package_row_label(package: Package, *, installed: bool, exists: bool) -> str:
    """
    Build the first cell of a browse-table row.

    Args:
        package: Package the row shows
        installed: Whether the package is installed on disk
        exists: Whether eix could find it in a repo

    Returns:
        Markup string, marked green when installed, red when it is missing
        from every repo
    """
    name = f"{package.category}/[bold]{package.name}[/bold]"

    if installed:
        return f"[green]✓[/green] {name}"

    if not exists:
        return f"[red]✗[/red] {name}"

    return f"  {name}"


_RANGE_SYMBOLS: dict[str, str] = {
    "lt": "<",
    "le": "≤",
    "eq": "=",
    "ge": "≥",
    "gt": ">",
    "rge": "≳",
    "rle": "≲",
    "rgt": ">~",
    "rlt": "<~",
}


def _range_symbol(range_str: str) -> str:
    """Convert a version range operator to its symbol."""
    return _RANGE_SYMBOLS.get(range_str, range_str)


def _format_conditions(conditions: list[dict], *, label: str, style: str) -> str:
    """Render one group of version conditions as a single line."""
    rendered: list[str] = []

    for condition in conditions:
        slot_info = f":{condition['slot']}" if condition["slot"] else ""
        rendered.append(f"{_range_symbol(condition['range'])} [bold]{condition['value']}{slot_info}[/bold]")

    return f"[{style}][b]{label}[/] {', '.join(rendered)}[/{style}]\n"


def format_glsa_header(glsa: GLSA) -> str:
    """
    Build the title block shown above a GLSA's details.

    Args:
        glsa: Advisory to describe

    Returns:
        Markup string ready for a Textual Static
    """
    header: str = f"[r]{glsa.title or glsa.synopsis}[/]\n\n"

    if glsa.product:
        header += f"[dim][b]Product:[/] {glsa.product}[/]\n"

    header += f"[dim][b]ID:[/] {glsa.id}[/]\n"

    if glsa.announced:
        header += f"[dim][b]Announced:[/] {glsa.announced}[/]\n"

    if glsa.impact_type:
        header += f"[dim][b]Severity:[/] {glsa.impact_type}[/]\n"

    if glsa.access:
        header += f"[dim][b]Exploitable:[/] {glsa.access}[/]"

    return header


def _format_affected_packages(glsa: GLSA) -> str:
    """Affected packages, each with its vulnerable and unaffected ranges."""
    if not glsa.affected_packages:
        return ""

    details: str = "[b]Affected Packages:[/]\n\n"

    for package in glsa.affected_packages:
        details += f"[dim][b]Package:[/] [r]{package.name}[/] on [b]{package.arch}[/][/dim]\n"

        if package.vulnerable_conditions:
            details += _format_conditions(package.vulnerable_conditions, label="Affected versions:", style="red")

        if package.unaffected_conditions:
            details += _format_conditions(package.unaffected_conditions, label="Unaffected versions:", style="green")

        details += "\n"  # spacing between packages

    return details


def _format_resolutions(glsa: GLSA) -> str:
    """Ordered fix steps."""
    if not glsa.resolutions:
        return ""

    details: str = "[b]Resolution:[/]\n"

    for i, resolution in enumerate(glsa.resolutions, 1):
        if resolution.text:
            details += f"{resolution.text}\n"

        if resolution.code:
            details += f"[dim]{resolution.code}[/dim]\n"

        # Spacing between multiple resolutions, but not after the last one
        if i < len(glsa.resolutions):
            details += "\n"

    return details


def format_glsa_details(glsa: GLSA) -> str:
    """
    Build the body of a GLSA's detail pane.

    Args:
        glsa: Advisory to render

    Returns:
        Markup string ready for a Textual Static
    """
    details: str = _format_affected_packages(glsa)

    if glsa.background:
        details += f"[b]Background:[/]\n{glsa.background}\n\n"

    if glsa.description:
        details += f"[b]Description:[/]\n{glsa.description}\n\n"

    if glsa.impact:
        details += f"[b]Impact:[/]\n{glsa.impact}\n\n"

    if glsa.workaround:
        details += f"[b]Workaround:[/]\n{glsa.workaround}\n\n"

    details += _format_resolutions(glsa)

    if glsa.references:
        details += "[b]References:[/]\n"
        for ref in glsa.references:
            details += f"  • {ref}\n"
        details += "\n"

    if glsa.bugs:
        details += "[b]Bugzilla entries:[/]\n"
        for bug in glsa.bugs:
            details += f"  • [link='https://bugs.gentoo.org/{bug}']{bug}[/link]\n"

    return details
