"""Utilities for managing Gentoo Linux Security Advisories (GLSAs)."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess

from lxml import etree

from carnage.core.portageq import get_gentoo_repo_path


@dataclass
class AffectedPackage:
    """Represents an affected package in a GLSA."""
    name: str
    auto: str
    arch: str
    unaffected_conditions: list[dict]
    vulnerable_conditions: list[dict]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"AffectedPackage(name={self.name!r})"


@dataclass
class Resolution:
    """Represents a resolution step with text and optional code."""
    text: str
    code: str | None = None

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"Resolution(text={self.text!r}, code={self.code!r})"


@dataclass
class GLSA:
    """Represents a Gentoo Linux Security Advisory."""
    id: str
    title: str | None
    synopsis: str
    product: str | None
    announced: str | None
    revised: str | None
    revision_count: str
    bugs: list[str]
    access: str | None
    background: str | None
    description: str
    impact: str
    impact_type: str
    workaround: str | None
    resolutions: list[Resolution]
    affected_packages: list[AffectedPackage]
    references: list[str]

    def __str__(self) -> str:
        return f"{self.id}: {self.title}"

    def __repr__(self) -> str:
        return f"GLSA(id={self.id!r}, title={self.title!r})"


def get_affected_glsas() -> tuple[int, str]:
    """
    Get GLSAs that affect the system.

    Wraps: glsa-check -tqn all

    Returns:
        Tuple of (return_code, output_string)
        - return_code 0: No GLSAs affect the system
        - return_code 6: GLSAs affect the system (output contains GLSA codes)
    """
    result: CompletedProcess[str] = subprocess.run(
        ["glsa-check", "-tqn", "all"],
        capture_output=True,
        text=True
    )

    return result.returncode, result.stdout.strip()


def fix_glsas() -> tuple[int, str, str]:
    """
    Fix all GLSAs affecting the system.

    Wraps: glsa-check -f $(glsa-check -t all)

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    from .privilege import run_privileged

    # First get the list of affected GLSAs
    returncode, glsa_list = get_affected_glsas()

    if returncode == 0 or not glsa_list:
        # No GLSAs to fix
        return 0, "No GLSAs affecting the system.", ""

    # Fix the GLSAs
    return run_privileged(["glsa-check", "-f"] + glsa_list.split())


def _parse_affected_packages(root: etree._Element) -> list[AffectedPackage]:
    """Parse affected packages from the XML."""
    packages: list[AffectedPackage] = []

    package_elems = root.xpath("affected/package")
    for package_elem in package_elems:
        name = package_elem.get("name", "")
        auto = package_elem.get("auto", "yes")
        arch = package_elem.get("arch", "*")

        # Parse conditions
        unaffected_elems = package_elem.xpath("unaffected")
        vulnerable_elems = package_elem.xpath("vulnerable")

        unaffected_conditions = []
        vulnerable_conditions = []

        # Parse unaffected conditions
        for unaffected_elem in unaffected_elems:
            condition = {
                "range": unaffected_elem.get("range", ""),
                "slot": unaffected_elem.get("slot", ""),
                "value": unaffected_elem.text or ""
            }
            unaffected_conditions.append(condition)

        # Parse vulnerable conditions
        for vulnerable_elem in vulnerable_elems:
            condition = {
                "range": vulnerable_elem.get("range", ""),
                "slot": vulnerable_elem.get("slot", ""),
                "value": vulnerable_elem.text or ""
            }
            vulnerable_conditions.append(condition)

        package = AffectedPackage(
            name=name,
            auto=auto,
            arch=arch,
            unaffected_conditions=unaffected_conditions,
            vulnerable_conditions=vulnerable_conditions
        )
        packages.append(package)

    return packages


def _parse_resolutions(root: etree._Element) -> list[Resolution]:
    """Parse resolution sections with text and code blocks."""
    resolutions: list[Resolution] = []
    resolution_elems = root.xpath("resolution")

    if not resolution_elems:
        return resolutions

    resolution_elem = resolution_elems[0]
    current_text = ""
    current_code = ""

    # Iterate through all elements in resolution
    for elem in resolution_elem.iter():
        if elem.tag == "p":
            # Save current resolution if we have content
            if current_text.strip() or current_code.strip():
                cleaned_code = _clean_code_indentation(current_code) if current_code else None
                resolutions.append(Resolution(text=current_text.strip(), code=cleaned_code))
                current_text = ""
                current_code = ""

            # Start new text section
            if elem.text:
                current_text = elem.text.strip()

        elif elem.tag == "code":
            # Add code block
            if elem.text:
                current_code += elem.text

        # Handle tail text
        if elem.tail and elem.tail.strip():
            if current_text:
                current_text += " " + elem.tail.strip()
            else:
                current_text = elem.tail.strip()

    # Don't forget the last resolution
    if current_text.strip() or current_code.strip():
        cleaned_code = _clean_code_indentation(current_code) if current_code else None
        resolutions.append(Resolution(text=current_text.strip(), code=cleaned_code))

    return resolutions


