from concurrent.futures import Future, ThreadPoolExecutor
from functools import cached_property
from typing import Any

from gentoolkit.package import Package

_executor = ThreadPoolExecutor(max_workers=1)
_QUERY_TIMEOUT = 5


def _portdb() -> Any:
    """Live portage tree database (tiny seam so tests can fake it)."""
    import portage

    return portage.db[portage.root]["porttree"].dbapi  # type: ignore


def _vardb() -> Any:
    """Live installed-packages database (tiny seam so tests can fake it)."""
    import portage

    return portage.db[portage.root]["vartree"].dbapi  # type: ignore


def _pinned_atom(cpv: str, repo: str | None) -> str:
    """Version atom pinned to its overlay; bare when the repo is unknown."""
    return f"={cpv}::{repo}" if repo else f"={cpv}"


def _run(query: Any) -> Any:
    """Run a portage query with a hang guard; workers already hold portage_lock."""
    future: Future[Any] = _executor.submit(query)

    try:
        return future.result(timeout=_QUERY_TIMEOUT)
    except TimeoutError:
        return None


def repo_available(cpv: str, repo: str | None) -> bool:
    """
    Whether this exact version is visible (unmasked) in its overlay.

    One match-visible query answers existence and masking together. Bare
    atoms keep today's best-visible semantics for versions whose overlay
    eix did not report.
    """
    try:
        return bool(_run(lambda: _portdb().xmatch("match-visible", _pinned_atom(cpv, repo))))
    except Exception:
        return False


def find_ebuild(cpv: str, repo: str | None) -> str | None:
    """Ebuild path for this version in its overlay, or None when absent."""
    try:
        found = _run(lambda: _portdb().findname2(cpv, myrepo=repo))
    except Exception:
        return None

    if not found:
        return None

    path, _tree = found
    return path


def repo_iuse(cpv: str, repo: str | None) -> list[str] | None:
    """IUSE flags of this version in its overlay, or None when unavailable."""
    try:
        raw = _run(lambda: _portdb().aux_get(cpv, ["IUSE"], myrepo=repo))
    except Exception:
        return None

    if not raw:
        return None

    return [flag.lstrip("+-") for flag in raw[0].split()]


def installed_use(cpv: str) -> set[str] | None:
    """USE flags enabled on the installed instance, or None when absent."""
    try:
        raw = _run(lambda: _vardb().aux_get(cpv, ["USE"]))

        if not raw:
            return None

        return set(raw[0].split())
    except Exception:
        return None


class GentoolkitPackage(Package):
    """Gentoolkit Package extended with extended specific helpers."""

    @cached_property
    def exists_f(self) -> bool:
        """True if the package exists in a repo."""
        future = _executor.submit(lambda: self.exists())

        try:
            return future.result(timeout=_QUERY_TIMEOUT)
        except TimeoutError:
            # A slow portage query must not take the app down. Treat it as
            # "not found" rather than letting the timeout escape into a
            # Textual message handler, which would exit the app.
            return False

    @cached_property
    def available(self) -> bool:
        """True if the package exists in a repo and is not masked."""
        future = _executor.submit(lambda: self.exists() and not self.is_masked())

        try:
            return future.result(timeout=_QUERY_TIMEOUT)
        except TimeoutError:
            # As above: report it as unavailable so the install button simply
            # stays hidden instead of crashing the view.
            return False
