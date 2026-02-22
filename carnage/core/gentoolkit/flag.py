"""Thread-safe wrappers for gentoolkit.flag functions."""

from concurrent.futures import ThreadPoolExecutor

from gentoolkit.flag import get_all_cpv_use

_executor = ThreadPoolExecutor(max_workers=1)


def get_all_cpv_usef(cpv) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Thread-safe wrapper for gentoolkit.flag.get_all_cpv_use().
    """

    future = _executor.submit(get_all_cpv_use, cpv)

    return future.result(timeout=10)