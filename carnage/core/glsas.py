"""Utilities for managing Gentoo Linux Security Advisories (GLSAs)."""

import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
from xml.etree.ElementTree import Element


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
    bug: str | None
    access: str | None
    background: str | None
    description: str
    impact: str
    impact_type: str
    workaround: str | None
    resolution: str
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
        root: Element | Any = tree.getroot()

        title_elem = root.find("title")
        synopsis_elem = root.find("synopsis")
        product_elem = root.find("product")
        announced_elem = root.find("announced")
        revised_elem = root.find("revised")
        bug_elem = root.find("bug")
        access_elem = root.find("access")
        background_elem = root.find("background/p")
        description_elem = root.find("description/p")
        impact_elem = root.find("impact/p")
        impact_type_elem = root.find("impact")
        workaround_elem = root.find("workaround/p")
        resolution_elem = root.find("resolution/p")

        # Parse references
        references: list[Any] = []
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
            bug=bug_elem.text if bug_elem is not None else None,
            access=access_elem.text if access_elem is not None else None,
            background=background_elem.text.strip() if background_elem is not None and background_elem.text else None,
            description=description_elem.text.strip() if description_elem is not None and description_elem.text else "",
            impact=impact_elem.text.strip() if impact_elem is not None and impact_elem.text else "",
            impact_type=impact_type_elem.get("type", "normal") if impact_type_elem is not None else "normal",
            workaround=workaround_elem.text.strip() if workaround_elem is not None and workaround_elem.text else None,
            resolution=resolution_elem.text.strip() if resolution_elem is not None and resolution_elem.text else "",
            references=references
        )
    except (ET.ParseError, OSError):
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

    glsas: list[Any] = []
    for glsa_code in glsa_codes.split():
        glsa_file: Path = glsa_metadata_dir / f"glsa-{glsa_code}.xml"

        if not glsa_file.exists():
            continue

        glsa: GLSA | None = _parse_glsa_xml(glsa_code, glsa_file)
        if glsa is not None:
            glsas.append(glsa)

    return glsas