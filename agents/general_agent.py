"""
General Purpose Web Automation Agent (Async, Playwright)

Features:
1. Navigation with retry logic (exponential backoff).
2. Click actions, text extraction, typing, scrolling.
3. Optional human-like delays before or after certain actions.
4. Screenshot capturing for debugging / record-keeping.
5. Check element presence (returns bool).
6. Evaluate custom JavaScript/TypeScript on the page if needed.
7. No LLM usage here; purely mechanical. Orchestrator or separate LLM-based agent
   can provide instructions for this agent on unknown domains or fallback scenarios.

DOM Enhancement Updates:
- Add support for locator-based selectors
- Implement selector performance tracking
- Enable AI-driven selector fallbacks
- Track selector success rates
"""

import asyncio
import random
import time
from typing import Any, Optional, List
from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError
)
from constants import TimingConstants, Messages
from utils.telemetry import TelemetryManager
from locators.linkedin_locators import LinkedInLocators  # Future import
from utils.dom.dom_service import DomService
from storage.logs_manager import LogsManager


class GeneralAgent:
    def __init__(
        self,
        dom_service: DomService,
        logs_manager: LogsManager,
        default_timeout: float = TimingConstants.DEFAULT_TIMEOUT,
        min_delay: float = TimingConstants.HUMAN_DELAY_MIN,
        max_delay: float = TimingConstants.HUMAN_DELAY_MAX,
        settings: dict = {}
    ):
        """
        Args:
            dom_service (DomService): The DomService instance for all DOM ops
            logs_manager (LogsManager): The LogsManager instance for logging
            default_timeout (float): Default timeout for waits
            min_delay (float): Min delay for human-like interaction
            max_delay (float): Max delay for human-like interaction
            settings (dict): Additional configuration for telemetry
        """
        self.dom_service = dom_service
        self.logs_manager = logs_manager
        self.page = dom_service.page  # convenience reference
        self.root_page = self.page    # Store reference to original "main" Page
        self.default_timeout = min(default_timeout, TimingConstants.MAX_WAIT_TIME)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.is_paused = False         # Track pause state
        self.telemetry = TelemetryManager(settings)

    # ===================
    # Pause/Resume Methods
    # ===================
    async def pause(self):
        """Pause further actions until 'resume' is called."""
        await self.logs_manager.info(f"[GeneralAgent] {Messages.PAUSE_MESSAGE}")
        self.is_paused = True

    async def resume(self):
        """Resume actions after being paused."""
        await self.logs_manager.info(f"[GeneralAgent] {Messages.RESUME_MESSAGE}")
        self.is_paused = False

    async def _check_if_paused(self):
        """Block execution if paused, resuming only when self.is_paused = False."""
        if self.is_paused:
            await self.logs_manager.info("[GeneralAgent] Currently paused... waiting.")
            while self.is_paused:
                await asyncio.sleep(TimingConstants.POLL_INTERVAL)
            await self.logs_manager.info("[GeneralAgent] Resumed from pause.")

    # ===================
    # Retry Logic
    # ===================
    async def _retry_operation(self, operation: callable, *args: Any, **kwargs: Any):
        """
        Retry an operation with exponential backoff.
        E.g., 2s, 4s, 8s (up to MAX_RETRIES).
        """
        last_exception = None
        for attempt in range(TimingConstants.MAX_RETRIES):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                delay = TimingConstants.BASE_RETRY_DELAY * (2 ** attempt)
                await self.logs_manager.warning(f"[GeneralAgent] {Messages.RETRY_MESSAGE.format(attempt+1, TimingConstants.MAX_RETRIES, e)}")
                await self.logs_manager.info(f"[GeneralAgent] Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
        error_msg = f"[GeneralAgent] All retries failed. Last error: {last_exception}"
        await self.logs_manager.error(error_msg)
        raise Exception(error_msg)

    async def _navigate_operation(self, url: str):
        """
        Operation used by _retry_operation to navigate to a URL.
        Uses a shorter timeout to prevent indefinite waits.
        """
        await self._human_delay()
        try:
            async with asyncio.timeout(TimingConstants.MAX_WAIT_TIME / 1000):
                return await self.dom_service.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=TimingConstants.MAX_WAIT_TIME
                )
        except asyncio.TimeoutError:
            await self.logs_manager.warning(f"[GeneralAgent] Navigation to {url} exceeded {TimingConstants.MAX_WAIT_TIME}ms limit. Proceeding anyway.")
            return None

    async def _human_delay(self, min_sec: float = None, max_sec: float = None):
        """
        Short random delay to mimic human-like interaction.
        If not specified, uses self.min_delay / self.max_delay.
        """
        if min_sec is None:
            min_sec = self.min_delay
        if max_sec is None:
            max_sec = self.max_delay
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    def _current_time_ms(self) -> int:
        """Helper method to get current time in milliseconds."""
        return int(time.time() * 1000)

    # -------------------------------------------------------------------------
    # Public Methods - Navigation & Basic Interactions
    # -------------------------------------------------------------------------
    async def navigate_to(self, url: str):
        """Navigate to a specific URL with up to MAX_RETRIES attempts."""
        await self._check_if_paused()
        result = await self._retry_operation(self._navigate_operation, url)
        await asyncio.sleep(TimingConstants.PAGE_TRANSITION_DELAY)
        return result

    async def click_element(self, selector: str):
        """
        Click element with fallback to LinkedInLocators if direct approach fails.
        """
        await self._check_if_paused()
        try:
            await self._human_delay()
            await self.logs_manager.debug(f"[GeneralAgent] Attempting to click element: {selector}")
            await self.dom_service.click_element(selector)
            await self.logs_manager.debug(f"[GeneralAgent] Successfully clicked element: {selector}")
        except Exception as e:
            await self.logs_manager.warning(f"[GeneralAgent] Direct click failed: {e}")
            # Domain-specific fallback
            try:
                dom_selector = await LinkedInLocators.get_element(
                    self.page, 
                    selector,
                    dom_fallback=True
                )
                if dom_selector:
                    await self.logs_manager.info(f"[GeneralAgent] Using fallback selector: {dom_selector}")
                    await self.dom_service.click_element(dom_selector)
                    await self.logs_manager.debug(f"[GeneralAgent] Successfully clicked with fallback selector")
                else:
                    error_msg = f"[GeneralAgent] Both direct click and fallback failed for '{selector}'"
                    await self.logs_manager.error(error_msg)
                    raise Exception(error_msg)
            except Exception as e:
                error_msg = f"[GeneralAgent] Click operation failed completely: {e}"
                await self.logs_manager.error(error_msg)
                raise Exception(error_msg)

    async def extract_text(self, selector: str) -> str:
        """Extract text from an element."""
        await self._check_if_paused()
        try:
            await self._human_delay()
            await self.logs_manager.debug(f"[GeneralAgent] Attempting to extract text from: {selector}")
            element = await self.dom_service.wait_for_selector(selector, timeout=self.default_timeout)
            if not element:
                error_msg = f"[GeneralAgent] No element found for {selector}"
                await self.logs_manager.error(error_msg)
                raise Exception(error_msg)
            text = await element.text_content()
            await asyncio.sleep(TimingConstants.ACTION_DELAY)
            await self.logs_manager.debug(f"[GeneralAgent] Successfully extracted text from: {selector}")
            return text or ""
        except Exception as e:
            error_msg = f"[GeneralAgent] Failed to extract text from '{selector}': {e}"
            await self.logs_manager.error(error_msg)
            raise Exception(error_msg)

    async def wait_for_text(self, selector: str, expected_text: str, timeout: Optional[float] = None) -> bool:
        """Wait until expected_text is found within element text."""
        await self._check_if_paused()
        use_timeout = min(timeout if timeout is not None else self.default_timeout, TimingConstants.MAX_WAIT_TIME)
        
        await self.logs_manager.debug(f"[GeneralAgent] Waiting for text '{expected_text}' in selector: {selector}")
        end_time = self._current_time_ms() + use_timeout
        while self._current_time_ms() < end_time:
            try:
                current_text = await self.extract_text(selector)
                if expected_text in current_text:
                    await self.logs_manager.debug(f"[GeneralAgent] Found expected text: '{expected_text}'")
                    return True
            except:
                pass
            await asyncio.sleep(0.5)
        
        error_msg = f"[GeneralAgent] Timed out waiting for text '{expected_text}' in '{selector}'"
        await self.logs_manager.error(error_msg)
        raise Exception(error_msg)

    async def type_text(self, selector: str, text: str, clear_first: bool = True) -> bool:
        """Type text into an input or textarea field."""
        await self._check_if_paused()
        try:
            await self._human_delay()
            await self.logs_manager.debug(f"[GeneralAgent] Typing text into: {selector}")
            await self.dom_service.type_text(selector, text, clear_first=clear_first)
            await self.logs_manager.debug(f"[GeneralAgent] Successfully typed text into: {selector}")
            return True
        except Exception as e:
            error_msg = f"[GeneralAgent] Failed to type text into '{selector}': {e}"
            await self.logs_manager.error(error_msg)
            raise Exception(error_msg)

    async def scroll_to_bottom(self, step: int = 200, pause: float = TimingConstants.INFINITE_SCROLL_DELAY):
        """
        Scroll to the bottom of the page in increments (simulating human scroll).
        
        Args:
            step (int): How many pixels to scroll each step.
            pause (float): Delay in seconds between each scroll step.
        """
        await self._check_if_paused()
        await self._human_delay()
        await self.logs_manager.debug(f"[GeneralAgent] Starting incremental scroll to bottom (step={step}px)")
        await self.dom_service.scroll_to_bottom(step=step, pause=pause)
        await self.logs_manager.debug("[GeneralAgent] Completed scrolling to bottom")

    async def scroll_to_element(self, selector: str):
        """
        Scroll until the element is visible in the viewport.
        """
        await self._human_delay()
        try:
            await self.logs_manager.debug(f"[GeneralAgent] Scrolling to element: {selector}")
            await self.dom_service.scroll_to_element(selector)
            await self.logs_manager.debug(f"[GeneralAgent] Successfully scrolled to element: {selector}")
        except Exception as e:
            error_msg = f"[GeneralAgent] Could not scroll to element '{selector}': {e}"
            await self.logs_manager.error(error_msg)
            raise Exception(error_msg)

    async def take_screenshot(self, path: str):
        """
        Take a full-page screenshot and save to the given path.
        """
        await self._human_delay()
        try:
            await self.logs_manager.debug(f"[GeneralAgent] Taking screenshot: {path}")
            await self.dom_service.take_screenshot(path=path, full_page=True)
            await self.logs_manager.info(f"[GeneralAgent] Screenshot saved to: {path}")
        except Exception as e:
            error_msg = f"[GeneralAgent] Failed to take screenshot: {e}"
            await self.logs_manager.error(error_msg)
            raise Exception(error_msg)

    async def check_element_present(self, selector: str, timeout: Optional[float] = None) -> bool:
        """
        Check if an element is present (without throwing an exception).
        
        Returns:
            True if element is found within the given timeout, else False.
        """
        use_timeout = timeout if timeout is not None else self.default_timeout
        await self.logs_manager.debug(f"[GeneralAgent] Checking for element presence: {selector}")
        result = await self.dom_service.check_element_present(selector, timeout=use_timeout)
        if result:
            await self.logs_manager.debug(f"[GeneralAgent] Element found: {selector}")
        else:
            await self.logs_manager.debug(f"[GeneralAgent] Element not found: {selector}")
        return result

    async def evaluate_script(self, script: str) -> Any:
        """
        Evaluate arbitrary JavaScript in the page context.
        """
        await self._human_delay()
        await self.logs_manager.debug("[GeneralAgent] Evaluating JavaScript")
        try:
            result = await self.dom_service.evaluate_script(script)
            await self.logs_manager.debug("[GeneralAgent] JavaScript evaluation completed")
            return result
        except Exception as e:
            error_msg = f"[GeneralAgent] JavaScript evaluation failed: {e}"
            await self.logs_manager.error(error_msg)
            raise Exception(error_msg)

    async def extract_links(self, selector: str = "a") -> List[str]:
        """
        Extract all 'href' attributes from elements matching selector.
        """
        await self._human_delay()
        try:
            await self.logs_manager.debug(f"[GeneralAgent] Extracting links with selector: {selector}")
            links = await self.dom_service.extract_links(selector)
            await self.logs_manager.debug(f"[GeneralAgent] Successfully extracted {len(links)} links")
            return links
        except Exception as e:
            error_msg = f"[GeneralAgent] Failed to extract links with selector '{selector}': {e}"
            await self.logs_manager.error(error_msg)
            raise Exception(error_msg)

    async def switch_to_iframe(self, iframe_selector: str):
        """
        Switch 'self.page' context to the content_frame of an iframe.
        Example usage: await self.switch_to_iframe("iframe#captcha-frame")
        """
        await self._human_delay()
        try:
            await self.logs_manager.debug(f"[GeneralAgent] Switching to iframe: {iframe_selector}")
            await self.dom_service.switch_to_iframe(iframe_selector)
            # Update our page reference to match dom_service
            self.page = self.dom_service.page
            await self.logs_manager.debug("[GeneralAgent] Successfully switched to iframe")
        except Exception as e:
            error_msg = f"[GeneralAgent] Failed to switch to iframe '{iframe_selector}': {e}"
            await self.logs_manager.error(error_msg)
            raise Exception(error_msg)

    async def switch_back_to_main_frame(self):
        """
        Switch back to the original root page context.
        Uses stored reference to avoid frame navigation issues.
        """
        await self._human_delay()
        await self.logs_manager.debug("[GeneralAgent] Switching back to main frame")
        self.dom_service.switch_back_to_main_frame(self.root_page)
        self.page = self.root_page
        await self.logs_manager.debug("[GeneralAgent] Successfully switched to main frame")

    async def drag_and_drop(self, source_selector: str, target_selector: str):
        """
        Drag from source_selector to target_selector.
        """
        await self._human_delay()
        try:
            await self.dom_service.drag_and_drop(source_selector, target_selector, hold_delay=0.5)
        except Exception as e:
            raise Exception(f"[GeneralAgent] Drag-and-drop from '{source_selector}' to '{target_selector}' failed: {e}")

    async def accept_cookies(self, accept_button_selector: str) -> bool:
        """
        Click the 'Accept Cookies' button if present.
        Returns True if clicked, False if not found or failed.
        """
        await self._human_delay()
        found = await self.dom_service.check_element_present(accept_button_selector, timeout=3000)
        if found:
            try:
                await self.click_element(accept_button_selector)
                print("[GeneralAgent] Cookies accepted.")
                return True
            except Exception as e:
                print(f"[GeneralAgent] Failed to click accept cookies button: {e}")
                return False
        else:
            print("[GeneralAgent] No cookies accept button found.")
            return False

    async def wait_for_condition(self, condition_fn, timeout: Optional[float] = None, poll_interval: float = 0.5) -> bool:
        """
        Wait for a custom condition function to return True.
        
        Args:
            condition_fn: Async function that returns bool
            timeout: Optional custom timeout in ms
            poll_interval: How often to check the condition in seconds
            
        Returns:
            True if condition met within timeout
            
        Raises:
            Exception if condition not met within timeout
        """
        await self._check_if_paused()
        use_timeout = min(timeout if timeout is not None else self.default_timeout, TimingConstants.MAX_WAIT_TIME)
        
        end_time = self._current_time_ms() + use_timeout
        while self._current_time_ms() < end_time:
            try:
                if await condition_fn():
                    return True
            except Exception as e:
                print(f"[GeneralAgent] Error checking condition: {e}")
            await asyncio.sleep(poll_interval)
            
        raise Exception("[GeneralAgent] Timed out waiting for condition")
