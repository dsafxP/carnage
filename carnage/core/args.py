__all__: list[str] = [
    "config_path",
    "show_help",
]

import argparse
import sys
from pathlib import Path
from typing import *

try:
    from .. import __version__
except ImportError:
    # Fallback if not installed as package
    __version__ = "dev"

class __ArgsInit:
    def __init__(self):
        self.args = self._parse_args()

    @staticmethod
    def _parse_args() -> argparse.Namespace:
        parser = argparse.ArgumentParser(
            add_help=False,
            formatter_class=argparse.RawDescriptionHelpFormatter
        )

        # add_argument alias for cleaner code
        add_arg = parser.add_argument

        # Help argument
        add_arg(
            "-h", "--help",
            action="store_true",
            default=False,
            help="Show this help message and exit"
        )

        # Version argument (placeholder)
        add_arg(
            "-V", "--version",
            action="store_true",
            default=False,
            help="Show version information and exit"
        )

        # Config file path
        add_arg(
            "-c", "--config",
            type=Path,
            default=None,
            help="Path to configuration file",
            metavar="FILE"
        )

        return parser.parse_args()

    def get_element(self, element: str) -> Any:
        """Returns the value of a command line argument"""
        return getattr(self.args, element, None)


# Initialize argument parser
__args = __ArgsInit()

# Public
config_path: Optional[Path] = __args.get_element("config")
show_help: bool = __args.get_element("help")
show_version: bool = __args.get_element("version")

# Handle help and version flags
if show_help:
    print("Usage: carnage [OPTIONS]")
    print("\nOptions:")
    print("  -h, --help          Show this help message and exit")
    print("  -V, --version       Show version information and exit")
    print("  -c, --config FILE   Path to configuration file")
    sys.exit(0)

if show_version:
    print(__version__)
    sys.exit(0)