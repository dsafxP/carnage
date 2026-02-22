from concurrent.futures import ThreadPoolExecutor
from functools import cached_property

from gentoolkit.package import Package

_executor = ThreadPoolExecutor(max_workers=1)


class GentoolkitPackage(Package):
    """Gentoolkit Package extended with extended specific helpers."""

    @cached_property
    def available(self) -> bool:
        """True if the package exists in a repo and is not masked."""
        future = _executor.submit(lambda: self.exists() and not self.is_masked())

        return future.result(timeout=5)