import argparse
from pathlib import Path
from typing import *

try:
    from .. import __version__
except ImportError:
    # Fallback if not installed as package
    __version__ = "dev"

__all__: list[str] = [
    "config_path",
]

class __ArgsInit:
    def __init__(self):
        self.args = self._parse_args()

    @staticmethod
    def _parse_args() -> argparse.Namespace:
        parser = argparse.ArgumentParser(
            prog="carnage",
            description="TUI front-end for Portage and eix",
            formatter_class=argparse.RawDescriptionHelpFormatter
        )

        # Version argument
        parser.add_argument(
            "-V", "--version",
            action="version",
            version=f"%(prog)s {__version__}",
            help="Show version information and exit"
        )

        # Config file path
        parser.add_argument(
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
config_path: Path | None = __args.get_element("config")
