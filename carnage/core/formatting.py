"""Pure formatting helpers for the package views.

These build Rich markup strings from parsed eix data only, so they live away
from the widgets and can be tested without a running app.
"""

from datetime import datetime

from carnage.core.eix.search import Package, PackageVersion


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
