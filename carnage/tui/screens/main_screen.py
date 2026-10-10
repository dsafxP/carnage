"""Main screen with tabs for Carnage."""

from typing import ClassVar

from rich.markup import MarkupError, escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Header, Input, RichLog, TabbedContent, TabPane

from carnage.core.config import Configuration, get_config
from carnage.core.eix.eix import has_cache, is_found
from carnage.tui.widgets.browse.browse_tab import BrowseTab
from carnage.tui.widgets.cachetabbedcontent import CachedTabbedContent
from carnage.tui.widgets.glsa_tab import GLSATab
from carnage.tui.widgets.news_tab import NewsTab
from carnage.tui.widgets.overlay_tab import OverlaysTab
from carnage.tui.widgets.use_tab import UseFlagsTab


class MainScreen(Screen):
    """Main screen with search bar and tabbed content."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+l", "toggle_operation_log", "Toggle log view pane", show=True)
    ]

    def __init__(self) -> None:
        super().__init__()
        self.eix_available = False
        self.eix_cache_available = False
        self._log_pane: RichLog | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the screen."""
        yield Header()

        # Search bar
        yield Input(id="search-input")

        # Tabbed content
        with Horizontal(id="main-content"):
            # Tabbed content on the left (takes most space)
            with CachedTabbedContent(cache_key="main_tabs", initial="news", id="tabs"):
                with TabPane("News", id="news"):
                    yield NewsTab()

                with TabPane("GLSAs", id="glsas"):
                    yield GLSATab()

                with TabPane("Browse", id="browse", disabled=True):
                    yield BrowseTab()

                with TabPane("USE", id="use", disabled=True):
                    yield UseFlagsTab()

                with TabPane("Overlays", id="overlays"):
                    yield OverlaysTab()

            # Operation log on the right
            yield RichLog(id="operation-log", markup=True, highlight=True, wrap=True)

    def on_mount(self) -> None:
        """Check eix availability when screen is mounted."""
        # The probe spawns a subprocess, so it runs in a worker: the first
        # frame must not wait for it, and neither must the screen swaps after
        # an update (when the cache is coldest). Tabs and search state are
        # enabled when it reports back.
        self._probe_eix_availability()

        config: Configuration = get_config()

        if config.compact_mode:
            self.add_class("compact")

        log_pane: RichLog = self.query_one("#operation-log", RichLog)

        # Hide by default
        log_pane.display = False

        # Resolved once: this is called for every streamed output line, and a
        # selector parse plus DOM walk per line is what made verbose commands
        # feel sluggish.
        self._log_pane = log_pane

    def log_operation_output(self, raw_line: bytes) -> None:
        """Add raw output (with ANSI codes) to the RichLog widget."""
        log_pane = self._log_pane

        if log_pane is None:
            log_pane = self._log_pane = self.query_one("#operation-log", RichLog)

        config: Configuration = get_config()

        if not log_pane.display and config.automatic_pane:
            # Optionally auto-show log when operation starts
            log_pane.display = True

        # RichLog automatically handles ANSI color codes
        # Decode as latin-1 to preserve all bytes, then log
        try:
            line = raw_line.decode("utf-8", errors="replace").rstrip()
        except Exception:
            line = raw_line.decode("latin-1", errors="replace").rstrip()

        # Write to RichLog - it will parse ANSI codes
        try:
            log_pane.write(line)
        except MarkupError:
            # Subprocess output is not authored by us: a stray "[" (or an
            # unmatched tag) must not blow up the worker running the command.
            # The app's own [dim]/[red] markers stay markup, everything else
            # falls back to literal text.
            log_pane.write(escape(line))

    @work(thread=True)
    def _probe_eix_availability(self) -> None:
        """Probe for eix off the event loop, then enable what it allows."""
        available = is_found()
        cache_available = has_cache() if available else False

        self.app.call_from_thread(self._apply_eix_availability, available, cache_available)

    def _apply_eix_availability(self, available: bool, cache_available: bool) -> None:
        """Enable eix tabs and refresh the search state (event loop only)."""
        self.eix_available = available
        self.eix_cache_available = cache_available

        if available and cache_available:
            # Enable Browse and USE tabs
            for tab in self.query_one(TabbedContent).query(TabPane):
                if tab.id in ("browse", "use"):
                    tab.disabled = False

        tabbed_content: TabbedContent = self.query_one(TabbedContent)
        self._update_search_state(tabbed_content.active)

    def _on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Handle tab changes to update search bar."""
        tab_id: str | None = event.tab.id

        if tab_id is None:
            return

        self._update_search_state(tab_id)

    def _update_search_state(self, tab_id: str) -> None:
        """Update the search bar placeholder and state for the active tab."""
        search_input: Input = self.query_one("#search-input", Input)

        # Update placeholder and state based on active tab
        if "overlays" in tab_id:
            search_input.placeholder = "Search overlays ..."
            search_input.disabled = False
        elif "use" in tab_id:
            search_input.placeholder = "Search USE flags ..."
            # USE tab will be disabled if eix is not available
            search_input.disabled = False
        else:
            if not self.eix_available:
                search_input.placeholder = "eix not found - Browse tab disabled"
                search_input.disabled = True
            elif not self.eix_cache_available:
                search_input.placeholder = "No eix cache - Run eix-update first"
                search_input.disabled = True
            else:
                search_input.placeholder = "Search a package ..."
                search_input.disabled = False

    def _on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id != "search-input":
            return

        # Get the current active tab
        tabbed_content: TabbedContent = self.query_one(TabbedContent)
        active_tab_id: str = tabbed_content.active

        query: str = event.value

        if active_tab_id == "overlays":
            # Apply search filter to overlays tab
            overlays_pane: TabPane = tabbed_content.query_one("#overlays", TabPane)
            overlays_tab: OverlaysTab = overlays_pane.query_one(OverlaysTab)
            overlays_tab.apply_filter(query)
        elif active_tab_id == "browse":
            # Apply search to browse tab
            browse_pane: TabPane = tabbed_content.query_one("#browse", TabPane)
            browse_tab: BrowseTab = browse_pane.query_one(BrowseTab)
            browse_tab.search_packages(query)
        elif active_tab_id == "use":
            # Apply search to USE tab
            use_pane: TabPane = tabbed_content.query_one("#use", TabPane)
            use_tab: UseFlagsTab = use_pane.query_one(UseFlagsTab)
            use_tab.search_useflags(query)
        elif active_tab_id in ("news", "glsas") and query:
            # Switch to Browse tab and trigger search there
            tabbed_content.active = "browse"

    def _on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "search-input":
            return

        tabbed_content: TabbedContent = self.query_one(TabbedContent)
        active_tab_id: str = tabbed_content.active

        # Focus the relevant widget in the active tab
        if active_tab_id == "browse":
            browse_tab: BrowseTab = tabbed_content.query_one("#browse", TabPane).query_one(BrowseTab)
            browse_tab.query_one("#browse-table").focus()
        elif active_tab_id == "overlays":
            overlays_tab: OverlaysTab = tabbed_content.query_one("#overlays", TabPane).query_one(OverlaysTab)
            overlays_tab.focus()
        elif active_tab_id == "use":
            use_tab: UseFlagsTab = tabbed_content.query_one("#use", TabPane).query_one(UseFlagsTab)
            use_tab.focus()

    def _action_toggle_operation_log(self) -> None:
        """Toggle the operation log pane visibility."""
        log_pane = self.query_one("#operation-log", RichLog)
        log_pane.display = not log_pane.display
