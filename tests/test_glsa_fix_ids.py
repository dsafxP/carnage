"""Tests for fixing GLSAs by id without re-scanning."""

from __future__ import annotations

from unittest.mock import Mock

import carnage.core.portage.glsas as glsas_module


def test_empty_id_list_completes_without_starting_anything(monkeypatch) -> None:
    started: list[list[str]] = []
    monkeypatch.setattr(glsas_module, "start_operation", lambda *a, **k: started.append(list(k.get("args", []))))
    on_complete = Mock()

    glsas_module.fix_glsas_by_ids(Mock(), [], on_complete=on_complete)

    on_complete.assert_called_once_with(True)
    assert started == []


def test_ids_are_passed_as_separate_operands(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def record(app, command_id, *, args=None, default_privilege=False, on_complete=None) -> None:
        recorded["command_id"] = command_id
        recorded["args"] = args
        recorded["on_complete"] = on_complete

    monkeypatch.setattr(glsas_module, "start_operation", record)
    on_complete = Mock()

    glsas_module.fix_glsas_by_ids(Mock(), ["GLSA-2024-0001", "GLSA-2024-0002"], on_complete=on_complete)

    assert recorded["command_id"] == "glsa.fix"
    assert recorded["args"] == ["GLSA-2024-0001", "GLSA-2024-0002"]
    assert recorded["on_complete"] is on_complete


def test_fix_glsas_still_scans_first(monkeypatch) -> None:
    """The full re-scan path stays available for callers without a list."""
    seen: list[str] = []
    monkeypatch.setattr(glsas_module, "get_vulnerable_glsas_async", lambda app, cb: seen.append("scanned"))

    glsas_module.fix_glsas(Mock(), on_complete=Mock())

    assert seen == ["scanned"]
