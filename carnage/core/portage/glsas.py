"""Utilities for managing Gentoo Linux Security Advisories (GLSAs)."""

from dataclasses import dataclass
from pathlib import Path

from lxml import etree
from portage.glsa import (Glsa, GlsaArgumentException, GlsaFormatException,
                          GlsaTypeException, get_applied_glsas, get_glsa_list)

from carnage.core.portage.portageq import ctx


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


def _parse_affected_packages(root: etree._Element) -> list[AffectedPackage]:
    """Parse affected packages from the XML."""
    packages: list[AffectedPackage] = []

    for package_elem in root.xpath("affected/package"):
        name = package_elem.get("name", "")
        auto = package_elem.get("auto", "yes")
        arch = package_elem.get("arch", "*")

        unaffected_conditions = [
            {
                "range": elem.get("range", ""),
                "slot": elem.get("slot", ""),
                "value": elem.text or ""
            }
            for elem in package_elem.xpath("unaffected")
        ]

        vulnerable_conditions = [
            {
                "range": elem.get("range", ""),
                "slot": elem.get("slot", ""),
                "value": elem.text or ""
            }
            for elem in package_elem.xpath("vulnerable")
        ]

        packages.append(AffectedPackage(
            name=name,
            auto=auto,
            arch=arch,
            unaffected_conditions=unaffected_conditions,
            vulnerable_conditions=vulnerable_conditions,
        ))

    return packages


def _clean_code_indentation(code: str) -> str:
    """Remove excessive indentation from code blocks."""
    lines = code.split("\n")
    min_indent: int | None = None
    for line in lines:
        if line.strip():
            indent = len(line) - len(line.lstrip())
            if min_indent is None or indent < min_indent:
                min_indent = indent

    if min_indent:
        lines = [line[min_indent:] if line.strip() else line for line in lines]

    return "\n".join(lines)


def _parse_resolutions(root: etree._Element) -> list[Resolution]:
    """Parse resolution sections with text and optional code blocks."""
    resolutions: list[Resolution] = []
    resolution_elems = root.xpath("resolution")

    if not resolution_elems:
        return resolutions

    current_text = ""
    current_code = ""

    for elem in resolution_elems[0].iter():
        if elem.tag == "p":
            if current_text.strip() or current_code.strip():
                resolutions.append(Resolution(
                    text=current_text.strip(),
                    code=_clean_code_indentation(current_code) if current_code else None,
                ))
                current_text = ""
                current_code = ""
            if elem.text:
                current_text = elem.text.strip()

        elif elem.tag == "code":
            if elem.text:
                current_code += elem.text

        if elem.tail and elem.tail.strip():
            current_text = (current_text + " " + elem.tail.strip()).strip()

    if current_text.strip() or current_code.strip():
        resolutions.append(Resolution(
            text=current_text.strip(),
            code=_clean_code_indentation(current_code) if current_code else None,
        ))

    return resolutions


def _parse_glsa_xml(glsa_id: str, xml_path: Path) -> GLSA | None:
    """Parse a GLSA XML file into a GLSA dataclass."""
    try:
        parser = etree.XMLParser(recover=True, remove_comments=True)
        root = etree.parse(xml_path, parser=parser).getroot()

        revised_elem = root.xpath("revised")
        impact_type_elem = root.xpath("impact")

        references: list[str] = []
        for uri_elem in root.xpath("references/uri"):
            link = uri_elem.get("link")
            if link:
                references.append(link)
            elif uri_elem.text:
                references.append(uri_elem.text)

        return GLSA(
            id=glsa_id,
            title=root.xpath("string(title)") or None,
            synopsis=root.xpath("string(synopsis)").strip(),
            product=root.xpath("string(product)") or None,
            announced=root.xpath("string(announced)") or None,
            revised=root.xpath("string(revised)") or None,
            revision_count=revised_elem[0].get("count", "01") if revised_elem else "01",
            bugs=root.xpath("bug/text()"),
            access=root.xpath("string(access)") or None,
            background=root.xpath("string(background/p)").strip() or None,
            description=root.xpath("string(description/p)").strip(),
            impact=root.xpath("string(impact/p)").strip(),
            impact_type=impact_type_elem[0].get("type", "normal") if impact_type_elem else "normal",
            workaround=root.xpath("string(workaround/p)").strip() or None,
            resolutions=_parse_resolutions(root),
            affected_packages=_parse_affected_packages(root),
            references=references,
        )
    except (etree.ParseError, etree.XMLSyntaxError, OSError) as e:
        print(f"Error parsing GLSA {glsa_id}: {e}")
        return None


def _is_vulnerable(glsa_id: str) -> bool:
    """Check whether this GLSA affects the current system via the portage API."""
    try:
        glsa = Glsa(glsa_id, ctx.settings, ctx.vardbapi, ctx.portdbapi)
        return glsa.isVulnerable()
    except (GlsaArgumentException, GlsaFormatException, GlsaTypeException):
        return False


def fetch_glsas() -> list[GLSA]:
    """
    Fetch all GLSAs affecting the system with their full metadata.

    Vulnerability checking uses the portage API directly. Metadata is parsed
    from the GLSA XML files with lxml for full structured detail.

    Returns:
        List of GLSA objects for all GLSAs affecting the system.
    """
    glsa_metadata_dir: Path = ctx.gentoo_repo_path / "metadata" / "glsa"
    applied = set(get_applied_glsas(ctx.settings))
    glsas: list[GLSA] = []

    for glsa_id in get_glsa_list(ctx.settings):
        if glsa_id in applied:
            continue
        if not _is_vulnerable(glsa_id):
            continue

        xml_path = glsa_metadata_dir / f"glsa-{glsa_id}.xml"
        if not xml_path.exists():
            continue

        glsa = _parse_glsa_xml(glsa_id, xml_path)
        if glsa is not None:
            glsas.append(glsa)

    return glsas


def fix_glsas() -> tuple[int, str, str]:
    """
    Fix all GLSAs affecting the system.

    Wraps: glsa-check -f <glsa_ids>

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    from carnage.core import run_privileged

    applied = set(get_applied_glsas(ctx.settings))
    vulnerable_ids: list[str] = []

    for glsa_id in get_glsa_list(ctx.settings):
        if glsa_id in applied:
            continue
        if _is_vulnerable(glsa_id):
            vulnerable_ids.append(glsa_id)

    if not vulnerable_ids:
        return 0, "No GLSAs affecting the system.", ""

    return run_privileged(["glsa-check", "-f"] + vulnerable_ids)