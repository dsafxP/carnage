"""Main screen with tabs for Carnage."""


from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Header, Input, TabbedContent, TabPane

from ...core.config import Configuration, get_config
from ...core.eix import has_cache, is_found
from ..widgets.browse_tab import BrowseTab
from ..widgets.glsa_tab import GLSATab
from ..widgets.news_tab import NewsTab
from ..widgets.overlay_tab import OverlaysTab
from ..widgets.use_tab import UseFlagsTab


class MainScreen(Screen):
    """Main screen with search bar and tabbed content."""

    def __init__(self) -> None:
        super().__init__()
        self.eix_available = False
        self.eix_cache_available = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the screen."""
        yield Header()

        with Container(id="main-container"):
            # Search bar at the top
            yield Input(
                id="search-input"
            )

            # Tabbed content
            with TabbedContent(initial="news"):
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

    def on_mount(self) -> None:
        """Check eix availability when screen is mounted."""
        self.eix_available = is_found()
        self.eix_cache_available = has_cache() if self.eix_available else False

        tabbed_content: TabbedContent = self.query_one(TabbedContent)

        # Enable/disable tabs based on eix availability
        if self.eix_available and self.eix_cache_available:
            # Enable Browse and USE tabs
            for tab in tabbed_content.query(TabPane):
                if tab.id in ("browse", "use"):
                    tab.disabled = False

        config: Configuration = get_config()

        tabbed_content.active = (
            config.initial_tab
            if (self.eix_available and self.eix_cache_available or config.initial_tab not in ("browse", "use"))
            else "news"
        )

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Handle tab changes to update search bar."""
        search_input: Input = self.query_one("#search-input", Input)
        tab_id: str | None = event.tab.id

        if tab_id is None:
            return

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

    def on_input_changed(self, event: Input.Changed) -> None:
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
