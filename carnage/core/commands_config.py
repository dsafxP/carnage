"""Command overrides configuration for Carnage using TOML."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.exceptions import TOMLKitError

from carnage.core.args import config_path as arg_cfg_path


@dataclass
class Command:
    """Represents a fully built command."""

    full_cmd: list[str] = field(default_factory=list)
    raw_cmd: list[str] = field(default_factory=list)
    cmd: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    privilege: bool | None = None
    is_overridden: bool = False


class CommandsConfiguration:
    """Manages Carnage command overrides using TOML files."""

    # Default configuration as a string
    DEFAULT_CONFIG = """# Carnage command overrides
# This file is optional and completely user-managed
# It can be risky to override entire commands as Carnage might not be suited to work with unexpected results
# Missing values are ignored - the app will use internal defaults

# Privilege escalation backend for administrative commands
privilege_backend = []

# [eix.search]
# Default flags for package search with eix
# command = ["-Qf", "3"]

# [eix.update]
# command = ["eix-update", "-v"]

# [eix.remote-update]
# command = ["eix-remote", "update"]

# [emerge.sync]
# command = ["emerge", "--sync"]
# privilege = true

# [emerge.install]
# command = ["emerge", "-v", "--nospinner", "$1"]
# privilege = true

# [emerge.noreplace]
# command = ["emerge", "-vn", "--nospinner", "$1"]
# privilege = true

# [emerge.uninstall]
# command = ["emerge", "-vc", "--nospinner", "$1"]
# privilege = true
# environment = { CLEAN_DELAY = "0" }

# [emerge.deselect]
# command = ["emerge", "-W", "$1"]
# privilege = true

# [euse.enable]
# command = ["euse", "-p", "$1", "-E", "$2"]
# privilege = true

# [euse.disable]
# command = ["euse", "-p", "$1", "-D", "$2"]
# privilege = true

# [eclean.dist]
# command = ["eclean-dist"]
# privilege = true

# [eclean.pkg]
# command = ["eclean-pkg"]
# privilege = true

# [glsa.fix]
# command = ["glsa-check", "-vf", "$1"]
# privilege = true

# [news.read]
# command = ["eselect", "news", "read", "--quiet", "$1"]

# [news.purge]
# command = ["eselect", "news", "purge"]

# [overlays.add]
# Carnage expects for the repository to be enabled and synchronized in a single call
# command = ["sh", "-c", "eselect repository enable $1 && emaint sync -r $1"]
# privilege = true

# [overlays.sync]
# command = ["emaint", "sync", "-r", "$1"]
# privilege = true

