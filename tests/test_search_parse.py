"""Tests for eix XML parsing."""

from __future__ import annotations

from lxml import etree

from carnage.core.eix.search import _parse_package

XML = """<eix>
  <category name="app-editors">
    <package name="vim">
      <description>Vi IMproved</description>
      <homepage>https://example.invalid</homepage>
      <licenses>vim</licenses>
      <version id="9.0.0" EAPI="8" repository="gentoo" virtual="0" installed="1" installDate="1700000000">
        <iuse default="1">gui python</iuse>
        <iuse>perl</iuse>
        <mask type="package"/>
        <properties flag="live"/>
        <restrict flag="test"/>
        <use enabled="1">gui</use>
        <use enabled="0">perl</use>
        <depend>sys-libs/ncurses</depend>
        <depend>sys-libs/ignored-duplicate</depend>
        <rdepend>sys-libs/ncurses</rdepend>
        <required_use>gui? ( python )</required_use>
      </version>
    </package>
    <package name="-evil"/>
  </category>
</eix>
"""


def test_parse_package_reads_every_field_once() -> None:
    root = etree.fromstring(XML.encode())
    categories = root.xpath("//category")

    packages = [
        package
        for category in categories
        for package in [_parse_package(element, category.get("name", "")) for element in category.xpath("package")]
        if package is not None
    ]

    assert [package.full_name for package in packages] == ["app-editors/vim"]

    (version,) = packages[0].versions
    assert version.id == "9.0.0"
    assert version.installed is True
    assert version.install_date == 1700000000
    assert version.iuse == ["gui", "python", "perl"]
    assert version.iuse_default == ["gui", "python"]
    assert version.masks == ["package"]
    assert version.properties == ["live"]
    assert version.restricts == ["test"]
    assert version.use_enabled == ["gui"]
    assert version.use_disabled == ["perl"]
    # The first of a doubled field wins, matching the old xpath [0] lookup.
    assert version.depend == "sys-libs/ncurses"
    assert version.rdepend == "sys-libs/ncurses"
    assert version.bdepend is None
    assert version.required_use == "gui? ( python )"
    assert packages[0].description == "Vi IMproved"
    assert packages[0].homepage == "https://example.invalid"
    assert packages[0].licenses == ["vim"]
