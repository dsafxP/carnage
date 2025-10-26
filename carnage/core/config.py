"""Configuration management for Carnage using TOML."""

from pathlib import Path
from typing import Any, Dict, List

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.exceptions import TOMLKitError
from tomlkit.items import Table


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
        self._toml_doc: TOMLDocument | None = None
        self._load_config()
    
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
    
    def _create_default_config(self) -> None:
        """Create default configuration file with comments."""
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create TOML document with comments
        doc: TOMLDocument = tomlkit.document()
        
        # Add header comment
        doc.add(tomlkit.comment("Carnage configuration file"))
        doc.add(tomlkit.nl())
        
        # Global section
        global_section: Table = tomlkit.table()
        global_section.add(tomlkit.comment("User interface theme"))
        global_section.add(tomlkit.comment("Preferred to be set directly through Carnage"))
        global_section.add("theme", "textual-dark")
        global_section.add(tomlkit.nl())
        global_section.add(tomlkit.comment("Privilege escalation backend for administrative commands"))
        global_section.add(tomlkit.comment("Options: auto, pkexec, sudo, doas, none"))
        global_section.add("privilege_backend", "auto")
        doc.add("global", global_section)
        
        # Browse section
        browse_section = tomlkit.table()
        browse_section.add(tomlkit.comment("Default flags for package search with eix"))
        browse_section.add(tomlkit.comment("These are passed to eix commands"))
        browse_section.add("search_flags", tomlkit.array('["-f", "2"]'))
        browse_section.add(tomlkit.nl())
        browse_section.add(tomlkit.comment("Minimum characters required before starting search"))
        browse_section.add(tomlkit.comment("Lower values may hinder performance"))
        browse_section.add("minimum_characters", 3)
        doc.add("browse", browse_section)
        
        # Overlays section
        overlays_section: Table = tomlkit.table()
        overlays_section.add(tomlkit.comment("Ignore warnings within overlays"))
        overlays_section.add("ignore_warnings", False)
        overlays_section.add(tomlkit.nl())
        overlays_section.add(tomlkit.comment("Skip counting packages in overlays (faster but less informative)"))
        overlays_section.add(tomlkit.comment("When false, package counts will be fetched but may take longer"))
        overlays_section.add("skip_package_counting", False)
        overlays_section.add(tomlkit.nl())
        overlays_section.add(tomlkit.comment("Maximum age for overlay cache in hours"))
        overlays_section.add(tomlkit.comment("Overlay data will be refreshed after this time"))
        overlays_section.add("cache_max_age", 72)
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
        
        # Write to file
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))

    
    def _load_config(self) -> None:
        """Load configuration from file or create default."""
        if not self.config_path.exists():
            self._create_default_config()
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._toml_doc = tomlkit.parse(f.read())
                # Convert to plain dict for easy access
                self._config = self._toml_doc.unwrap()
        except (TOMLKitError, OSError, ImportError):
            # Fall back to defaults if config is corrupted
            self._config = self._get_default_config()
    
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
    
    def _get_nested_value(self, keys: List[str], default: Any = None) -> Any:
        """Get a nested value from the configuration."""
        current = self._config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
    
    def _set_nested_value(self, keys: List[str], value: Any) -> None:
        """Set a nested value in the configuration."""
        current = self._config
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
    
    # Global settings
    @property
    def theme(self) -> str:
        """Get the theme setting."""
        return self._get_nested_value(["global", "theme"], "textual-dark")
    
    @theme.setter
    def theme(self, value: str) -> None:
        """Set the theme setting."""
        self._set_nested_value(["global", "theme"], value)

        if self._toml_doc:
            self._toml_doc["global"]["theme"] = self.theme # type: ignore

        self._save_config()
    
    @property
    def privilege_backend(self) -> str:
        """Get the privilege escalation backend setting."""
        return self._get_nested_value(["global", "privilege_backend"], "auto")
    
    @property
    def search_flags(self) -> List[str]:
        """Get the search flags for package browsing."""
        return self._get_nested_value(["browse", "search_flags"], ["-f", "2"])
    
    @property
    def browse_minimum_characters(self) -> int:
        """Get the minimum characters for browse search."""
        return self._get_nested_value(["browse", "minimum_characters"], 3)
    
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