def _clean_code_indentation(code: str) -> str:
    """Remove excessive indentation from code blocks."""
    lines: list[str] = code.split('\n')

    # Find the minimum indentation (excluding empty lines)
    min_indent: int | None = None
    for line in lines:
        if line.strip():  # Non-empty line
            indent: int = len(line) - len(line.lstrip())
            if min_indent is None or indent < min_indent:
                min_indent = indent

    # Remove the minimum indentation from all lines
    if min_indent is not None and min_indent > 0:
        cleaned_lines: list[str] = []
        for line in lines:
            if line.strip():
                cleaned_lines.append(line[min_indent:])
            else:
                cleaned_lines.append(line)
        return '\n'.join(cleaned_lines)

    return code


def _parse_glsa_xml(glsa_id: str, xml_path: Path) -> GLSA | None:
    """
    Parse a GLSA XML file.

    Args:
        glsa_id: GLSA identifier (e.g., "200310-03")
        xml_path: Path to the GLSA XML file

    Returns:
        GLSA object or None if parsing fails
    """
    try:
        parser = etree.XMLParser(recover=True, remove_comments=True)
        tree = etree.parse(xml_path, parser=parser)
        root = tree.getroot()

        title = root.xpath("string(title)")
        synopsis = root.xpath("string(synopsis)")
        product = root.xpath("string(product)")
        announced = root.xpath("string(announced)")
        revised = root.xpath("string(revised)")
        access = root.xpath("string(access)")
        background = root.xpath("string(background/p)")
        description = root.xpath("string(description/p)")
        impact = root.xpath("string(impact/p)")
        workaround = root.xpath("string(workaround/p)")

        # Parse multiple bugs
        bugs = root.xpath("bug/text()")

        # Parse impact type
        impact_type_elem = root.xpath("impact")
        impact_type = impact_type_elem[0].get("type", "normal") if impact_type_elem else "normal"

        # Parse revision count
        revised_elem = root.xpath("revised")
        revision_count = revised_elem[0].get("count", "01") if revised_elem else "01"

        # Parse affected packages
        affected_packages = _parse_affected_packages(root)

        # Parse resolutions
        resolutions = _parse_resolutions(root)

        # Parse references - get both URI text and link attributes
        references: list[str] = []
        uri_elems = root.xpath("references/uri")
        for uri_elem in uri_elems:
            # Prefer link attribute if available, otherwise use text
            link = uri_elem.get("link")
            if link:
                references.append(link)
            elif uri_elem.text:
                references.append(uri_elem.text)

        return GLSA(
            id=glsa_id,
            title=title if title else None,
            synopsis=synopsis.strip(),
            product=product if product else None,
            announced=announced if announced else None,
            revised=revised if revised else None,
            revision_count=revision_count,
            bugs=bugs,
            access=access if access else None,
            background=background.strip() if background else None,
            description=description.strip(),
            impact=impact.strip(),
            impact_type=impact_type,
            workaround=workaround.strip() if workaround else None,
            resolutions=resolutions,
            affected_packages=affected_packages,
            references=references
        )
    except (etree.ParseError, etree.XMLSyntaxError, OSError) as e:
        print(f"Error parsing GLSA {glsa_id}: {e}")
        return None


def fetch_glsas() -> list[GLSA]:
    """
    Fetch all GLSAs affecting the system with their metadata.

    Returns:
        List of GLSA objects for all GLSAs affecting the system.
    """
    glsa_metadata_dir: Path = get_gentoo_repo_path() / "metadata" / "glsa"

    # Get affected GLSAs
    returncode, glsa_codes = get_affected_glsas()

    if returncode == 0 or not glsa_codes:
        # No GLSAs affecting the system
        return []

    glsas: list[GLSA] = []
    for glsa_code in glsa_codes.split():
        glsa_file: Path = glsa_metadata_dir / f"glsa-{glsa_code}.xml"

        if not glsa_file.exists():
            continue

        glsa: GLSA | None = _parse_glsa_xml(glsa_code, glsa_file)
        if glsa is not None:
            glsas.append(glsa)

    return glsas
