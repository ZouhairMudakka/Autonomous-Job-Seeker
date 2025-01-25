"""
Credentials Agent

Architecture:
------------
This module maintains separation of concerns:

1. Credentials Logic (This Module)
   - CAPTCHA handling strategy
   - Login flow orchestration
   - Credential management
   - Error recovery

2. DOM Interactions (via DomService)
   - Element discovery and interaction
   - Screenshots and visual feedback
   - Basic DOM operations
   - Element state verification

3. Platform-Specific Selectors (via LinkedInLocators)
   - Centralized selector definitions
   - Platform-specific element paths
   - Selector versioning and fallbacks

Dependencies:
------------
- DomService: Handles all direct DOM interactions
- LinkedInLocators: Provides centralized selector definitions
- asyncio: For asynchronous operations
- requests: For 2captcha API calls (remains synchronous)
"""

import os
import random
import asyncio
import requests
import base64
import uuid
from pathlib import Path
from typing import Optional
from PIL import Image
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from constants import TimingConstants, Selectors, Messages
from utils.dom.dom_service import DomService
from locators.linkedin_locators import LinkedInLocators

class CredentialsAgent:
    def __init__(self, settings: dict, dom_service: Optional[DomService] = None):
        """Initialize the credentials agent with settings and optional DomService."""
        self.settings = settings
        self.captcha_handler = settings.get("captcha_handler", "manual")
        self.data_dir = settings.get("data_dir", "./data")
        self.two_captcha_key = os.getenv("TWO_CAPTCHA_API_KEY", "")
        
        # Get LinkedIn-specific settings
        linkedin_settings = settings.get('linkedin', {})
        self.default_timeout = linkedin_settings.get('default_timeout', TimingConstants.DEFAULT_TIMEOUT)
        self.min_delay = linkedin_settings.get('min_delay', TimingConstants.HUMAN_DELAY_MIN)
        self.max_delay = linkedin_settings.get('max_delay', TimingConstants.HUMAN_DELAY_MAX)
        
        # Check if we're using an existing browser session
        browser_settings = settings.get('browser', {})
        self.attach_mode = browser_settings.get('attach_existing', False)

        # Store DomService instance
        self.dom_service = dom_service

    async def random_delay(self, min_sec: float = None, max_sec: float = None):
        """Introduce a random delay to mimic human-like interaction."""
        min_sec = min_sec if min_sec is not None else self.min_delay
        max_sec = max_sec if max_sec is not None else self.max_delay
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    async def handle_captcha(self, captcha_selector: str) -> Optional[str]:
        """Main captcha handling logic."""
        if not self.dom_service:
            print("[CredentialsAgent] No DomService provided. Cannot handle captcha.")
            return None

        try:
            await self.dom_service.wait_for_selector(captcha_selector, timeout=self.default_timeout)
            await asyncio.sleep(TimingConstants.ACTION_DELAY)
        except PlaywrightTimeoutError:
            print("[CredentialsAgent] No CAPTCHA detected.")
            return None

        print("[CredentialsAgent] CAPTCHA detected.")
        await asyncio.sleep(TimingConstants.MODAL_TRANSITION_DELAY)

        if self.captcha_handler == "2captcha" and self.two_captcha_key:
            solution = await self._handle_captcha_2captcha(captcha_selector)
            if solution:
                await asyncio.sleep(TimingConstants.ACTION_DELAY)
                return solution

        return await self._handle_captcha_manual(captcha_selector)

    async def _handle_captcha_2captcha(self, captcha_selector: str) -> Optional[str]:
        """Use 2captcha service to solve the captcha."""
        if not self.dom_service:
            return None

        print("[CredentialsAgent] Attempting 2captcha solution...")
        await asyncio.sleep(TimingConstants.ACTION_DELAY)

        try:
            # Get the captcha element screenshot
            await asyncio.sleep(TimingConstants.SCREENSHOT_DELAY)
            img_bytes = await self.dom_service.screenshot_element(captcha_selector)
            if not img_bytes:
                print("[CredentialsAgent] Could not screenshot captcha.")
                return None

            solution_text = await self._upload_to_2captcha(img_bytes)
            if solution_text:
                print(f"[CredentialsAgent] 2captcha solution: {solution_text}")
                await asyncio.sleep(TimingConstants.ACTION_DELAY)
                return solution_text
            else:
                print("[CredentialsAgent] 2captcha returned no solution.")
                return None

        except Exception as e:
            print(f"[CredentialsAgent] 2captcha solving error: {e}")
            return None

    async def _upload_to_2captcha(self, image_data: bytes) -> Optional[str]:
        """Handle the 2captcha API calls."""
        if not self.two_captcha_key:
            print("[CredentialsAgent] No TWO_CAPTCHA_API_KEY provided.")
            return None

        print("[CredentialsAgent] Uploading captcha to 2captcha...")
        await asyncio.sleep(TimingConstants.ACTION_DELAY)

        try:
            img_b64 = base64.b64encode(image_data).decode("utf-8")

            upload_resp = requests.post(
                "http://2captcha.com/in.php",
                data={
                    "key": self.two_captcha_key,
                    "method": "base64",
                    "body": img_b64,
                    "json": 1
                }
            ).json()

            if upload_resp["status"] == 0:
                print("[CredentialsAgent] 2captcha upload error:", upload_resp["request"])
                return None

            captcha_id = upload_resp["request"]
            print(f"[CredentialsAgent] 2captcha captcha_id: {captcha_id}")

            max_attempts = int(TimingConstants.MAX_WAIT_TIME / (TimingConstants.POLL_INTERVAL * 1000))
            for attempt in range(max_attempts):
                await asyncio.sleep(TimingConstants.POLL_INTERVAL)
                check_resp = requests.get(
                    "http://2captcha.com/res.php",
                    params={
                        "key": self.two_captcha_key,
                        "action": "get",
                        "id": captcha_id,
                        "json": 1
                    }
                ).json()

                if check_resp["status"] == 1:
                    await asyncio.sleep(TimingConstants.ACTION_DELAY)
                    return check_resp["request"]

                if check_resp["request"] == "CAPCHA_NOT_READY":
                    print(f"[CredentialsAgent] 2captcha still solving, attempt: {attempt + 1}")
                    continue

                print("[CredentialsAgent] 2captcha error:", check_resp["request"])
                return None

            print(f"[CredentialsAgent] 2captcha timed out after {max_attempts} attempts.")
            return None

        except Exception as ex:
            print(f"[CredentialsAgent] 2captcha exception: {ex}")
            return None

    async def _handle_captcha_manual(self, captcha_selector: str) -> Optional[str]:
        """Manual fallback for captcha solving."""
        if not self.dom_service:
            return None

        print("[CredentialsAgent] Manual captcha solving selected.")
        await asyncio.sleep(TimingConstants.ACTION_DELAY)

        # Check if the captcha element exists
        element_exists = await self.dom_service.query_selector(captcha_selector)
        if not element_exists:
            print("[CredentialsAgent] Captcha element not found for manual input.")
            return None

        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        unique_id = str(uuid.uuid4())
        captcha_path = Path(self.data_dir) / f"temp_captcha_{unique_id}.png"

        await asyncio.sleep(TimingConstants.SCREENSHOT_DELAY)
        await self.dom_service.screenshot_element(captcha_selector, path=str(captcha_path))
        print(f"\nCAPTCHA image saved to: {captcha_path}")
        solution = input("Please enter CAPTCHA solution (or press Enter to skip): ").strip()

        try:
            captcha_path.unlink(missing_ok=True)
        except OSError:
            pass

        if solution:
            await asyncio.sleep(TimingConstants.ACTION_DELAY)
            return solution
        return None

    async def login_to_platform(self, platform_name: str):
        """
        Future method: automate login for a given platform (LinkedIn, Google, etc.).
        Currently not implemented in MVP because user logs in manually or uses existing session.
        """
        if self.attach_mode:
            print(f"[CredentialsAgent] Using existing {platform_name} session")
            return
            
        print(f"[CredentialsAgent] (Future) login flow for {platform_name} not implemented.")

    async def verify_login_status(self, success_selector: str) -> bool:
        """Verify if login was successful."""
        if not self.dom_service:
            print("[CredentialsAgent] No DomService - cannot verify login properly.")
            return False

        try:
            await self.dom_service.wait_for_selector(success_selector, timeout=self.default_timeout)
            await asyncio.sleep(TimingConstants.PAGE_TRANSITION_DELAY)
            return True
        except PlaywrightTimeoutError:
            return False

