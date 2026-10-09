"""Tests for timeout containment in blocking portage queries."""

from __future__ import annotations

from concurrent.futures import Future

import pytest

import carnage.core.gentoolkit.flag as flag_module
import carnage.core.gentoolkit.package as package_module
import carnage.core.portage.glsas as glsas_module
from carnage.core.gentoolkit.flag import get_all_cpv_usef
from carnage.core.gentoolkit.package import GentoolkitPackage


class _StalledExecutor:
    """Executor whose futures never complete."""

    def submit(self, fn, *args, **kwargs) -> Future:  # noqa: ARG002 - the work is deliberately never run
        return Future()


@pytest.fixture(autouse=True)
def stalled_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in (package_module, flag_module, glsas_module):
        monkeypatch.setattr(module, "_executor", _StalledExecutor())
        monkeypatch.setattr(module, "_QUERY_TIMEOUT", 0.01)


def test_package_existence_reports_missing_on_timeout() -> None:
    package = object.__new__(GentoolkitPackage)

    assert package.exists_f is False


def test_package_availability_reports_unavailable_on_timeout() -> None:
    package = object.__new__(GentoolkitPackage)

    assert package.available is False


def test_use_flag_lookup_reports_no_flags_on_timeout() -> None:
    assert get_all_cpv_usef("cat/pkg-1") == ([], [], [], [])


def test_vulnerability_check_reports_not_vulnerable_on_timeout() -> None:
    assert glsas_module._is_vulnerable("GLSA-2024-0001") is False
