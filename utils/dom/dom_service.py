"""DOM Service for managing page interactions and element tracking"""

import os
import json
from typing import List, Optional, Any
from playwright.async_api import Page, ElementHandle, TimeoutError as PlaywrightTimeoutError
from utils.telemetry import TelemetryManager
from storage.logs_manager import LogsManager
from .dom_models import DOMElementNode
import asyncio

class DomService:
    def __init__(self, page: Page, telemetry: TelemetryManager = None, settings: dict = None, logs_manager: LogsManager = None):
        """Initialize DOM service with page and optional telemetry."""
        self.page = page
        self.telemetry = telemetry or TelemetryManager(settings or {"telemetry": {"enabled": True}})
        self.logs_manager = logs_manager
        
        self.js_path = os.path.join(
            os.path.dirname(__file__), 
            "build_dom_tree.js"
        )
        
        if self.logs_manager:
            asyncio.create_task(self.logs_manager.info("Initialized DomService with page and telemetry"))

    async def _inject_logging_bridge(self):
        """Inject the logging bridge into the page context."""
        if not self.logs_manager:
            return
            
        # Create a bridge function that will call our Python logs_manager
        bridge_script = """
        window.logToPython = (level, message) => {
            window.logQueue = window.logQueue || [];
            window.logQueue.push({level, message});
        };
        """
        await self.page.evaluate(bridge_script)
        
        # Set up an interval to check for and process logs
        process_logs_script = """
        setInterval(() => {
            if (window.logQueue && window.logQueue.length > 0) {
                const logs = window.logQueue;
                window.logQueue = [];
                window._processLogs(logs);
            }
        }, 100);
        """
        
        # Expose Python logging function to JavaScript
        async def process_logs(logs):
            for log in logs:
                level = log.get('level', 'info')
                message = log.get('message', '')
                if level == 'error':
                    await self.logs_manager.error(f"[DOM Tree] {message}")
                elif level == 'warning':
                    await self.logs_manager.warning(f"[DOM Tree] {message}")
                elif level == 'debug':
                    await self.logs_manager.debug(f"[DOM Tree] {message}")
                else:
                    await self.logs_manager.info(f"[DOM Tree] {message}")
                    
        await self.page.expose_function('_processLogs', process_logs)
        await self.page.evaluate(process_logs_script)

    # ===================
    # Basic Query Methods
    # ===================
    async def wait_for_selector(self, selector: str, timeout: float = None) -> Optional[ElementHandle]:
        """Wait for element to appear and return it."""
        if self.logs_manager:
            await self.logs_manager.debug(f"Waiting for selector: {selector} (timeout={timeout}s)")
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if self.logs_manager:
                if element:
                    await self.logs_manager.debug(f"Successfully found selector: {selector}")
                else:
                    await self.logs_manager.warning(f"Selector returned None: {selector}")
            return element
        except PlaywrightTimeoutError:
            if self.logs_manager:
                await self.logs_manager.warning(f"Timeout waiting for selector: {selector}")
            return None

    async def query_selector(self, selector: str) -> Optional[ElementHandle]:
        """Find first matching element."""
        if self.logs_manager:
            await self.logs_manager.debug(f"Querying for selector: {selector}")
        element = await self.page.query_selector(selector)
        if self.logs_manager:
            if element:
                await self.logs_manager.debug(f"Found element for selector: {selector}")
            else:
                await self.logs_manager.debug(f"No element found for selector: {selector}")
        return element

    async def query_selector_all(self, selector: str) -> List[ElementHandle]:
        """Find all matching elements."""
        if self.logs_manager:
            await self.logs_manager.debug(f"Querying for all elements matching selector: {selector}")
        elements = await self.page.query_selector_all(selector)
        if self.logs_manager:
            await self.logs_manager.debug(f"Found {len(elements)} elements for selector: {selector}")
        return elements

    async def check_element_present(self, selector: str, timeout: float = None) -> bool:
        """Check if element is present without throwing exception."""
        if self.logs_manager:
            await self.logs_manager.debug(f"Checking presence of element: {selector} (timeout={timeout}s)")
        try:
            await self.wait_for_selector(selector, timeout=timeout)
            if self.logs_manager:
                await self.logs_manager.debug(f"Element is present: {selector}")
            return True
        except PlaywrightTimeoutError:
            if self.logs_manager:
                await self.logs_manager.debug(f"Element is not present: {selector}")
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
        if self.logs_manager:
            await self.logs_manager.info(f"Navigating to URL: {url} (wait_until={wait_until})")
        try:
            response = await self.page.goto(url, wait_until=wait_until, timeout=timeout)
            if self.logs_manager:
                if response:
                    await self.logs_manager.info(f"Successfully navigated to {url} (status={response.status})")
                else:
                    await self.logs_manager.warning(f"Navigation to {url} completed but no response received")
            return response
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to navigate to {url}: {str(e)}")
            raise

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
        if self.logs_manager:
            await self.logs_manager.debug(f"Attempting to click element: {selector}")
        
        element = await self.wait_for_selector(selector)
        if not element:
            if self.logs_manager:
                await self.logs_manager.error(f"Unable to click. Selector not found: {selector}")
            raise Exception(f"[DomService] Unable to click. Selector not found: {selector}")
            
        try:
            await element.click()
            if self.logs_manager:
                await self.logs_manager.debug(f"Successfully clicked element: {selector}")
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to click element {selector}: {str(e)}")
            raise

    async def type_text(self, selector: str, text: str, clear_first: bool = True):
        """
        Type text into input field.
        
        Args:
            selector: Input field selector
            text: Text to type
            clear_first: Whether to clear existing text first
        """
        if self.logs_manager:
            await self.logs_manager.debug(f"Attempting to type text into element: {selector}")
            
        element = await self.wait_for_selector(selector)
        if not element:
            if self.logs_manager:
                await self.logs_manager.error(f"Unable to type text. Selector not found: {selector}")
            raise Exception(f"[DomService] Unable to type text. Selector not found: {selector}")
            
        try:
            if clear_first:
                if self.logs_manager:
                    await self.logs_manager.debug(f"Clearing existing text in: {selector}")
                await element.fill("")
            await element.type(text)
            if self.logs_manager:
                await self.logs_manager.debug(f"Successfully typed text into: {selector}")
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to type text into {selector}: {str(e)}")
            raise

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
        if self.logs_manager:
            await self.logs_manager.debug(f"Starting gradual scroll to bottom (step={step}px, pause={pause}s)")
            
        current_height = await self.page.evaluate("() => document.body.scrollHeight")
        pos = 0
        while pos < current_height:
            pos += step
            await self.page.mouse.wheel(0, step)
            await self.page.wait_for_timeout(int(pause * 1000))
            new_height = await self.page.evaluate("() => document.body.scrollHeight")
            
            if self.logs_manager:
                await self.logs_manager.debug(f"Scrolled to position {pos}/{current_height}px")
                
            if new_height > current_height:
                if self.logs_manager:
                    await self.logs_manager.debug(f"Page height increased from {current_height} to {new_height}px")
                current_height = new_height
                
        if self.logs_manager:
            await self.logs_manager.debug("Completed scroll to bottom")

    async def scroll_to_element(self, selector: str):
        """
        Scroll element into view.
        
        Args:
            selector: Element selector to scroll to
            
        Raises:
            Exception if element not found
        """
        if self.logs_manager:
            await self.logs_manager.debug(f"Attempting to scroll to element: {selector}")
            
        element = await self.wait_for_selector(selector)
        if not element:
            if self.logs_manager:
                await self.logs_manager.error(f"scroll_to_element: selector not found: {selector}")
            raise Exception(f"[DomService] scroll_to_element: selector not found: {selector}")
            
        try:
            await element.scroll_into_view_if_needed()
            if self.logs_manager:
                await self.logs_manager.debug(f"Successfully scrolled to element: {selector}")
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to scroll to element {selector}: {str(e)}")
            raise

    # ===================
    # Screenshot Methods
    # ===================
    async def screenshot_element(self, selector: str, path: Optional[str] = None) -> Optional[bytes]:
        """Take screenshot of specific element."""
        if self.logs_manager:
            await self.logs_manager.debug(f"Attempting to screenshot element: {selector}")
            
        element = await self.query_selector(selector)
        if not element:
            if self.logs_manager:
                await self.logs_manager.warning(f"Element not found for screenshot: {selector}")
            return None
            
        try:
            screenshot = await element.screenshot(path=path)
            if self.logs_manager:
                if path:
                    await self.logs_manager.info(f"Saved element screenshot to: {path}")
                else:
                    await self.logs_manager.debug("Captured element screenshot to memory")
            return screenshot
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to take element screenshot: {str(e)}")
            raise

    async def take_screenshot(self, path: str, full_page: bool = True):
        """Take full page or viewport screenshot."""
        try:
            if self.logs_manager:
                await self.logs_manager.info(f"Taking {'full page' if full_page else 'viewport'} screenshot: {path}")
            await self.page.screenshot(path=path, full_page=full_page)
            if self.logs_manager:
                await self.logs_manager.info(f"Successfully saved screenshot to: {path}")
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to take screenshot: {str(e)}")
            raise

    # ===================
    # Evaluation Methods
    # ===================
    async def evaluate_script(self, script: str) -> Any:
        """Evaluate JavaScript in page context."""
        if self.logs_manager:
            await self.logs_manager.debug("Evaluating JavaScript in page context")
        try:
            result = await self.page.evaluate(script)
            if self.logs_manager:
                await self.logs_manager.debug("Successfully evaluated JavaScript")
            return result
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to evaluate JavaScript: {str(e)}")
            raise

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
        if self.logs_manager:
            await self.logs_manager.debug(f"Attempting to switch to iframe: {iframe_selector}")
            
        frame_element = await self.wait_for_selector(iframe_selector)
        if not frame_element:
            if self.logs_manager:
                await self.logs_manager.error(f"Iframe not found: {iframe_selector}")
            raise Exception(f"[DomService] Iframe not found: {iframe_selector}")
            
        try:
            frame = await frame_element.content_frame()
            if not frame:
                if self.logs_manager:
                    await self.logs_manager.error(f"Could not get content_frame for {iframe_selector}")
                raise Exception(f"[DomService] Could not get content_frame for {iframe_selector}")
                
            self.page = frame
            if self.logs_manager:
                await self.logs_manager.info(f"Successfully switched to iframe: {iframe_selector}")
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to switch to iframe {iframe_selector}: {str(e)}")
            raise

    def switch_back_to_main_frame(self, main_page: Page):
        """
        Switch back to main page context.
        
        Args:
            main_page: The original Page object to switch back to
        """
        if self.logs_manager:
            # Since this is a sync method, we use create_task for the async log call
            asyncio.create_task(self.logs_manager.info("Switching back to main frame"))
            
        self.page = main_page
        
        if self.logs_manager:
            asyncio.create_task(self.logs_manager.info("Successfully switched back to main frame"))

    # ===================
    # Advanced Interactions
    # ===================
    async def drag_and_drop(self, source_selector: str, target_selector: str, hold_delay: float = 0.5):
        """Perform drag and drop operation."""
        if self.logs_manager:
            await self.logs_manager.debug(f"Starting drag and drop operation from {source_selector} to {target_selector}")
            
        source = await self.wait_for_selector(source_selector)
        target = await self.wait_for_selector(target_selector)
        
        if not source or not target:
            if self.logs_manager:
                await self.logs_manager.error("Source or target element not found for drag and drop")
            raise Exception("[DomService] Source or target element not found for drag and drop")

        try:
            if self.logs_manager:
                await self.logs_manager.debug(f"Hovering over source element: {source_selector}")
            await source.hover()
            
            if self.logs_manager:
                await self.logs_manager.debug("Mouse down on source element")
            await self.page.mouse.down()
            
            await self.page.wait_for_timeout(int(hold_delay * 1000))
            
            if self.logs_manager:
                await self.logs_manager.debug(f"Hovering over target element: {target_selector}")
            await target.hover()
            
            if self.logs_manager:
                await self.logs_manager.debug("Mouse up on target element")
            await self.page.mouse.up()
            
            if self.logs_manager:
                await self.logs_manager.info("Successfully completed drag and drop operation")
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to perform drag and drop: {str(e)}")
            raise

    async def extract_links(self, selector: str = "a") -> List[str]:
        """Extract href attributes from elements."""
        if self.logs_manager:
            await self.logs_manager.debug(f"Extracting links from elements matching: {selector}")
            
        elements = await self.query_selector_all(selector)
        links = []
        
        for i, el in enumerate(elements, 1):
            try:
                href = await el.get_attribute("href")
                if href:
                    links.append(href)
                    if self.logs_manager:
                        await self.logs_manager.debug(f"Found link {i}: {href}")
            except Exception as e:
                if self.logs_manager:
                    await self.logs_manager.warning(f"Failed to extract href from element {i}: {str(e)}")
                
        if self.logs_manager:
            await self.logs_manager.info(f"Extracted {len(links)} links from {len(elements)} elements")
        return links

    # ===================
    # DOM Tree Methods
    # ===================
    async def get_dom_tree(self, highlight: bool = False, max_highlight: int = 75) -> DOMElementNode:
        """Get DOM tree with optional highlighting."""
        if self.logs_manager:
            await self.logs_manager.info(f"Building DOM tree (highlight={highlight}, max_highlight={max_highlight})")
            
        # Inject logging bridge if needed
        await self._inject_logging_bridge()
            
        with open(self.js_path, "r", encoding="utf-8") as f:
            js_code = f.read()

        script = f"""
        (() => {{
            {js_code}
            return buildDomTree(document.body, {str(highlight).lower()}, {max_highlight});
        }})();
        """

        try:
            tree_data = await self.page.evaluate(script)
            if self.logs_manager:
                await self.logs_manager.info("Successfully built DOM tree")
            return DOMElementNode.from_dict(tree_data)
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to build DOM tree: {str(e)}")
            raise

    async def get_clickable_elements(self, highlight: bool = True, max_highlight: int = 75) -> List[DOMElementNode]:
        """Get clickable elements with optional highlighting."""
        if self.logs_manager:
            await self.logs_manager.info("Finding clickable elements in DOM tree")
            
        try:
            dom_tree = await self.get_dom_tree(highlight=highlight, max_highlight=max_highlight)
            clickable = dom_tree.find_clickable_elements()
            
            if self.logs_manager:
                await self.logs_manager.info(f"Found {len(clickable)} clickable elements")
            return clickable
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to find clickable elements: {str(e)}")
            raise

    async def refresh_highlights(self, interval_sec: float = 2.0, iterations: int = 5) -> None:
        """Refresh element highlights periodically."""
        if self.logs_manager:
            await self.logs_manager.info(f"Starting highlight refresh cycle ({iterations} iterations)")
            
        try:
            for i in range(iterations):
                if self.logs_manager:
                    await self.logs_manager.debug(f"Refresh iteration {i+1}/{iterations}")
                await self.get_clickable_elements(highlight=True, max_highlight=75)
                await self.page.wait_for_timeout(int(interval_sec * 1000))
                
            if self.logs_manager:
                await self.logs_manager.info("Completed highlight refresh cycle")
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to refresh highlights: {str(e)}")
            raise
