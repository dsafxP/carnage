"""Configuration management for Carnage using TOML."""

from pathlib import Path
from typing import Any, Dict, List
import tomllib


class Configuration:
    """Manages Carnage configuration with TOML files."""

    def __init__(self, config_path: Path | None = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config file. Defaults to ~/.config/carnage.toml
        """
        if config_path is None:
            config_path = Path.home() / ".config" / "carnage.toml"

        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._load_config()



    def _create_default_config(self) -> None:
        """Create default configuration file with comments."""
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write default config with comments
        config_content = """# Carnage configuration file
# This file uses TOML format. Edit values as needed.

[global]
# User interface theme
# Preferred to be set directly through Carnage
theme = "textual-dark"

# Privilege escalation backend for administrative commands
# Options: auto, pkexec, sudo, doas, none
privilege_backend = "auto"

[browse]
# Default flags for package search with eix
# These are passed to eix commands
search_flags = ["-f", "2"]

# Minimum characters required before starting search
# Lower values may hinder performance
minimum_characters = 3

[overlays]
# Ignore warnings within overlays
ignore_warnings = false

# Skip counting packages in overlays (faster but less informative)
# When false, package counts will be fetched but may take longer
skip_package_counting = false

# Maximum age for overlay cache in hours
# Overlay data will be refreshed after this time
cache_max_age = 72

[use]
# Minimum characters required before starting USE flag search
# Lower values may hinder performance
minimum_characters = 3

# Maximum age for USE flag cache in hours
# USE flag data will be refreshed after this time
cache_max_age = 96"""

        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(config_content)

    def _load_config(self) -> None:
        """Load configuration from file or create default."""
        if not self.config_path.exists():
            self._create_default_config()

        try:
            with open(self.config_path, "rb") as f:
                self._config = tomllib.load(f)
        except (tomllib.TOMLDecodeError, OSError):
            # Fall back to defaults if config is corrupted
            self._config = self._get_default_config()

    def _get_nested_value(self, keys: List[str], default: Any = None) -> Any:
        """Get a nested value from the configuration."""
        current = self._config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    @staticmethod
    def _get_default_config() -> Dict[str, Any]:
        """Get the default configuration."""
        return {
            "global": {
                "theme": "textual-dark",
                "privilege_backend": "auto"
            },
            "browse": {
                "search_flags": ["-f", "2"],
                "minimum_characters": 3
            },
            "overlays": {
                "ignore_warnings": False,
                "skip_package_counting": False,
                "cache_max_age": 72
            },
            "use": {
                "minimum_characters": 3,
                "cache_max_age": 96
            }
        }

    # Global settings
    @property
    def theme(self) -> str:
        """Get the theme setting."""
        return self._get_nested_value(["global", "theme"], "textual-dark")

    @property
    def privilege_backend(self) -> str:
        """Get the privilege escalation backend setting."""
        return self._get_nested_value(["global", "privilege_backend"], "auto")

    # Browse settings
    @property
    def search_flags(self) -> List[str]:
        """Get the search flags for package browsing."""
        return self._get_nested_value(["browse", "search_flags"], ["-f", "2"])

    @property
    def browse_minimum_characters(self) -> int:
        """Get the minimum characters for browse search."""
        return self._get_nested_value(["browse", "minimum_characters"], 3)

    # Overlay settings
    @property
    def ignore_warnings(self) -> bool:
        """Get whether to ignore overlay warnings."""
        return self._get_nested_value(["overlays", "ignore_warnings"], False)

    @property
    def skip_package_counting(self) -> bool:
        """Get whether to skip package counting for overlays."""
        return self._get_nested_value(["overlays", "skip_package_counting"], False)

    @property
    def overlays_cache_max_age(self) -> int:
        """Get the cache max age for overlays in hours."""
        return self._get_nested_value(["overlays", "cache_max_age"], 72)

    # Use flag settings
    @property
    def use_minimum_characters(self) -> int:
        """Get the minimum characters for USE flag search."""
        return self._get_nested_value(["use", "minimum_characters"], 3)

    @property
    def use_cache_max_age(self) -> int:
        """Get the cache max age for USE flags in hours."""
        return self._get_nested_value(["use", "cache_max_age"], 96)

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
        _config_instance = Configuration(config_path)

    return _config_instance