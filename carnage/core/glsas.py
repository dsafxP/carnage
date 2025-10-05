"""Utilities for managing Gentoo Linux Security Advisories (GLSAs)."""

import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from xml.etree.ElementTree import Element


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
    resolutions: list[Resolution]  # Changed from single resolution to list
    affected_packages: list[AffectedPackage]  # Added for affected packages
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


def _parse_affected_packages(root: Element) -> list[AffectedPackage]:
    """Parse affected packages from the XML."""
    packages: list[AffectedPackage] = []

    for package_elem in root.findall("affected/package"):
        name: str = package_elem.get("name", "")
        auto: str = package_elem.get("auto", "yes")
        arch: str = package_elem.get("arch", "*")

        unaffected_conditions = []
        vulnerable_conditions = []

        # Parse unaffected conditions
        for unaffected_elem in package_elem.findall("unaffected"):
            condition: dict[str, str] = {
                "range": unaffected_elem.get("range", ""),
                "slot": unaffected_elem.get("slot", ""),
                "value": unaffected_elem.text or ""
            }
            unaffected_conditions.append(condition)

        # Parse vulnerable conditions
        for vulnerable_elem in package_elem.findall("vulnerable"):
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


def _parse_resolutions(root: Element) -> list[Resolution]:
    """Parse resolution sections with text and code blocks."""
    resolutions: list[Resolution] = []
    resolution_elem = root.find("resolution")

    if resolution_elem is not None:
        current_text = ""
        current_code = ""

        for elem in resolution_elem.iter():
            if elem.tag == "p":
                # If we have accumulated text and possibly code, save the current resolution
                if current_text.strip() or current_code.strip():
                    # Clean up code by removing excessive indentation
                    cleaned_code: str | None = _clean_code_indentation(current_code) if current_code else None
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

            # Handle tail text (text after elements)
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
        tree = ET.parse(xml_path)
        root = tree.getroot()

        title_elem = root.find("title")
        synopsis_elem = root.find("synopsis")
        product_elem = root.find("product")
        announced_elem = root.find("announced")
        revised_elem = root.find("revised")
        access_elem = root.find("access")
        background_elem = root.find("background/p")
        description_elem = root.find("description/p")
        impact_elem = root.find("impact/p")
        impact_type_elem = root.find("impact")
        workaround_elem = root.find("workaround/p")

        # Parse multiple bugs
        bugs: list[str] = []
        for bug_elem in root.findall("bug"):
            if bug_elem.text:
                bugs.append(bug_elem.text)

        # Parse affected packages
        affected_packages: list[AffectedPackage] = _parse_affected_packages(root)

        # Parse resolutions
        resolutions: list[Resolution] = _parse_resolutions(root)

        # Parse references
        references: list[str] = []
        for ref_elem in root.findall("references/uri"):
            if ref_elem.text:
                references.append(ref_elem.text)

        return GLSA(
            id=glsa_id,
            title=title_elem.text if title_elem is not None else "",
            synopsis=synopsis_elem.text.strip() if synopsis_elem is not None and synopsis_elem.text else "",
            product=product_elem.text if product_elem is not None else "",
            announced=announced_elem.text if announced_elem is not None else "",
            revised=revised_elem.text if revised_elem is not None else "",
            revision_count=revised_elem.get("count", "01") if revised_elem is not None else "01",
            bugs=bugs,
            access=access_elem.text if access_elem is not None else None,
            background=background_elem.text.strip() if background_elem is not None and background_elem.text else None,
            description=description_elem.text.strip() if description_elem is not None and description_elem.text else "",
            impact=impact_elem.text.strip() if impact_elem is not None and impact_elem.text else "",
            impact_type=impact_type_elem.get("type", "normal") if impact_type_elem is not None else "normal",
            workaround=workaround_elem.text.strip() if workaround_elem is not None and workaround_elem.text else None,
            resolutions=resolutions,
            affected_packages=affected_packages,
            references=references
        )
    except (ET.ParseError, OSError) as e:
        print(f"Error parsing GLSA {glsa_id}: {e}")
        return None


def fetch_glsas() -> list[GLSA]:
    """
    Fetch all GLSAs affecting the system with their metadata.

    Returns:
        List of GLSA objects for all GLSAs affecting the system.
    """
    gentoo_repo_path = Path("/var/db/repos/gentoo")

    glsa_metadata_dir: Path = gentoo_repo_path / "metadata" / "glsa"

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