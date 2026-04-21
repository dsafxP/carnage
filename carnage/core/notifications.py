from typing import Optional

try:
    from desktop_notifier import DesktopNotifier
    from desktop_notifier.common import Icon

    HAS_NOTIFICATIONS = True
except ImportError:
    HAS_NOTIFICATIONS = False


def get_notifier() -> Optional["DesktopNotifier"]:
    """Get a DesktopNotifier instance configured for carnage."""
    if not HAS_NOTIFICATIONS:
        return None

    return DesktopNotifier(app_name="carnage", app_icon=Icon(name="carnage"))
