"""Portage repository path queries and shared portage API context."""

from functools import cached_property
from pathlib import Path

import portage
import portage.util
from portage.dbapi.porttree import portdbapi
from portage.dbapi.vartree import vardbapi


class PortageContext:
    """
    Lazily exposes the portage trees, settings, and dbapis needed for
    interacting with the portage API.
    """

    @cached_property
    def _trees(self) -> portage.util.LazyItemsDict:
        """The trees dict for the target root, built via ``create_trees()``."""
        trees = portage.create_trees()
        return trees[trees._target_eroot]

    @cached_property
    def settings(self) -> portage.config: # type: ignore
        """The portage config/settings for the current root."""
        return self._trees["vartree"].settings

    @cached_property
    def vardbapi(self) -> vardbapi:
        """The installed-packages database (vartree)."""
        return self._trees["vartree"].dbapi

    @cached_property
    def portdbapi(self) -> portdbapi:
        """The ebuild repository database (porttree)."""
        return self._trees["porttree"].dbapi

    @cached_property
    def gentoo_repo_path(self) -> Path:
        """Path to the main Gentoo repository."""
        for repo in self.settings.repositories:
            if repo.name == "gentoo":
                return Path(repo.location)

        return Path("/var/db/repos/gentoo") # fallback

    @cached_property
    def repos_path(self) -> Path:
        """Parent directory containing all repository directories."""
        return self.gentoo_repo_path.parent


ctx = PortageContext()