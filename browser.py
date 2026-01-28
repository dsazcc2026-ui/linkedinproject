"""
Browser management with persistent Chrome context.
Reuses existing Chrome login session for LinkedIn.
"""

import os
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


def get_brain_profile_dir() -> Path:
    """Get the Brain-specific profile directory."""
    # Allow override via environment variable
    if custom_path := os.environ.get("BRAIN_PROFILE_DIR"):
        return Path(custom_path)

    # Use a dedicated directory for Brain in the project folder
    return Path(__file__).parent / ".brain_profile"


class LinkedInBrowser:
    """Manages a persistent browser session for LinkedIn."""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self):
        """Start the browser with persistent context."""
        profile_dir = get_brain_profile_dir()
        profile_dir.mkdir(exist_ok=True)

        self._playwright = sync_playwright().start()

        # Use persistent context - login once, reuse session
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",  # Less detectable
            ]
        )

        # Use existing page or create new one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = self._context.new_page()

    def close(self):
        """Close browser and cleanup."""
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass  # Browser may already be closed
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page

    def goto_linkedin(self) -> bool:
        """Navigate to LinkedIn and check if logged in."""
        self.page.goto("https://www.linkedin.com/feed/", timeout=60000)
        self.page.wait_for_load_state("domcontentloaded")

        # Give page a moment to redirect if not logged in
        self.page.wait_for_timeout(2000)

        # Check if we're on the feed (logged in) or redirected to login
        current_url = self.page.url
        is_logged_in = "/feed" in current_url or "/in/" in current_url

        return is_logged_in

    def search(self, query: str) -> None:
        """Execute a search on LinkedIn."""
        # Navigate to search
        search_url = f"https://www.linkedin.com/search/results/people/?keywords={query}"
        self.page.goto(search_url, timeout=60000)
        self.page.wait_for_load_state("domcontentloaded")
