import os
import sys

from carnage.core.lock import InstanceLock
from carnage.tui.app import CarnageApp


def main() -> None:
    # Check if running as root
    if os.geteuid() == 0:
        print("carnage must not be run as root!")
        sys.exit(1)

    app = CarnageApp()

    lock = InstanceLock(on_signal=lambda _: app.bell())

    if not lock.acquire():
        sys.exit(0)
    try:
        app.run()
    finally:
        lock.release()


if __name__ == "__main__":
    main()
