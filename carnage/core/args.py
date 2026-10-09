import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir

import carnage


class __ArgsInit:
    def __init__(self) -> None:
        self.__namespace: argparse.Namespace | None = None

    @staticmethod
    def _build_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog=carnage.__name__, description=carnage.__doc__)

        # Version argument
        parser.add_argument(
            "-V",
            "--version",
            action="version",
            version=f"%(prog)s {carnage.__version__}",
            help="Show version information and exit",
        )

        # Config file path
        parser.add_argument(
            "-c", "--config", type=Path, default=None, help="Path to configuration file", metavar="FILE"
        )

        # CSS file path
        parser.add_argument(
            "--css",
            type=Path,
            default=Path(user_config_dir("carnage")) / "custom.tcss",
            help="Path to custom CSS file",
            metavar="FILE",
        )

        return parser

    def parse(self, argv: Sequence[str] | None = None) -> argparse.Namespace:
        """Parse the command line, unless it was already parsed."""
        if self.__namespace is None:
            self.__namespace = self._build_parser().parse_args(argv)
        return self.__namespace

    def reset(self) -> None:
        """Forget the cached command line so it can be parsed again."""
        self.__namespace = None

    def get_element(self, element: str) -> Any:
        """Returns the value of a command line argument"""
        return getattr(self.parse(), element, None)


__args = __ArgsInit()


def parse_args(argv: Sequence[str] | None = None) -> None:
    """Eagerly parse the command line so ``--help``/``--version`` exit before startup work."""
    _ = __args.parse(argv)


def reset_args() -> None:
    """Discard the cached command line. Intended for tests."""
    __args.reset()


def get_config_path() -> Path | None:
    """Path to the configuration file requested on the command line, if any."""
    return __args.get_element("config")


def get_css_path() -> Path:
    """Path to the custom stylesheet requested on the command line."""
    return __args.get_element("css")
