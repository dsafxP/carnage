"""Tests for configuration loading and persistence (``carnage.core.config``)."""

from __future__ import annotations

from pathlib import Path

from carnage.core.config import Configuration


def test_fresh_install_generates_and_reads_back_defaults(config_file: Path) -> None:
    config = Configuration(config_path=config_file)

    assert config_file.exists()
    assert config._toml_doc is not None
    assert config._validate_config_structure()
    assert config.theme == "textual-dark"
    assert config.automatic_pane is True


def test_first_save_keeps_the_generated_defaults(config_file: Path) -> None:
    """The first setter used to truncate the file it had just generated."""
    config = Configuration(config_path=config_file)

    config.compact_mode = True

    reloaded = Configuration(config_path=config_file)

    assert reloaded.compact_mode is True
    assert reloaded.theme == "textual-dark"
    assert reloaded.automatic_pane is True


def test_settings_survive_multiple_reloads(config_file: Path) -> None:
    config = Configuration(config_path=config_file)
    config.theme = "solarized-dark"

    assert Configuration(config_path=config_file).theme == "solarized-dark"

    Configuration(config_path=config_file).compact_mode = True

    reloaded = Configuration(config_path=config_file)
    assert reloaded.theme == "solarized-dark"
    assert reloaded.compact_mode is True


def test_corrupted_config_is_migrated_with_a_backup(config_file: Path) -> None:
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("this is not [ valid toml", encoding="utf-8")

    config = Configuration(config_path=config_file)

    assert config._validate_config_structure()
    assert config.theme == "textual-dark"
    assert list(config_file.parent.glob("*.old"))
