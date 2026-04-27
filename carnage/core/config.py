"""Configuration management for Carnage using TOML."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Final

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.exceptions import TOMLKitError
from tomlkit.items import Table

from carnage.core.args import config_path as arg_cfg_path

# Default configuration as a constant
_DEFAULT_CONFIG: Final[dict[str, Any]] = {
    "global": {
        "theme": "textual-dark",
        "compact_mode": False,
        "ignore_warnings": False,
    },
    "browse": {
        "minimum_characters": 3,
        "syntax_style": "github-dark",
        "expand": True,
        "depth": 1,
    },
    "overlays": {
        "skip_package_counting": True,
        "cache_max_age": 72,
        "overlay_source": "https://api.gentoo.org/overlays/repositories.xml",
    },
    "use": {
        "minimum_characters": 3,
        "cache_max_age": 96,
    },
    "logging": {
        "automatic_pane": True,
    },
}


class Configuration:
    """Manages Carnage configuration with TOML files."""

    def __init__(self, config_path: Path | None = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config file. Defaults to ~/.config/carnage/carnage.toml
        """
        if config_path is None:
            from platformdirs import user_config_dir

            config_path = Path(user_config_dir("carnage")) / "carnage.toml"

        self.config_path = config_path
        self._config: dict[str, Any] = {}
        self._toml_doc: TOMLDocument | None = None
        self._load_config()

    def _backup_config(self) -> None:
        """Backup current config file with .old prefix and timestamp."""
        if not self.config_path.exists():
            return

        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path: Path = self.config_path.parent / f"{self.config_path.name}.{timestamp}.old"

        shutil.copy2(self.config_path, backup_path)

    def _migrate_config(self) -> None:
        """
        Migrate configuration by backing up old and creating new default.
        """
        # Backup existing config
        self._backup_config()

        # Create fresh default configuration
        self._create_default_config()

        # Reload the new configuration
        self._load_config()

    def _validate_config_structure(self) -> bool:
        """
        Validate that all expected sections and options are present.

        Returns:
            True if config is valid, False if migration is needed
        """
        # Check if all main sections exist
        for section in _DEFAULT_CONFIG.keys():
            if section not in self._config:
                return False

        # Check if all expected options exist in each section
        for section, options in _DEFAULT_CONFIG.items():
            if section not in self._config:
                return False

            for option in options.keys():
                if option not in self._config[section]:
                    return False

        return True

    def _create_default_config(self) -> None:
        """Create default configuration file with comments."""
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create TOML document with comments
        doc: TOMLDocument = tomlkit.document()

        # Add header comment
        doc.add(tomlkit.comment("Carnage configuration file"))
        doc.add(tomlkit.comment("This file was automatically generated"))
        doc.add(tomlkit.nl())

        # Global section
        global_section: Table = tomlkit.table()
        global_section.add(tomlkit.comment("User interface theme"))
        global_section.add(tomlkit.comment("Preferred to be set directly through Carnage"))
        global_section.add("theme", "textual-dark")
        global_section.add(tomlkit.nl())
        global_section.add(tomlkit.comment("Compact mode reduces visual noise and increases content density"))
        global_section.add(tomlkit.comment("Preferred to be set directly through Carnage"))
        global_section.add("compact_mode", False)
        global_section.add(tomlkit.nl())
        global_section.add(tomlkit.comment("Ignore all warnings"))
        global_section.add("ignore_warnings", False)
        global_section.add(tomlkit.nl())
        doc.add("global", global_section)

        # Browse section
        browse_section: Table = tomlkit.table()
        browse_section.add(tomlkit.comment("Minimum characters required before starting search"))
        browse_section.add(tomlkit.comment("Lower values may hinder performance"))
        browse_section.add("minimum_characters", 3)
        browse_section.add(tomlkit.nl())
        browse_section.add(tomlkit.comment("Pygments style to use for ebuild syntax highlighting"))
        browse_section.add(tomlkit.comment("Find a list at: https://pygments.org/styles"))
        browse_section.add("syntax_style", "github-dark")
        browse_section.add(tomlkit.nl())
        browse_section.add(tomlkit.comment("Expand all tree nodes automatically in dependencies or installed files"))
        browse_section.add("expand", True)
        browse_section.add(tomlkit.nl())
        browse_section.add(tomlkit.comment("Dependency tree depth limit"))
        browse_section.add("depth", 1)
        doc.add("browse", browse_section)

        # Overlays section
        overlays_section: Table = tomlkit.table()
        overlays_section.add(tomlkit.comment("Skip counting packages in overlays (faster but less informative)"))
        overlays_section.add(tomlkit.comment("When false, package counts will be fetched but may take longer"))
        overlays_section.add("skip_package_counting", True)
        overlays_section.add(tomlkit.nl())
        overlays_section.add(tomlkit.comment("Maximum age for overlay cache in hours"))
        overlays_section.add(tomlkit.comment("Overlay data will be refreshed after this time"))
        overlays_section.add("cache_max_age", 72)
        overlays_section.add(tomlkit.nl())
        overlays_section.add(tomlkit.comment("URL to fetch overlay metadata from"))
        overlays_section.add(tomlkit.comment("Change this only if you need to use a different overlay list source"))
        overlays_section.add("overlay_source", "https://api.gentoo.org/overlays/repositories.xml")
        doc.add("overlays", overlays_section)

        # Use section
        use_section: Table = tomlkit.table()
        use_section.add(tomlkit.comment("Minimum characters required before starting USE flag search"))
        use_section.add(tomlkit.comment("Lower values may hinder performance"))
        use_section.add("minimum_characters", 3)
        use_section.add(tomlkit.nl())
        use_section.add(tomlkit.comment("Maximum age for USE flag cache in hours"))
        use_section.add(tomlkit.comment("USE flag data will be refreshed after this time"))
        use_section.add("cache_max_age", 96)
        doc.add("use", use_section)

        # Logging section
        logging_section: Table = tomlkit.table()
        logging_section.add(tomlkit.comment("Automatically open the logging output pane when executing a command"))
        logging_section.add("automatic_pane", True)
        doc.add("logging", logging_section)

        # Write to file
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))

    def _load_config(self) -> None:
        """Load configuration from file or create default."""
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.config_path.exists():
            self._create_default_config()
            return

        try:
            with open(self.config_path, encoding="utf-8") as f:
                self._toml_doc = tomlkit.parse(f.read())
                # Convert to plain dict for easy access
                self._config = self._toml_doc.unwrap()

            # Validate configuration structure
            if not self._validate_config_structure():
                self._migrate_config()

        except (TOMLKitError, OSError, ImportError):
            # Migrate if config is corrupted or unreadable
            self._migrate_config()

    def _save_config(self) -> None:
        """Save current configuration to file preserving comments."""
        if self._toml_doc is None:
            # Create new document if we don't have one
            self._toml_doc = tomlkit.document()

        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write back to file
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(self._toml_doc))

    def _get_nested_value(self, keys: list[str], default: Any = None) -> Any:
        """Get a nested value from the configuration."""
        current = self._config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def _set_nested_value(self, keys: list[str], value: Any) -> None:
        """Set a nested value in the configuration."""
        current = self._config
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    def _set_nested_value_and_save(self, keys: list[str], value: Any) -> None:
        """Set a nested value, sync to the TOML document, and save."""
        self._set_nested_value(keys, value)

        if self._toml_doc:
            current = self._toml_doc
            for key in keys[:-1]:  # type: ignore
                if key not in current:  # type: ignore
                    current[key] = {}  # type: ignore
                current = current[key]  # type: ignore
            current[keys[-1]] = value  # type: ignore

        self._save_config()

    # Global settings
    @property
    def theme(self) -> str:
        """Get the theme setting."""
        return self._get_nested_value(["global", "theme"], _DEFAULT_CONFIG["global"]["theme"])

    @theme.setter
    def theme(self, value: str) -> None:
        """Set the theme setting."""
        self._set_nested_value_and_save(["global", "theme"], value)

    @property
    def compact_mode(self) -> bool:
        """Get the compact mode setting."""
        return self._get_nested_value(["global", "compact_mode"], _DEFAULT_CONFIG["global"]["compact_mode"])

    @compact_mode.setter
    def compact_mode(self, value: bool) -> None:
        """Set the compact mode setting."""
        self._set_nested_value_and_save(["global", "compact_mode"], value)

    @property
    def ignore_warnings(self) -> bool:
        """Get whether to ignore warnings system-wide."""
        return self._get_nested_value(["global", "ignore_warnings"], _DEFAULT_CONFIG["global"]["ignore_warnings"])

    @property
    def browse_minimum_characters(self) -> int:
        """Get the minimum characters for browse search."""
        return self._get_nested_value(["browse", "minimum_characters"], _DEFAULT_CONFIG["browse"]["minimum_characters"])

    @property
    def syntax_style(self) -> str:
        """Get the syntax highlighting style."""
        return self._get_nested_value(["browse", "syntax_style"], _DEFAULT_CONFIG["browse"]["syntax_style"])

    @property
    def expand(self) -> bool:
        """Get whether to expand nodes or not."""
        return self._get_nested_value(["browse", "expand"], _DEFAULT_CONFIG["browse"]["expand"])

    @property
    def depth(self) -> int:
        """Get dependency tree's maximum depth."""
        return self._get_nested_value(["browse", "depth"], _DEFAULT_CONFIG["browse"]["depth"])

    @property
    def skip_package_counting(self) -> bool:
        """Get whether to skip package counting for overlays."""
        return self._get_nested_value(
            ["overlays", "skip_package_counting"], _DEFAULT_CONFIG["overlays"]["skip_package_counting"]
        )

    @property
    def overlays_cache_max_age(self) -> int:
        """Get the cache max age for overlays in hours."""
        return self._get_nested_value(["overlays", "cache_max_age"], _DEFAULT_CONFIG["overlays"]["cache_max_age"])

    @property
    def overlay_source(self) -> str:
        """Get the overlay metadata source URL."""
        return self._get_nested_value(["overlays", "overlay_source"], _DEFAULT_CONFIG["overlays"]["overlay_source"])

    @property
    def use_minimum_characters(self) -> int:
        """Get the minimum characters for USE flag search."""
        return self._get_nested_value(["use", "minimum_characters"], _DEFAULT_CONFIG["use"]["minimum_characters"])

    @property
    def use_cache_max_age(self) -> int:
        """Get the cache max age for USE flags in hours."""
        return self._get_nested_value(["use", "cache_max_age"], _DEFAULT_CONFIG["use"]["cache_max_age"])

    @property
    def automatic_pane(self) -> bool:
        """Get whether to automatically open the logging pane."""
        return self._get_nested_value(["logging", "automatic_pane"], _DEFAULT_CONFIG["logging"]["automatic_pane"])

    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by dot notation.

        Args:
            key: Dot notation key (e.g., "global.theme")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys: list[str] = key.split(".")
        return self._get_nested_value(keys, default)


# Global configuration instance
_config_instance: Configuration | None = None


def get_config(config_path: Path | None = None) -> Configuration:
    """
    Get the global configuration instance.

    Args:
        config_path: Optional path to config file

    Returns:
        Configuration instance
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = Configuration(arg_cfg_path or config_path)

    return _config_instance
