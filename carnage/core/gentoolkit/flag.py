"""Thread-safe wrappers for gentoolkit.flag functions."""

from concurrent.futures import ThreadPoolExecutor

from gentoolkit.flag import get_all_cpv_use

_executor = ThreadPoolExecutor(max_workers=1)
_QUERY_TIMEOUT = 10


def get_all_cpv_usef(cpv) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Thread-safe wrapper for gentoolkit.flag.get_all_cpv_use().

    Returns empty flag lists when the portage query times out, so a slow
    system shows an empty USE list instead of exiting the app.
    """

    future = _executor.submit(get_all_cpv_use, cpv)

    try:
        return future.result(timeout=_QUERY_TIMEOUT)
    except TimeoutError:
        return ([], [], [], [])
