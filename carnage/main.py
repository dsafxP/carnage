import sys

from carnage.core.args import parse_args
from carnage.core.lock import InstanceLock
from carnage.tui.app import CarnageApp


def main() -> None:
    parse_args()

    app = CarnageApp()

    lock = InstanceLock(on_signal=lambda _: app.call_from_thread(app.bell))

    if not lock.acquire():
        sys.exit(0)
    try:
        app.run()
    finally:
        lock.release()


if __name__ == "__main__":
    main()