# [overlays.remove]
# command = ["eselect", "repository", "remove", "$1"]
# privilege = true
"""

    # Internal default commands for fallback
    _DEFAULT_COMMANDS: dict[str, dict[str, Any]] = {
        "eix.search": {
            "command": ["-Qf", "3"],
        },
        "eix.update": {
            "command": ["eix-update", "-v"],
        },
        "eix.remote-update": {
            "command": ["eix-remote", "update"],
        },
        "emerge.sync": {
            "command": ["emerge", "--sync"],
        },
        "emerge.install": {
            "command": ["emerge", "-v", "--nospinner", "$1"],
        },
        "emerge.noreplace": {
            "command": ["emerge", "-vn", "--nospinner", "$1"],
        },
        "emerge.uninstall": {
            "command": ["emerge", "-vc", "--nospinner", "$1"],
            "environment": {"CLEAN_DELAY": "0"},
        },
        "emerge.deselect": {
            "command": ["emerge", "-W", "$1"],
        },
        "euse.enable": {
            "command": ["euse", "-p", "$1", "-E", "$2"],
        },
        "euse.disable": {
            "command": ["euse", "-p", "$1", "-D", "$2"],
        },
        "eclean.dist": {
            "command": ["eclean-dist"],
        },
        "eclean.pkg": {
            "command": ["eclean-pkg"],
        },
        "glsa.fix": {
            "command": ["glsa-check", "-vf", "$1"],
        },
        "news.read": {
            "command": ["eselect", "news", "read", "--quiet", "$1"],
        },
        "news.purge": {
            "command": ["eselect", "news", "purge"],
        },
        "overlays.add": {
            "command": ["sh", "-c", "eselect repository enable $1 && emaint sync -r $1"],
        },
        "overlays.sync": {
            "command": ["emaint", "sync", "-r", "$1"],
        },
        "overlays.remove": {
            "command": ["eselect", "repository", "remove", "$1"],
        },
    }

    def __init__(self, config_path: Path | None = None):
        """
        Initialize command configuration.

        Args:
            config_path: Path to commands.toml file.
                        Defaults to ~/.config/carnage/commands.toml
        """
        if config_path is None:
            from platformdirs import user_config_dir

            config_path = Path(user_config_dir("carnage")) / "commands.toml"

        self.config_path = config_path
        self._config: dict[str, Any] = {}
        self._toml_doc: TOMLDocument | None = None
        self._load_config()

    def _create_default_config(self) -> None:
        """Create default command configuration file."""
        from carnage.core.operation import generate_default_privilege_backend

        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        content = self.DEFAULT_CONFIG

        detected_backend = generate_default_privilege_backend()

        if detected_backend:
            privilege_line = f'privilege_backend = ["{detected_backend}"]'

            content = content.replace("privilege_backend = []", privilege_line)

        # Ensure double quotes by replacing any single quotes from repr
        # (though our f-string already uses double quotes)
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _load_config(self) -> None:
        """Load configuration from file or create default."""
        if not self.config_path.exists():
            self._create_default_config()
            self._config = {}
            self._toml_doc = None
            return

        try:
            with open(self.config_path, encoding="utf-8") as f:
                content = f.read()
                self._toml_doc = tomlkit.parse(content)
                self._config = self._toml_doc.unwrap()
        except (TOMLKitError, OSError):
            self._config = {}
            self._toml_doc = None

    def _get_nested_value(self, keys: list[str], default: Any = None) -> Any:
        """Get a nested value from the configuration."""
        current = self._config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def _substitute_args(self, cmd: list[str], args: list[str]) -> list[str]:
        """Substitute $1, $2, etc. with actual arguments."""
        result = []
        for part in cmd:
            substituted = part
            for i, arg in enumerate(args, 1):
                substituted = substituted.replace(f"${i}", arg)
            result.append(substituted)
        return result

    @property
    def privilege_backend(self) -> list[str]:
        """Get the privilege escalation backend setting."""
        return self._get_nested_value(["privilege_backend"], ["pkexec"])

    @property
    def eix_search_flags(self) -> list[str]:
        """Get eix search flags from command override."""
        cmd_config = self._get_nested_value(["eix", "search"])

        if cmd_config:
            raw_cmd = cmd_config.get("command")

            if raw_cmd:
                return raw_cmd

        return self._DEFAULT_COMMANDS["eix.search"]["command"]

    def get_command(
        self,
        command_path: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        default_privilege: bool = False,
    ) -> Command:
        """
        Get a fully built command configuration.

        Args:
            command_path: Dot notation path (e.g., "emerge.install", "news.read")
            args: Arguments to substitute for $1, $2, etc.
            env: Additional environment variables to merge
            default_privilege: Internal default privilege if not overridden

        Returns:
            Command object with fully built command (always returns a Command)
        """
        args = args or []
        env = env or {}

        keys = command_path.split(".")

        # Try to get from config first
        table = self._get_nested_value(keys)

        # If not in config, use default
        if not table or not isinstance(table, dict):
            default_config = self._DEFAULT_COMMANDS.get(command_path)
            if default_config:
                table = default_config
                is_overridden = False
            else:
                # Fallback to empty command
                return Command(is_overridden=False)
        else:
            is_overridden = True

        # Get raw command
        raw_cmd = table.get("command", [])
        if not isinstance(raw_cmd, list):
            raw_cmd = []

        # Get privilege override
        privilege = table.get("privilege")
        if privilege is not None and not isinstance(privilege, bool):
            privilege = None

        # Get environment from config
        config_env = table.get("environment", {})
        if not isinstance(config_env, dict):
            config_env = {}

        # Merge environments (config takes precedence)
        merged_env = {**env, **config_env}

        # Build command with args substituted (no privilege/env yet)
        cmd_with_args = self._substitute_args(raw_cmd, args)

        # Determine if we need privilege
        use_privilege = privilege if privilege is not None else default_privilege

        # Build full command with privilege and env
        full_cmd = list(cmd_with_args)

        if merged_env:
            env_args = []
            for k, v in merged_env.items():
                env_args.extend([f"{k}={v}"])
            full_cmd = ["env", *env_args, *full_cmd]

        if use_privilege and self.privilege_backend:
            full_cmd = [*self.privilege_backend, *full_cmd]

        return Command(
            full_cmd=full_cmd,
            raw_cmd=raw_cmd,
            cmd=cmd_with_args,
            env=merged_env,
            privilege=privilege,
            is_overridden=is_overridden,
        )

    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()


# Global command configuration instance
_commands_instance: CommandsConfiguration | None = None


def get_commands_config(config_path: Path | None = None) -> CommandsConfiguration:
    """
    Get the global command configuration instance.

    Args:
        config_path: Optional path to commands.toml file

    Returns:
        CommandsConfiguration instance
    """
    global _commands_instance

    if _commands_instance is None:
        if arg_cfg_path:
            config_path = arg_cfg_path.parent / "commands.toml"
        _commands_instance = CommandsConfiguration(config_path)

    return _commands_instance
