import threading
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property

from gentoolkit.package import Package

_executor = ThreadPoolExecutor(max_workers=1)
_QUERY_TIMEOUT = 5

portage_lock = threading.Lock()
"""
Serializes in-process portage access across worker threads.

Portage is not thread-safe for concurrent use (its config object raises
"Configuration is locked" and its lazy imports race). The single-thread
executors above serialize within one module, but workers in different
modules - or direct queries like parsed_contents() - still meet inside
portage. Hold this around any blocking portage call made off the loop.
"""


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
