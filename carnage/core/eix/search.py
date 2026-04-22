"""Package search functionality using direct eix queries."""

import subprocess
from dataclasses import dataclass, field
from subprocess import CompletedProcess

from gentoolkit.cpv import CPV
from lxml import etree

from carnage.core.commands_config import CommandsConfiguration, get_commands_config
from carnage.core.eix.eix import has_remote_cache
from carnage.core.gentoolkit.package import GentoolkitPackage


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

    def to_gentoolkit(self, category: str, name: str) -> GentoolkitPackage:
        """
        Return a gentoolkit Package for this specific version.

        Args:
            category: Package category (e.g. "app-portage")
            name: Package name (e.g. "carnage")

        Returns:
            GentoolkitPackage for this CPV
        """
        cpv_str: str = f"{category}/{name}-{self.id}"
        return GentoolkitPackage(CPV(cpv_str))

    def all_deps(self) -> list[str]:
        """
        Return a deduplicated flat list of category/name atoms from all
        dep strings (depend, rdepend, bdepend, pdepend, idepend).

        Parses the raw eix dep strings without calling Portage — safe for
        remote-only packages. USE conditionals, version constraints, slot
        specs, and USE flag annotations are all stripped.
        """
        raw_parts: list[str | None] = [
            self.depend,
            self.rdepend,
            self.bdepend,
            self.pdepend,
            self.idepend,
        ]
        combined: str = " ".join(p for p in raw_parts if p)
        return _parse_dep_string(combined)


def _parse_dep_string(raw: str) -> list[str]:
    """
    Parse an eix dep string into a deduplicated list of category/name atoms.

    Strips version operators, USE conditionals, slot specs, USE flag
    annotations, and HTML entities. Returns bare category/name strings.
    """
    import html

    text: str = html.unescape(raw)

    # Drop USE conditional tokens (flag? or !flag?)
    import re

    text = re.sub(r"!?\w[\w.+-]*\?", "", text)

    # Remove grouping parentheses
    text = re.sub(r"[()]", " ", text)

    # Remove blocker operators
    text = re.sub(r"!!?", "", text)

    atoms: list[str] = []
    seen: set[str] = set()

    for token in text.split():
        # Strip leading version operators
        token = re.sub(r"^[><=~!]+", "", token)

        if "/" not in token:
            continue

        # Strip slot and USE flag annotations
        token = re.sub(r"[:\[].*$", "", token)

        parts = token.split("/")
        if len(parts) != 2:
            continue

        category, pkg = parts

        # Strip version suffix (hyphen followed by a digit)
        pkg = re.sub(r"-\d.*$", "", pkg)

        # Validate both parts
        if not re.match(r"^[a-zA-Z0-9_][a-zA-Z0-9_.+-]*$", category):
            continue
        if not re.match(r"^[a-zA-Z0-9_][a-zA-Z0-9_.+-]*$", pkg):
            continue

        atom: str = f"{category}/{pkg}"
        if atom not in seen:
            seen.add(atom)
            atoms.append(atom)

    return atoms


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

    def to_gentoolkit(self) -> GentoolkitPackage:
        """
        Return a gentoolkit Package for this package (no specific version).

        Uses the installed version if available, otherwise the first version.
        Useful for unversioned queries such as checking masks, keywords, or
        fetching metadata that doesn't depend on a specific version.

        Returns:
            GentoolkitPackage for category/name
        """
        cpv_str: str = self.full_name

        return GentoolkitPackage(CPV(cpv_str))

    def is_in_world_file(self) -> bool:
        """
        Check if package is in world file.

        Returns:
            True if package is in world file, False otherwise
        """
        try:
            result: CompletedProcess[str] = subprocess.run(
                ["eix", "--selected-file", "-0Qq", self.full_name], capture_output=True, text=True, check=False
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def is_installed_dependency(self) -> bool:
        """
        Check if package is an installed dependency.

        Returns:
            True if package is an installed dependency, False otherwise
        """
        try:
            result: CompletedProcess[str] = subprocess.run(
                ["eix", "--installed-deps", "-0Qq", self.full_name], capture_output=True, text=True, check=False
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False


def _parse_version(version_elem: etree._Element) -> PackageVersion:
    """Parse a version element from eix XML."""
    # Parse IUSE flags
    iuse_elems = version_elem.xpath("iuse")
    iuse: list[str] = []
    iuse_default: list[str] = []

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
        repository=version_elem.get("repository") or "gentoo",
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
        use_disabled=use_disabled,
    )


def _parse_package(package_elem: etree._Element, category: str) -> Package:
    """Parse a package element from eix XML."""
    name = package_elem.get("name", "")

    desc_elem = package_elem.xpath("description")[0] if package_elem.xpath("description") else None
    homepage_elem = package_elem.xpath("homepage")[0] if package_elem.xpath("homepage") else None
    licenses_elem = package_elem.xpath("licenses")[0] if package_elem.xpath("licenses") else None

    # Parse licenses
    licenses: list[str] = []
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
        versions=versions,
    )


def fetch_packages_by_query(query: list[str], append_cfg: bool = True) -> list[Package]:
    """
    Fetch packages from eix using search query arguments.

    Uses remote cache if available, falls back to local only.

    Args:
        query: List of search query arguments
        append_cfg: Append arguments from configuration

    Returns:
        List of matching Package objects

    Raises:
        subprocess.CalledProcessError: If eix command fails
        etree.ParseError: If XML parsing fails
    """
    # Build base command based on remote cache availability
    if has_remote_cache():
        cmd: list[str] = ["eix", "-RQ", "--xml"]
    else:
        cmd = ["eix", "-Q", "--xml"]

    if append_cfg:
        cmd_config: CommandsConfiguration = get_commands_config()

        # Append search flags from configuration
        cmd.extend(cmd_config.eix_search_flags)

    # Append the search query arguments
    cmd.extend(query)

    result: CompletedProcess[str] = subprocess.run(cmd, capture_output=True, text=True, check=True)

    parser = etree.XMLParser(recover=True, remove_comments=True)
    root = etree.fromstring(result.stdout.encode("utf-8"), parser=parser)

    packages: list[Package] = []

    category_elems = root.xpath("//category")
    for category_elem in category_elems:
        category_name = category_elem.get("name", "")

        # Get all packages in this category
        package_elems = category_elem.xpath("package")
        for package_elem in package_elems:
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
        # Split the query into individual arguments to handle flags properly
        query_args: list[str] = query.split()

        # Check if any arguments are flags (start with - or --)
        has_flags: bool = any(arg.startswith("-") for arg in query_args)

        # Only append config if no flags are present in the query
        append_cfg: bool = not has_flags

        packages: list[Package] = fetch_packages_by_query(query_args, append_cfg=append_cfg)
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
        packages: list[Package] = fetch_packages_by_query([atom])
        # Look for exact match
        for pkg in packages:
            if pkg.full_name == atom:
                return pkg
        return None
    except (subprocess.CalledProcessError, etree.ParseError):
        return None
