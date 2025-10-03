"""Package search functionality using eix with in-memory database."""

import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from subprocess import CompletedProcess
from typing import Callable
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


class PackageDatabase:
    """In-memory package database for fast searching."""

    def __init__(self):
        """Initialize empty package database."""
        self.packages: list[Package] = []
        self._by_name: dict[str, list[Package]] = {}
        self._by_category: dict[str, list[Package]] = {}
        self._loaded: bool = False

    def load(self) -> None:
        """Load all packages from eix into memory."""
        if self._loaded:
            return

        self.packages = _fetch_all_packages()
        self._build_indices()
        self._loaded = True

    def _build_indices(self) -> None:
        """Build search indices for faster lookups."""
        self._by_name.clear()
        self._by_category.clear()

        for pkg in self.packages:
            # Index by package name
            if pkg.name not in self._by_name:
                self._by_name[pkg.name] = []
            self._by_name[pkg.name].append(pkg)

            # Index by category
            if pkg.category not in self._by_category:
                self._by_category[pkg.category] = []
            self._by_category[pkg.category].append(pkg)

    def search(
            self,
            query: str,
            case_sensitive: bool = False,
            search_description: bool = True
    ) -> list[Package]:
        """
        Search for packages by name or description.

        Args:
            query: Search query string
            case_sensitive: Whether to perform case-sensitive search
            search_description: Whether to search in descriptions

        Returns:
            List of matching packages
        """
        if not self._loaded:
            self.load()

        if not case_sensitive:
            query = query.lower()

        results: list[Package] = []

        for pkg in self.packages:
            name: str = pkg.name if case_sensitive else pkg.name.lower()
            full_name: str = pkg.full_name if case_sensitive else pkg.full_name.lower()

            # Search in name
            if query in name or query in full_name:
                results.append(pkg)
                continue

            # Search in description
            if search_description and pkg.description:
                desc: str = pkg.description if case_sensitive else pkg.description.lower()
                if query in desc:
                    results.append(pkg)

        return results

    def filter(
            self,
            predicate: Callable[[Package], bool]
    ) -> list[Package]:
        """
        Filter packages using a custom predicate function.

        Args:
            predicate: Function that returns True for packages to include

        Returns:
            List of packages matching the predicate
        """
        if not self._loaded:
            self.load()

        return [pkg for pkg in self.packages if predicate(pkg)]

    def get_by_category(self, category: str) -> list[Package]:
        """Get all packages in a specific category."""
        if not self._loaded:
            self.load()

        return self._by_category.get(category, [])

    def get_by_name(self, name: str) -> list[Package]:
        """Get all packages with a specific name (may be in different categories)."""
        if not self._loaded:
            self.load()

        return self._by_name.get(name, [])

    def get_installed(self) -> list[Package]:
        """Get all installed packages."""
        return self.filter(lambda pkg: pkg.is_installed())

    def categories(self) -> list[str]:
        """Get list of all categories."""
        if not self._loaded:
            self.load()

        return sorted(self._by_category.keys())


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


def _fetch_all_packages() -> list[Package]:
    """
    Fetch all packages from eix.

    Tries with remote cache first (-R flag), falls back to local only if it fails.

    Returns:
        List of all Package objects

    Raises:
        subprocess.CalledProcessError: If eix command fails with both attempts
        ET.ParseError: If XML parsing fails
    """
    # Try with remote cache first
    result: CompletedProcess[str] = subprocess.run(
        ["eix", "-RQ", "--xml"],
        capture_output=True,
        text=True
    )

    # If remote cache fails (exit code 1), try without -R
    if result.returncode == 1:
        result = subprocess.run(
            ["eix", "-Q", "--xml"],
            capture_output=True,
            text=True,
            check=True
        )
    elif result.returncode != 0:
        # Other error, raise it
        result.check_returncode()

    root = ET.fromstring(result.stdout)
    packages: list[Package] = []

    for category_elem in root.findall("category"):
        category_name: str = category_elem.get("name", "")

        for package_elem in category_elem.findall("package"):
            pkg: Package = _parse_package(package_elem, category_name)
            packages.append(pkg)

    return packages


def search_packages(
        query: str,
        case_sensitive: bool = False,
        search_description: bool = True
) -> list[Package]:
    """
    Search for packages without loading full database into memory.

    This is a lightweight alternative for low-spec systems.
    Note: Currently loads full database. Will be optimized later.

    Args:
        query: Search query string
        case_sensitive: Whether to perform case-sensitive search
        search_description: Whether to search in descriptions

    Returns:
        List of matching packages
    """
    # For now, use the database
    # TODO: Implement direct eix search without loading everything
    db = PackageDatabase()
    db.load()
    return db.search(query, case_sensitive, search_description)