"""Operation output log with a widget-scoped clear binding."""

from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.widgets import RichLog


class OperationLog(RichLog):
    """
    RichLog whose Del key clears the output.

    The binding lives on the widget rather than on the screen or the app,
    so Del only clears the log while the pane itself is focused.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("delete", "clear_log", "Clear log", show=True),
    ]

    def action_clear_log(self) -> None:
        """Clear all output from the log."""
        self.clear()
