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


class GeneralAgent:
    def __init__(
        self,
        page: Page,
        default_timeout: float = TimingConstants.DEFAULT_TIMEOUT,
        min_delay: float = TimingConstants.HUMAN_DELAY_MIN,
        max_delay: float = TimingConstants.HUMAN_DELAY_MAX
    ):
        """
        Args:
            page (Page): An async Playwright Page instance.
            default_timeout (float): Default timeout in ms for wait_for_selector, etc.
            min_delay (float): Minimum seconds for human-like delay.
            max_delay (float): Maximum seconds for human-like delay.
        """
        self.page = page                # Current active page or frame
        self.root_page = page          # Store reference to original "main" Page
        self.default_timeout = min(default_timeout, TimingConstants.MAX_WAIT_TIME)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.is_paused = False         # Track pause state

    async def pause(self):
        """Pause further actions until 'resume' is called."""
        print(f"[GeneralAgent] {Messages.PAUSE_MESSAGE}")
        self.is_paused = True

    async def resume(self):
        """Resume actions after being paused."""
        print(f"[GeneralAgent] {Messages.RESUME_MESSAGE}")
        self.is_paused = False

    async def _check_if_paused(self):
        """Block execution if paused, resuming only when self.is_paused = False."""
        if self.is_paused:
            print("[GeneralAgent] Currently paused... waiting.")
            while self.is_paused:
                await asyncio.sleep(TimingConstants.POLL_INTERVAL)
            print("[GeneralAgent] Resumed from pause.")

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
                print(f"[GeneralAgent] {Messages.RETRY_MESSAGE.format(attempt+1, TimingConstants.MAX_RETRIES, e)}")
                print(f"[GeneralAgent] Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
        raise Exception(f"[GeneralAgent] All retries failed. Last error: {last_exception}")

    async def _navigate_operation(self, url: str):
        """
        Operation used by _retry_operation to navigate to a URL.
        Uses a shorter timeout to prevent indefinite waits.
        """
        await self._human_delay()
        try:
            async with asyncio.timeout(TimingConstants.MAX_WAIT_TIME / 1000):
                return await self.page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=TimingConstants.MAX_WAIT_TIME
                )
        except asyncio.TimeoutError:
            print(f"[GeneralAgent] Navigation to {url} exceeded {TimingConstants.MAX_WAIT_TIME}ms limit. Proceeding anyway.")
            return None

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    async def navigate_to(self, url: str):
        """
        Navigate to a specific URL with up to MAX_RETRIES attempts.

        Raises:
            Exception if all retries fail.
        """
        await self._check_if_paused()
        result = await self._retry_operation(self._navigate_operation, url)
        await asyncio.sleep(TimingConstants.PAGE_TRANSITION_DELAY)
        return result

    async def click_element(self, selector: str) -> bool:
        """
        Click an element on the page (waits for it to be visible).
        
        Returns:
            True if successful. Raises Exception on failure.
        """
        await self._check_if_paused()
        try:
            await self._human_delay()
            await self.page.wait_for_selector(
                selector,
                state="visible",
                timeout=min(self.default_timeout, TimingConstants.MAX_WAIT_TIME)
            )
            await self.page.click(selector)
            await asyncio.sleep(TimingConstants.ACTION_DELAY)
            return True
        except Exception as e:
            raise Exception(f"[GeneralAgent] Failed to click element '{selector}': {e}")

    async def extract_text(self, selector: str) -> str:
        """
        Extract text from an element.

        Returns:
            The text content of the element.
        Raises:
            Exception if the element can't be found or read.
        """
        await self._check_if_paused()
        try:
            await self._human_delay()
            element = await self.page.wait_for_selector(
                selector,
                state="visible",
                timeout=self.default_timeout
            )
            text = await element.text_content()
            await asyncio.sleep(TimingConstants.ACTION_DELAY)
            return text or ""
        except Exception as e:
            raise Exception(f"[GeneralAgent] Failed to extract text from '{selector}': {e}")

    async def wait_for_text(self, selector: str, expected_text: str, timeout: Optional[float] = None) -> bool:
        """
        Wait until `expected_text` is found within the text of element at `selector`.
        
        Args:
            selector: The element selector to check
            expected_text: The text to wait for
            timeout: Optional custom timeout in ms (uses default_timeout if not specified)
            
        Returns:
            True if found within timeout
            
        Raises:
            Exception if text not found within timeout
        """
        await self._check_if_paused()
        use_timeout = min(timeout if timeout is not None else self.default_timeout, TimingConstants.MAX_WAIT_TIME)
        
        end_time = self._current_time_ms() + use_timeout
        while self._current_time_ms() < end_time:
            try:
                current_text = await self.extract_text(selector)
                if expected_text in current_text:
                    return True
            except:
                pass  # Element might not exist yet
            await asyncio.sleep(0.5)  # Poll every 500ms instead of 1s for more responsiveness
            
        raise Exception(f"[GeneralAgent] Timed out waiting for text '{expected_text}' in '{selector}'")

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

    async def type_text(self, selector: str, text: str, clear_first: bool = True) -> bool:
        """
        Type text into an input or textarea field (optional clearing first).

        Returns:
            True if successful.
        Raises:
            Exception on failure.
        """
        await self._check_if_paused()
        try:
            await self._human_delay()
            field = await self.page.wait_for_selector(
                selector,
                state="visible",
                timeout=self.default_timeout
            )
            if clear_first:
                await field.fill("")
            await self._human_delay()
            await field.type(text)
            return True
        except Exception as e:
            raise Exception(f"[GeneralAgent] Failed to type text into '{selector}': {e}")

    async def scroll_to_bottom(self, step: int = 200, pause: float = TimingConstants.INFINITE_SCROLL_DELAY):
        """
        Scroll to the bottom of the page in increments (simulating human scroll).
        
        Args:
            step (int): How many pixels to scroll each step.
            pause (float): Delay in seconds between each scroll step.
        """
        await self._check_if_paused()
        await self._human_delay()
        current_height = await self.page.evaluate("() => document.body.scrollHeight")
        pos = 0
        while pos < current_height:
            await self._check_if_paused()  # Check pause state during long scroll
            pos += step
            await self.page.mouse.wheel(0, step)
            await asyncio.sleep(pause)
            new_height = await self.page.evaluate("() => document.body.scrollHeight")
            if new_height > current_height:
                current_height = new_height

    async def scroll_to_element(self, selector: str):
        """
        Scroll until the element is visible in the viewport.
        """
        await self._human_delay()
        try:
            element = await self.page.wait_for_selector(selector, timeout=self.default_timeout)
            await element.scroll_into_view_if_needed()
        except PlaywrightTimeoutError:
            raise Exception(f"[GeneralAgent] Could not scroll to element '{selector}' - not found.")

    async def take_screenshot(self, path: str):
        """
        Take a full-page screenshot and save to the given path.
        """
        await self._human_delay()
        try:
            await self.page.screenshot(path=path, full_page=True)
            print(f"[GeneralAgent] Screenshot saved to: {path}")
        except Exception as e:
            raise Exception(f"[GeneralAgent] Failed to take screenshot: {e}")

    async def check_element_present(self, selector: str, timeout: Optional[float] = None) -> bool:
        """
        Check if an element is present (without throwing an exception).
        
        Returns:
            True if element is found within the given timeout, else False.
        """
        use_timeout = timeout if timeout is not None else self.default_timeout
        try:
            await self.page.wait_for_selector(
                selector,
                state="attached",
                timeout=use_timeout
            )
            return True
        except PlaywrightTimeoutError:
            return False

    async def evaluate_script(self, script: str) -> Any:
        """
        Evaluate arbitrary JavaScript in the page context.

        Args:
            script (str): A JS expression or function body to be evaluated.
        
        Returns:
            The result of the evaluation (if any).
        """
        await self._human_delay()
        return await self.page.evaluate(script)

    async def extract_links(self, selector: str = "a") -> List[str]:
        """
        Extract all 'href' attributes from elements matching the provided selector.
        By default, it extracts from all <a> tags on the page.
        
        Returns:
            A list of URLs (strings).
        """
        await self._human_delay()
        try:
            elements = await self.page.query_selector_all(selector)
            links = []
            for el in elements:
                href = await el.get_attribute("href")
                if href:
                    links.append(href)
            return links
        except Exception as e:
            raise Exception(f"[GeneralAgent] Failed to extract links with selector '{selector}': {e}")

    async def switch_to_iframe(self, iframe_selector: str):
        """
        Switch 'self.page' context to the content_frame of an iframe.
        Example usage: await self.switch_to_iframe("iframe#captcha-frame")
        """
        await self._human_delay()
        try:
            frame_element = await self.page.wait_for_selector(
                iframe_selector, 
                timeout=self.default_timeout
            )
            frame = await frame_element.content_frame()
            if not frame:
                raise Exception(f"[GeneralAgent] Could not find content frame for '{iframe_selector}'")
            self.page = frame  # Now 'self.page' is the iframe's frame context
        except PlaywrightTimeoutError:
            raise Exception(f"[GeneralAgent] Timeout waiting for iframe '{iframe_selector}'")
        except Exception as e:
            raise Exception(f"[GeneralAgent] Failed to switch to iframe '{iframe_selector}': {e}")

    async def switch_back_to_main_frame(self):
        """
        Switch back to the original root page context.
        Uses stored reference to avoid frame navigation issues.
        """
        await self._human_delay()
        self.page = self.root_page    # Restore the original top-level Page

    async def drag_and_drop(self, source_selector: str, target_selector: str):
        """
        Drag an element from source_selector to target_selector.
        Useful for puzzle-like CAPTCHAs or site UIs with drag-and-drop.
        """
        await self._human_delay()
        try:
            source = await self.page.wait_for_selector(
                source_selector, 
                timeout=self.default_timeout
            )
            target = await self.page.wait_for_selector(
                target_selector, 
                timeout=self.default_timeout
            )

            # Hover source, mouse down, hover target, mouse up
            await source.hover()
            await self.page.mouse.down()
            await self._human_delay(0.5, 1.0)  # short wait while "holding" the element
            await target.hover()
            await self.page.mouse.up()
        except Exception as e:
            raise Exception(f"[GeneralAgent] Drag-and-drop from '{source_selector}' to '{target_selector}' failed: {e}")

    async def accept_cookies(self, accept_button_selector: str) -> bool:
        """
        Click the 'Accept Cookies' button if present.
        Returns True if the button was clicked, False if not found or failed.
        """
        await self._human_delay()
        found = await self.check_element_present(accept_button_selector, timeout=3000)
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

    # -------------------------------------------------------------------------
    # Internal / Helper Methods
    # -------------------------------------------------------------------------

    def _current_time_ms(self) -> int:
        """Helper method to get current time in milliseconds."""
        return int(time.time() * 1000)
