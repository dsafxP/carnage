from carnage.core.lock import InstanceLock
from carnage.tui.app import CarnageApp


def main() -> None:
    app = CarnageApp()

    lock = InstanceLock(on_signal=lambda _: app.bell())

    if not lock.acquire():
        import sys
        sys.exit(0)

    try:
        app.run()
    finally:
        lock.release()

if __name__ == "__main__":
    main()