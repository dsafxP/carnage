"""Package search functionality using direct eix queries."""

import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from subprocess import CompletedProcess
from xml.etree.ElementTree import Element


@dataclass
class PackageVersion:
    """Represents a specific version of a package."""
    id: str
    eapi: str | None
    repository: str | None
    virtual: bool
    installed: bool
    src_uri: str | None
    iuse: list[str]
    iuse_default: list[str]
    required_use: str | None
    depend: str | None
    rdepend: str | None
    bdepend: str | None
    pdepend: str | None
    idepend: str | None
    masks: list[str]
    unmasks: list[str]
    properties: list[str]
    restricts: list[str]
    use_enabled: list[str]
    use_disabled: list[str]


@dataclass
class Package:
    """Represents a Gentoo package with all its versions."""
    category: str
    name: str
    description: str | None
    homepage: str | None
    licenses: list[str]
    versions: list[PackageVersion] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        """Get the full package name (category/name)."""
        return f"{self.category}/{self.name}"

    def __str__(self) -> str:
        return self.full_name

    def __repr__(self) -> str:
        return f"Package({self.full_name!r}, versions={len(self.versions)})"

    def is_installed(self) -> bool:
        """Check if any version of this package is installed."""
        return any(v.installed for v in self.versions)

    def installed_version(self) -> PackageVersion | None:
        """Get the installed version, if any."""
        for v in self.versions:
            if v.installed:
                return v
        return None


def _parse_version(version_elem: ET.Element) -> PackageVersion:
    """Parse a version element from eix XML."""
    iuse_elems: list[Element] = version_elem.findall("iuse")
    iuse: list[str] = []
    iuse_default: list[str] = []

    for iuse_elem in iuse_elems:
        flags: list[str] = iuse_elem.text.split() if iuse_elem.text else []
        for flag in flags:
            iuse.append(flag)
            if iuse_elem.get("default") == "1":
                iuse_default.append(flag)

    # Parse masks
    masks: list[str] = [m.get("type", "") for m in version_elem.findall("mask")]
    unmasks: list[str] = [u.get("type", "") for u in version_elem.findall("unmask")]

    # Parse properties
    properties: list[str] = [p.get("flag", "") for p in version_elem.findall("properties")]

    # Parse restricts
    restricts: list[str] = [r.get("flag", "") for r in version_elem.findall("restrict")]

    # Parse use flags
    use_elems: list[Element] = version_elem.findall("use")
    use_enabled = []
    use_disabled = []

    for use_elem in use_elems:
        if use_elem.get("enabled") == "1":
            use_enabled = use_elem.text.split() if use_elem.text else []
        elif use_elem.get("enabled") == "0":
            use_disabled = use_elem.text.split() if use_elem.text else []

    # Get depend fields
    depend_elem = version_elem.find("depend")
    rdepend_elem = version_elem.find("rdepend")
    bdepend_elem = version_elem.find("bdepend")
    pdepend_elem = version_elem.find("pdepend")
    idepend_elem = version_elem.find("idepend")
    required_use_elem = version_elem.find("required_use")

    return PackageVersion(
        id=version_elem.get("id", ""),
        eapi=version_elem.get("EAPI"),
        repository=version_elem.get("repository"),
        virtual=version_elem.get("virtual") == "1",
        installed=version_elem.get("installed") == "1",
        src_uri=version_elem.get("srcURI"),
        iuse=iuse,
        iuse_default=iuse_default,
        required_use=required_use_elem.text if required_use_elem is not None else None,
        depend=depend_elem.text if depend_elem is not None else None,
        rdepend=rdepend_elem.text if rdepend_elem is not None else None,
        bdepend=bdepend_elem.text if bdepend_elem is not None else None,
        pdepend=pdepend_elem.text if pdepend_elem is not None else None,
        idepend=idepend_elem.text if idepend_elem is not None else None,
        masks=masks,
        unmasks=unmasks,
        properties=properties,
        restricts=restricts,
        use_enabled=use_enabled,
        use_disabled=use_disabled
    )


def _parse_package(package_elem: ET.Element, category: str) -> Package:
    """Parse a package element from eix XML."""
    name: str = package_elem.get("name", "")

    desc_elem = package_elem.find("description")
    homepage_elem = package_elem.find("homepage")
    licenses_elem = package_elem.find("licenses")

    # Parse licenses
    licenses: list[str] = []
    if licenses_elem is not None and licenses_elem.text:
        licenses = licenses_elem.text.split()

    # Parse versions
    versions: list[PackageVersion] = []
    for version_elem in package_elem.findall("version"):
        versions.append(_parse_version(version_elem))

    return Package(
        category=category,
        name=name,
        description=desc_elem.text if desc_elem is not None else None,
        homepage=homepage_elem.text if homepage_elem is not None else None,
        licenses=licenses,
        versions=versions
    )


def _fetch_packages_by_query(query: str) -> list[Package]:
    """
    Fetch packages from eix using a search query.

    Tries with remote cache first (-R flag), falls back to local only if it fails.

    Args:
        query: Search query string

    Returns:
        List of matching Package objects

    Raises:
        subprocess.CalledProcessError: If eix command fails with both attempts
        ET.ParseError: If XML parsing fails
    """
    # Try with remote cache first
    result: CompletedProcess[str] = subprocess.run(
        ["eix", "-RQ", "--xml", query],
        capture_output=True,
        text=True
    )

    # If remote cache fails (exit code 1), try without -R
    if result.returncode == 1:
        result = subprocess.run(
            ["eix", "-Q", "--xml", query],
            capture_output=True,
            text=True,
            check=True
        )
    elif result.returncode != 0:
        # Other error, raise it
        result.check_returncode()

    root: Element = ET.fromstring(result.stdout)
    packages: list[Package] = []

    for category_elem in root.findall("category"):
        category_name: str = category_elem.get("name", "")

        for package_elem in category_elem.findall("package"):
            pkg: Package = _parse_package(package_elem, category_name)
            packages.append(pkg)

    return packages


def search_packages(query: str) -> list[Package]:
    """
    Search for packages using direct eix queries.

    Args:
        query: Search query string

    Returns:
        List of matching packages
    """
    if not query.strip():
        return []

    try:
        packages: list[Package] = _fetch_packages_by_query(query)
        return packages
    except (subprocess.CalledProcessError, ET.ParseError) as e:
        # Return empty list on error rather than crashing
        return []


def get_package_by_atom(atom: str) -> Package | None:
    """
    Get a specific package by its full atom.

    Args:
        atom: Package atom (e.g., "app-editors/vim")

    Returns:
        Package object if found, None otherwise
    """
    try:
        packages: list[Package] = _fetch_packages_by_query(atom)
        # Look for exact match
        for pkg in packages:
            if pkg.full_name == atom:
                return pkg
        return None
    except (subprocess.CalledProcessError, ET.ParseError):
        return None


def get_installed_packages() -> list[Package]:
    """
    Get all installed packages.

    Returns:
        List of installed Package objects
    """
    try:
        # Use eix's installed filter
        packages: list[Package] = _fetch_packages_by_query("--installed")
        return packages
    except (subprocess.CalledProcessError, ET.ParseError):
        return []