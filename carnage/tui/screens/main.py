
"""Main screen with tabs for Carnage."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Header, Footer, TabbedContent, TabPane, Input, Label

from ...core.eix import is_found, has_cache
from ..widgets.overlay_tab import OverlaysTab
from ..widgets.news_tab import NewsTab
from ..widgets.glsa_tab import GLSATab

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
                    yield Label("Package browser will go here")

                with TabPane("USE", id="use", disabled=True):
                    yield Label("USE flags will go here")

                with TabPane("Overlays", id="overlays"):
                    yield OverlaysTab()

        yield Footer()

    def on_mount(self) -> None:
        """Check eix availability when screen is mounted."""
        self.eix_available = is_found()
        self.eix_cache_available = has_cache() if self.eix_available else False

        if self.eix_available and self.eix_cache_available:
            # Enable/disable tabs based on eix availability
            tabbed_content: TabbedContent = self.query_one(TabbedContent)

            # Enable Browse and USE tabs
            for tab in tabbed_content.query(TabPane):
                if tab.id in ("browse", "use"):
                    tab.disabled = False

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

        if active_tab_id in ("news", "glsas") and query:
            # Switch to Browse tab and trigger search there
            tabbed_content.active = "browse"