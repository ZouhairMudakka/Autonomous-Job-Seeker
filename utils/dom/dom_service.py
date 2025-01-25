"""DOM Service for managing page interactions and element tracking"""

import os
from typing import List, Optional, Any
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

    # ===================
    # Basic Query Methods
    # ===================
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

    async def check_element_present(self, selector: str, timeout: float = None) -> bool:
        """Check if element is present without throwing exception."""
        try:
            await self.wait_for_selector(selector, timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    # ===================
    # Navigation Methods
    # ===================
    async def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: float = None):
        """
        Navigate to URL with specified wait condition.
        
        Args:
            url: The URL to navigate to
            wait_until: Navigation wait condition ('domcontentloaded', 'load', 'networkidle')
            timeout: Maximum time to wait for navigation
        """
        return await self.page.goto(url, wait_until=wait_until, timeout=timeout)

    # ===================
    # Action Methods
    # ===================
    async def click_element(self, selector: str):
        """
        Click element with given selector.
        
        Args:
            selector: CSS or XPath selector
            
        Raises:
            Exception if element not found or click fails
        """
        element = await self.wait_for_selector(selector)
        if not element:
            raise Exception(f"[DomService] Unable to click. Selector not found: {selector}")
        await element.click()

    async def type_text(self, selector: str, text: str, clear_first: bool = True):
        """
        Type text into input field.
        
        Args:
            selector: Input field selector
            text: Text to type
            clear_first: Whether to clear existing text first
        """
        element = await self.wait_for_selector(selector)
        if not element:
            raise Exception(f"[DomService] Unable to type text. Selector not found: {selector}")
        if clear_first:
            await element.fill("")
        await element.type(text)

    # ===================
    # Scrolling Methods
    # ===================
    async def scroll_to_bottom(self, step: int = 200, pause: float = 1.0):
        """
        Scroll to page bottom gradually.
        
        Args:
            step: Pixels to scroll each step
            pause: Delay between steps in seconds
        """
        current_height = await self.page.evaluate("() => document.body.scrollHeight")
        pos = 0
        while pos < current_height:
            pos += step
            await self.page.mouse.wheel(0, step)
            await self.page.wait_for_timeout(int(pause * 1000))
            new_height = await self.page.evaluate("() => document.body.scrollHeight")
            if new_height > current_height:
                current_height = new_height

    async def scroll_to_element(self, selector: str):
        """
        Scroll element into view.
        
        Args:
            selector: Element selector to scroll to
            
        Raises:
            Exception if element not found
        """
        element = await self.wait_for_selector(selector)
        if not element:
            raise Exception(f"[DomService] scroll_to_element: selector not found: {selector}")
        await element.scroll_into_view_if_needed()

    # ===================
    # Screenshot Methods
    # ===================
    async def screenshot_element(self, selector: str, path: Optional[str] = None) -> Optional[bytes]:
        """Take screenshot of specific element."""
        element = await self.query_selector(selector)
        if not element:
            return None
        return await element.screenshot(path=path)

    async def take_screenshot(self, path: str, full_page: bool = True):
        """Take full page or viewport screenshot."""
        await self.page.screenshot(path=path, full_page=full_page)

    # ===================
    # Evaluation Methods
    # ===================
    async def evaluate_script(self, script: str) -> Any:
        """Evaluate JavaScript in page context."""
        return await self.page.evaluate(script)

    # ===================
    # Frame Handling
    # ===================
    async def switch_to_iframe(self, iframe_selector: str):
        """
        Switch context to iframe.
        Updates self.page to point to iframe content.
        
        Args:
            iframe_selector: Selector for the iframe element
            
        Raises:
            Exception if iframe not found or content frame not accessible
        """
        frame_element = await self.wait_for_selector(iframe_selector)
        if not frame_element:
            raise Exception(f"[DomService] Iframe not found: {iframe_selector}")
        frame = await frame_element.content_frame()
        if not frame:
            raise Exception(f"[DomService] Could not get content_frame for {iframe_selector}")
        self.page = frame

    def switch_back_to_main_frame(self, main_page: Page):
        """
        Switch back to main page context.
        
        Args:
            main_page: The original Page object to switch back to
        """
        self.page = main_page

    # ===================
    # Advanced Interactions
    # ===================
    async def drag_and_drop(self, source_selector: str, target_selector: str, hold_delay: float = 0.5):
        """Perform drag and drop operation."""
        source = await self.wait_for_selector(source_selector)
        target = await self.wait_for_selector(target_selector)
        
        if not source or not target:
            raise Exception("[DomService] Source or target element not found for drag and drop")

        await source.hover()
        await self.page.mouse.down()
        await self.page.wait_for_timeout(int(hold_delay * 1000))
        await target.hover()
        await self.page.mouse.up()

    async def extract_links(self, selector: str = "a") -> List[str]:
        """Extract href attributes from elements."""
        elements = await self.query_selector_all(selector)
        links = []
        for el in elements:
            href = await el.get_attribute("href")
            if href:
                links.append(href)
        return links

    # ===================
    # DOM Tree Methods
    # ===================
    async def get_dom_tree(self, highlight: bool = False, max_highlight: int = 75) -> DOMElementNode:
        """Get DOM tree with optional highlighting."""
        with open(self.js_path, "r", encoding="utf-8") as f:
            js_code = f.read()

        script = f"""
        (() => {{
            {js_code}
            return buildDomTree(document.body, {str(highlight).lower()}, {max_highlight});
        }})();
        """

        tree_data = await self.page.evaluate(script)
        return DOMElementNode.from_dict(tree_data)

    async def get_clickable_elements(self, highlight: bool = True, max_highlight: int = 75) -> List[DOMElementNode]:
        """Get clickable elements with optional highlighting."""
        dom_tree = await self.get_dom_tree(highlight=highlight, max_highlight=max_highlight)
        clickable = dom_tree.find_clickable_elements()
        return clickable

    async def refresh_highlights(self, interval_sec: float = 2.0, iterations: int = 5) -> None:
        """Refresh element highlights periodically."""
        for _ in range(iterations):
            await self.get_clickable_elements(highlight=True, max_highlight=75)
            await self.page.wait_for_timeout(int(interval_sec * 1000))
