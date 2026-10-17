"""Tests for grounding eix installed flags in the live vardb."""

from __future__ import annotations

import pytest

import carnage.core.eix.search as search_module
from carnage.core.eix.search import Package, PackageVersion, _correct_installed_repos


def _version(version_id: str, repository: str | None, installed: bool, virtual: bool = False) -> PackageVersion:
    return PackageVersion(
        id=version_id,
        eapi="8",
        repository=repository,
        virtual=virtual,
        installed=installed,
        install_date=None,
        install_eapi=None,
        src_uri=None,
        iuse=[],
        iuse_default=[],
        required_use=None,
        depend=None,
        rdepend=None,
        bdepend=None,
        pdepend=None,
        idepend=None,
        masks=[],
        unmasks=[],
        properties=[],
        restricts=[],
        use_enabled=[],
        use_disabled=[],
    )


def _package(versions: list[PackageVersion]) -> Package:
    return Package(
        category="media-libs",
        name="mesa",
        description="d",
        homepage=None,
        licenses=[],
        versions=versions,
    )


class _FakeVardb:
    """Minimal vardb double: installed CPVs mapped to their repo."""

    def __init__(self, repos: dict[str, str]) -> None:
        self._repos = repos

    def cp_list(self, full_name: str) -> list[str]:
        return [f"{full_name}-{version}" for version in self._repos] if full_name == "media-libs/mesa" else []

    def aux_get(self, cpv: str, keys: list[str]) -> list[str]:
        version = cpv.rsplit("-", 1)[1]
        return [self._repos[version]]


def _patch_vardb(monkeypatch: pytest.MonkeyPatch, repos: dict[str, str]) -> None:
    monkeypatch.setattr(search_module, "_vardb", lambda: _FakeVardb(repos))


def test_wrong_remote_repo_is_corrected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mesa case: remote says inode64-overlay, vardb says gentoo."""
    pkg = _package([_version("26.2.4", "inode64-overlay", installed=True, virtual=True)])
    _patch_vardb(monkeypatch, {"26.2.4": "gentoo"})

    _correct_installed_repos([pkg])

    (version,) = pkg.versions
    assert version.repository == "gentoo"
    assert version.virtual is False
    assert version.installed is True


def test_stale_installed_flag_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """eix claims installed, vardb knows nothing of the package."""
    pkg = _package([_version("1.0", "gentoo", installed=True)])
    _patch_vardb(monkeypatch, {})

    _correct_installed_repos([pkg])

    assert pkg.versions[0].installed is False


def test_stale_version_flag_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Package installed, but not at the version eix flagged."""
    pkg = _package(
        [
            _version("1.0", "gentoo", installed=True),
            _version("2.0", "gentoo", installed=False),
        ]
    )
    _patch_vardb(monkeypatch, {"2.0": "gentoo"})

    _correct_installed_repos([pkg])

    assert pkg.versions[0].installed is False
    assert pkg.versions[1].installed is False


def test_uninstalled_packages_are_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    """No installed flags: vardb is never consulted."""
    pkg = _package([_version("1.0", None, installed=False)])

    def _boom() -> object:
        raise AssertionError("vardb must not be consulted")

    monkeypatch.setattr(search_module, "_vardb", _boom)

    _correct_installed_repos([pkg])

    assert pkg.versions[0].repository is None
    assert pkg.versions[0].installed is False


def test_vardb_failure_leaves_eix_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any portage error keeps the eix data rather than failing."""
    pkg = _package([_version("1.0", "guru", installed=True)])

    def _boom() -> object:
        raise RuntimeError("portage exploded")

    monkeypatch.setattr(search_module, "_vardb", _boom)

    _correct_installed_repos([pkg])

    assert pkg.versions[0].installed is True
    assert pkg.versions[0].repository == "guru"
