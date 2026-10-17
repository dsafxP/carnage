"""Tests for the repo-pinned portage queries."""

from __future__ import annotations

import pytest

import carnage.core.gentoolkit.package as package_module
from carnage.core.gentoolkit.package import find_ebuild, installed_use, repo_available, repo_iuse


class _FakePortdb:
    """Portage tree double with one visible gentoo version."""

    def xmatch(self, kind: str, atom: str) -> list[str]:
        assert kind == "match-visible"
        if atom == "=media-libs/mesa-26.2.4::gentoo":
            return ["media-libs/mesa-26.2.4"]
        return []

    def findname2(self, cpv: str, myrepo: str | None = None) -> tuple[str | None, object]:
        if cpv == "media-libs/mesa-26.2.4" and myrepo == "gentoo":
            return ("/var/db/repos/gentoo/media-libs/mesa/mesa-26.2.4.ebuild", None)
        return (None, 0)

    def aux_get(self, cpv: str, keys: list[str], myrepo: str | None = None) -> list[str]:
        assert keys == ["IUSE"]
        if cpv == "media-libs/mesa-26.2.4" and myrepo == "gentoo":
            return ["vulkan wayland +opengl"]
        raise KeyError(cpv)


class _FakeVardb:
    def aux_get(self, cpv: str, keys: list[str]) -> list[str]:
        assert keys == ["USE"]
        if cpv == "media-libs/mesa-26.2.4":
            return ["vulkan wayland"]
        raise KeyError(cpv)


@pytest.fixture(autouse=True)
def fake_databases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(package_module, "_portdb", lambda: _FakePortdb())
    monkeypatch.setattr(package_module, "_vardb", lambda: _FakeVardb())


def test_repo_available_pins_the_overlay() -> None:
    assert repo_available("media-libs/mesa-26.2.4", "gentoo") is True
    assert repo_available("media-libs/mesa-26.2.4", "inode64-overlay") is False


def test_repo_available_bare_atom_keeps_best_visible() -> None:
    assert repo_available("media-libs/mesa-26.2.4", None) is False


def test_find_ebuild_pins_the_overlay() -> None:
    assert find_ebuild("media-libs/mesa-26.2.4", "gentoo") == (
        "/var/db/repos/gentoo/media-libs/mesa/mesa-26.2.4.ebuild"
    )
    assert find_ebuild("media-libs/mesa-26.2.4", "inode64-overlay") is None


def test_repo_iuse_strips_signs() -> None:
    assert repo_iuse("media-libs/mesa-26.2.4", "gentoo") == ["vulkan", "wayland", "opengl"]
    assert repo_iuse("media-libs/mesa-26.2.4", "inode64-overlay") is None


def test_installed_use_reads_vardb() -> None:
    assert installed_use("media-libs/mesa-26.2.4") == {"vulkan", "wayland"}
    assert installed_use("media-libs/mesa-9999") is None
