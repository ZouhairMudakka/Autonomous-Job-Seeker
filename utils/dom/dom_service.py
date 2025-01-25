"""DOM Service for managing page interactions and element tracking"""

import os
from typing import List, Optional
from playwright.async_api import Page, ElementHandle, TimeoutError as PlaywrightTimeoutError
from utils.telemetry import TelemetryManager
from .dom_models import DOMElementNode

class DomService:
    def __init__(self, page: Page, telemetry: TelemetryManager = None):
        self.page = page
        self.telemetry = telemetry or TelemetryManager()

        self.js_path = os.path.join(
            os.path.dirname(__file__), 
            "build_dom_tree.js"
        )

    async def wait_for_selector(self, selector: str, timeout: float = None) -> Optional[ElementHandle]:
        """Wait for element to appear and return it."""
        try:
            return await self.page.wait_for_selector(selector, timeout=timeout)
        except PlaywrightTimeoutError:
            return None

    async def query_selector(self, selector: str) -> Optional[ElementHandle]:
        """Find first matching element."""
        return await self.page.query_selector(selector)

    async def query_selector_all(self, selector: str) -> List[ElementHandle]:
        """Find all matching elements."""
        return await self.page.query_selector_all(selector)

    async def screenshot_element(self, selector: str, path: Optional[str] = None) -> Optional[bytes]:
        """Take screenshot of element matching selector."""
        element = await self.query_selector(selector)
        if not element:
            return None
        return await element.screenshot(path=path)

    async def verify_selector_visible(self, selector: str, timeout: float = None) -> bool:
        """Check if selector is visible within timeout."""
        try:
            await self.wait_for_selector(selector, timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    async def get_dom_tree(self, highlight: bool = False, max_highlight: int = 75) -> DOMElementNode:
        """
        Get complete DOM tree with optional highlighting of up to 'max_highlight' clickable elements.
        In-viewport elements have priority for highlighting.
        """
        with open(self.js_path, "r", encoding="utf-8") as f:
            js_code = f.read()

        # Evaluate the script in the browser with highlight + maxHighlight
        script = f"""
        (() => {{
            {js_code}
            // We call buildDomTree on document.body
            return buildDomTree(document.body, {str(highlight).lower()}, {max_highlight});
        }})();
        """

        tree_data = await self.page.evaluate(script)

        return DOMElementNode.from_dict(tree_data)

    async def get_clickable_elements(self, highlight: bool = True, max_highlight: int = 75) -> List[DOMElementNode]:
        """
        Retrieve all clickable elements (according to the JS script).
        Optionally highlight them on screen, up to max_highlight, in-viewport first.
        """
        dom_tree = await self.get_dom_tree(highlight=highlight, max_highlight=max_highlight)
        clickable = dom_tree.find_clickable_elements()
        return clickable

    async def refresh_highlights(self, interval_sec: float = 2.0, iterations: int = 5) -> None:
        """
        (Optional) Repeatedly call get_clickable_elements to re-highlight 
        as the user scrolls or the DOM changes. 
        This is purely for demonstration; you can remove or adapt as needed.
        """
        for _ in range(iterations):
            await self.get_clickable_elements(highlight=True, max_highlight=75)
            # Wait before calling again
            await self.page.wait_for_timeout(interval_sec * 1000)
