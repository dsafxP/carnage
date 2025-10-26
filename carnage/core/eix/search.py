"""Package search functionality using direct eix queries."""

import subprocess
from dataclasses import dataclass, field
from subprocess import CompletedProcess
from typing import List
from . import has_remote_cache
from lxml import etree


@dataclass
class PackageVersion:
    """Represents a specific version of a package."""
    id: str
    eapi: str | None
    repository: str | None
    virtual: bool
    installed: bool
    src_uri: str | None
    iuse: List[str]
    iuse_default: List[str]
    required_use: str | None
    depend: str | None
    rdepend: str | None
    bdepend: str | None
    pdepend: str | None
    idepend: str | None
    masks: List[str]
    unmasks: List[str]
    properties: List[str]
    restricts: List[str]
    use_enabled: List[str]
    use_disabled: List[str]


@dataclass
class Package:
    """Represents a Gentoo package with all its versions."""
    category: str
    name: str
    description: str | None
    homepage: str | None
    licenses: List[str]
    versions: List[PackageVersion] = field(default_factory=list)

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


def _parse_version(version_elem: etree._Element) -> PackageVersion:
    """Parse a version element from eix XML."""
    # Parse IUSE flags
    iuse_elems = version_elem.xpath("iuse")
    iuse: List[str] = []
    iuse_default: List[str] = []

    for iuse_elem in iuse_elems:
        flags = iuse_elem.text.split() if iuse_elem.text else []
        for flag in flags:
            iuse.append(flag)
            if iuse_elem.get("default") == "1":
                iuse_default.append(flag)

    # Parse masks and unmasks
    masks = version_elem.xpath("mask/@type")
    unmasks = version_elem.xpath("unmask/@type")

    # Parse properties
    properties = version_elem.xpath("properties/@flag")

    # Parse restricts
    restricts = version_elem.xpath("restrict/@flag")

    # Parse use flags
    use_enabled_elems = version_elem.xpath('use[@enabled="1"]')
    use_disabled_elems = version_elem.xpath('use[@enabled="0"]')

    use_enabled = use_enabled_elems[0].text.split() if use_enabled_elems and use_enabled_elems[0].text else []
    use_disabled = use_disabled_elems[0].text.split() if use_disabled_elems and use_disabled_elems[0].text else []

    # Get depend fields
    depend_elem = version_elem.xpath("depend")[0] if version_elem.xpath("depend") else None
    rdepend_elem = version_elem.xpath("rdepend")[0] if version_elem.xpath("rdepend") else None
    bdepend_elem = version_elem.xpath("bdepend")[0] if version_elem.xpath("bdepend") else None
    pdepend_elem = version_elem.xpath("pdepend")[0] if version_elem.xpath("pdepend") else None
    idepend_elem = version_elem.xpath("idepend")[0] if version_elem.xpath("idepend") else None
    required_use_elem = version_elem.xpath("required_use")[0] if version_elem.xpath("required_use") else None

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


def _parse_package(package_elem: etree._Element, category: str) -> Package:
    """Parse a package element from eix XML."""
    name = package_elem.get("name", "")

    desc_elem = package_elem.xpath("description")[0] if package_elem.xpath("description") else None
    homepage_elem = package_elem.xpath("homepage")[0] if package_elem.xpath("homepage") else None
    licenses_elem = package_elem.xpath("licenses")[0] if package_elem.xpath("licenses") else None

    # Parse licenses
    licenses: List[str] = []
    if licenses_elem is not None and licenses_elem.text:
        licenses = licenses_elem.text.split()

    # Parse versions
    version_elems = package_elem.xpath("version")
    versions: list[PackageVersion] = [_parse_version(version_elem) for version_elem in version_elems]

    return Package(
        category=category,
        name=name,
        description=desc_elem.text if desc_elem is not None else None,
        homepage=homepage_elem.text if homepage_elem is not None else None,
        licenses=licenses,
        versions=versions
    )


def _fetch_packages_by_query(query: str) -> List[Package]:
    """
    Fetch packages from eix using a search query.

    Uses remote cache if available, falls back to local only.

    Args:
        query: Search query string

    Returns:
        List of matching Package objects

    Raises:
        subprocess.CalledProcessError: If eix command fails
        etree.ParseError: If XML parsing fails
    """
    # Build command based on remote cache availability
    if has_remote_cache():
        cmd: list[str] = ["eix", "-RQ", "--xml", query]
    else:
        cmd = ["eix", "-Q", "--xml", query]

    result: CompletedProcess[str] = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True
    )

    parser = etree.XMLParser(recover=True, remove_comments=True)
    root = etree.fromstring(result.stdout.encode('utf-8'), parser=parser)

    packages: List[Package] = []

    category_elems = root.xpath("//category")
    for category_elem in category_elems:
        category_name = category_elem.get("name", "")

        # Get all packages in this category
        package_elems = category_elem.xpath("package")
        for package_elem in package_elems:
            pkg: Package = _parse_package(package_elem, category_name)
            packages.append(pkg)

    return packages


def search_packages(query: str) -> List[Package]:
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
        packages: List[Package] = _fetch_packages_by_query(query)
        return packages
    except (subprocess.CalledProcessError, etree.ParseError):
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
        packages: List[Package] = _fetch_packages_by_query(atom)
        # Look for exact match
        for pkg in packages:
            if pkg.full_name == atom:
                return pkg
        return None
    except (subprocess.CalledProcessError, etree.ParseError):
        return None


def get_installed_packages() -> List[Package]:
    """
    Get all installed packages.

    Returns:
        List of installed Package objects
    """
    try:
        # Use eix's installed filter
        packages: List[Package] = _fetch_packages_by_query("--installed")
        return packages
    except (subprocess.CalledProcessError, etree.ParseError):
        return []


def get_packages_with_useflag(useflag: str) -> List[Package]:
    """
    Get packages that have a specific USE flag.

    Uses remote cache if available, falls back to local only.

    Args:
        useflag: USE flag name to search for

    Returns:
        List of Package objects that have this USE flag
    """
    from lxml import etree

    # Build command based on remote cache availability
    if has_remote_cache():
        cmd: list[str] = ["eix", "-RUQ", "--xml", "--use", useflag]
    else:
        cmd = ["eix", "-UQ", "--xml", "--use", useflag]

    result: CompletedProcess[str] = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return []

    try:
        parser = etree.XMLParser(recover=True, remove_comments=True)
        root = etree.fromstring(result.stdout.encode('utf-8'), parser=parser)
        packages: List[Package] = []

        category_elems = root.xpath("//category")
        for category_elem in category_elems:
            category_name: str = category_elem.get("name", "")

            package_elems = category_elem.xpath("package")
            for package_elem in package_elems:
                pkg: Package = _parse_package(package_elem, category_name)
                packages.append(pkg)

        return packages
    except etree.ParseError:
        return []