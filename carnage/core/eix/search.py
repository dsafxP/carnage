"""Package search functionality using direct eix queries."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from subprocess import CompletedProcess
from typing import TYPE_CHECKING, Any

from lxml import etree

from carnage.core.commands_config import CommandsConfiguration, get_commands_config, is_valid_component
from carnage.core.eix.eix import has_remote_cache
from carnage.core.process import tracked_run

if TYPE_CHECKING:
    from carnage.core.gentoolkit.package import GentoolkitPackage


@lru_cache(maxsize=1024)
def _gentoolkit_package(cpv_str: str) -> GentoolkitPackage:
    """
    Build a gentoolkit Package once per CPV string.

    Every to_gentoolkit() call used to construct a fresh instance, so the
    exists_f/available cached_property never survived the call and the same
    portage query ran again on every row selection. Masking answers can go
    stale mid-session, but installs flip the version's own installed flag
    (from fresh eix data), which is what the views key off.
    """
    from gentoolkit.cpv import CPV

    from carnage.core.gentoolkit.package import GentoolkitPackage

    return GentoolkitPackage(CPV(cpv_str))


@dataclass
class PackageVersion:
    """Represents a specific version of a package."""

    id: str
    eapi: str | None
    repository: str | None
    virtual: bool
    installed: bool
    install_date: int | None
    install_eapi: str | None
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
        return _gentoolkit_package(cpv_str)

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

        return _gentoolkit_package(cpv_str)

    def is_in_world_file(self) -> bool:
        """
        Check if package is in world file.

        Returns:
            True if package is in world file, False otherwise
        """
        try:
            result: CompletedProcess[str] = tracked_run(["eix", "--selected-file", "-0Qq", self.full_name], text=True)
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
            result: CompletedProcess[str] = tracked_run(["eix", "--installed-deps", "-0Qq", self.full_name], text=True)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False


def _parse_version(version_elem: etree._Element) -> PackageVersion:
    """Parse a version element from eix XML."""
    # Parse IUSE flags
    iuse: list[str] = []
    iuse_default: list[str] = []

    for iuse_elem in version_elem.findall("iuse"):
        is_default = iuse_elem.get("default") == "1"
        flags = iuse_elem.text.split() if iuse_elem.text else []
        for flag in flags:
            iuse.append(flag)
            if is_default:
                iuse_default.append(flag)

    # Parse masks and unmasks
    masks = version_elem.xpath("mask/@type")
    unmasks = version_elem.xpath("unmask/@type")

    # Parse properties
    properties = version_elem.xpath("properties/@flag")

    # Parse restricts
    restricts = version_elem.xpath("restrict/@flag")

    # Parse use flags
    use_enabled_elem = next(
        (use_elem for use_elem in version_elem.findall("use") if use_elem.get("enabled") == "1"), None
    )
    use_disabled_elem = next(
        (use_elem for use_elem in version_elem.findall("use") if use_elem.get("enabled") == "0"), None
    )

    use_enabled = use_enabled_elem.text.split() if use_enabled_elem is not None and use_enabled_elem.text else []
    use_disabled = use_disabled_elem.text.split() if use_disabled_elem is not None and use_disabled_elem.text else []

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
        # None means eix did not report one (local queries omit overlay
        # info): unknown, not gentoo. Display layers fall back to "gentoo".
        repository=version_elem.get("repository"),
        virtual=version_elem.get("virtual") == "1",
        installed=version_elem.get("installed") == "1",
        install_date=int(d) if (d := version_elem.get("installDate")) is not None else None,
        install_eapi=version_elem.get("installEAPI"),
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


def _parse_package(package_elem: etree._Element, category: str) -> Package | None:
    """
    Parse a package element from eix XML.

    Returns:
        The package, or None when category/name cannot safely be used as a
        command argument.
    """
    name = package_elem.get("name", "")

    # category/name become package atoms handed to privileged commands, so skip
    # anything getopt could read as an option rather than as a package.
    if not is_valid_component(category) or not is_valid_component(name):
        return None

    desc_elem = package_elem.find("description")
    homepage_elem = package_elem.find("homepage")
    licenses_elem = package_elem.find("licenses")

    # Parse licenses. eix hands over the raw LICENSE expression, operators
    # included ("|| ( Ruby-BSD BSD-2 )"), so keep only the license names.
    licenses: list[str] = []
    if licenses_elem is not None and licenses_elem.text:
        seen_licenses: set[str] = set()
        for token in licenses_elem.text.split():
            name_token = token.strip("()")
            if not name_token or name_token == "||" or name_token in seen_licenses:
                continue
            seen_licenses.add(name_token)
            licenses.append(name_token)

    # Parse versions
    versions: list[PackageVersion] = [_parse_version(version_elem) for version_elem in package_elem.findall("version")]

    return Package(
        category=category,
        name=name,
        description=desc_elem.text if desc_elem is not None else None,
        homepage=homepage_elem.text if homepage_elem is not None else None,
        licenses=licenses,
        versions=versions,
    )


def _vardb() -> Any:
    """Live installed-packages database (tiny seam so tests can fake it)."""
    import portage

    return portage.db[portage.root]["vartree"].dbapi  # type: ignore


def _correct_installed_repos(packages: list[Package]) -> None:
    """
    Ground eix installed flags in the live vardb.

    Remote eix data can attribute an installed version to the wrong overlay
    (stale cache) or mark it virtual. Vardb knows which repo each installed
    version really came from, so trust it: fix the repo, clear the virtual
    flag, and drop installed flags vardb no longer knows. Never fails a
    search: any portage error leaves the eix data untouched.
    """
    flagged: list[Package] = [p for p in packages if any(v.installed for v in p.versions)]

    if not flagged:
        return

    try:
        from portage.versions import cpv_getversion

        from carnage.core.gentoolkit import portage_lock

        with portage_lock:
            vardb = _vardb()

            for pkg in flagged:
                try:
                    installed_cpvs: list[str] = vardb.cp_list(pkg.full_name)
                except Exception:
                    continue

                if not installed_cpvs:
                    for v in pkg.versions:
                        v.installed = False
                    continue

                repo_by_version: dict[str, str] = {}

                for cpv in installed_cpvs:
                    try:
                        version = cpv_getversion(cpv)
                        if version is None:
                            continue
                        repo_by_version[version] = vardb.aux_get(cpv, ["repository"])[0]
                    except Exception:
                        continue

                for v in pkg.versions:
                    if not v.installed:
                        continue

                    if v.id not in repo_by_version:
                        v.installed = False
                    else:
                        if repo_by_version[v.id]:
                            v.repository = repo_by_version[v.id]
                        v.virtual = False
    except Exception:
        pass


def fetch_packages_by_query(query: list[str], append_cfg: bool = True) -> list[Package]:
    """
    Fetch packages from eix using search query arguments.

    Uses remote cache if available, falls back to local only.

    Args:
        query: List of search query arguments
        append_cfg: Append arguments from configuration

    Returns:
        List of matching Package objects, or an empty list when eix produced
        nothing usable (no matches, a broken cache, or non-XML output)
    """
    # Build base command based on remote cache availability
    if has_remote_cache():
        cmd: list[str] = ["eix", "-R", "--xml"]
    else:
        cmd = ["eix", "--xml"]

    if append_cfg:
        cmd_config: CommandsConfiguration = get_commands_config()

        # Append search flags from configuration
        cmd.extend(cmd_config.eix_search_flags)

    # Append the search query arguments
    cmd.extend(query)

    result: CompletedProcess[bytes] = tracked_run(cmd)

    # eix exits 1 when nothing matches, and prints diagnostics rather than XML
    # when the cache is broken. Neither is an error for us - and recovering from
    # non-XML used to leave root as None, which then crashed on the xpath below.
    # Bytes go straight to lxml: decoding to str first only to re-encode here
    # copied a multi-megabyte document twice per query.
    if not result.stdout.strip():
        return []

    parser = etree.XMLParser(recover=True, remove_comments=True)
    root = etree.fromstring(result.stdout, parser=parser)

    if root is None:
        return []

    packages: list[Package] = []

    category_elems = root.xpath("//category")
    for category_elem in category_elems:
        category_name = category_elem.get("name", "")

        # Get all packages in this category
        package_elems = category_elem.xpath("package")
        for package_elem in package_elems:
            pkg: Package | None = _parse_package(package_elem, category_name)
            if pkg is not None:
                packages.append(pkg)

    _correct_installed_repos(packages)

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
    except (subprocess.SubprocessError, etree.ParseError, OSError):
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
    except (subprocess.SubprocessError, etree.ParseError, OSError):
        return None
