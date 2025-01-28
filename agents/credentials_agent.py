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

CAPTCHA Handling Strategy:
------------------------
Current Implementation:
1. Image-based CAPTCHA via 2captcha
2. Manual fallback with screenshot

Planned Enhancements (MVP):
1. ReCAPTCHA Support
   - Checkbox detection and interaction
   - Site key extraction for v2/v3
   - Token injection post-solution
   - Puzzle detection and handling

2. Alternative Services Integration
   - AntiCaptcha support
   - CapMonster integration
   - hCaptcha solver capability

3. Enhanced Fallback Strategy
   - Progressive fallback chain
   - User notification system
   - CLI-based manual solving
   - Session preservation

4. Puzzle-Specific Handling
   - Traffic light recognition
   - Image grid processing
   - Invisible reCAPTCHA support
   - Dynamic puzzle type detection

Future Considerations:
--------------------
1. Machine Learning Integration
   - Local puzzle solving capability
   - Pattern recognition for common CAPTCHAs
   - Success rate optimization

2. Rate Limiting & Recovery
   - Smart retry mechanisms
   - IP rotation support
   - Session preservation
   - Failure analysis

3. Enterprise Features
   - Custom solver integration
   - Analytics and reporting
   - Cost optimization
   - Performance metrics

Notes:
------
- CAPTCHA handling should be non-blocking when possible
- Maintain clear separation between solver services
- Implement proper error recovery
- Track solver performance metrics
- Consider cost vs. speed tradeoffs
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

        # Future service keys
        self.anti_captcha_key = os.getenv("ANTI_CAPTCHA_API_KEY", "")
        self.capmonster_key = os.getenv("CAPMONSTER_API_KEY", "")
        self.hcaptcha_key = os.getenv("HCAPTCHA_API_KEY", "")

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

    async def detect_captcha_type(self, page_content: str) -> str:
        """
        Future method: Detect the type of CAPTCHA present on the page.
        Returns: 'image', 'recaptcha_v2', 'recaptcha_v3', 'hcaptcha', or 'unknown'
        """
        # TODO: Implement CAPTCHA type detection
        return "image"  # Default to image-based CAPTCHA for now

    async def handle_recaptcha_v2(self, site_key: str, page_url: str) -> Optional[str]:
        """
        Future method: Handle reCAPTCHA v2 using 2captcha or alternative services.
        """
        if self.captcha_handler == "2captcha" and self.two_captcha_key:
            # TODO: Implement reCAPTCHA v2 handling
            pass
        return None

    async def handle_recaptcha_checkbox(self) -> bool:
        """
        Future method: Handle simple reCAPTCHA checkbox clicking.
        Returns True if successful, False if puzzle appears.
        """
        if not self.dom_service:
            return False
        # TODO: Implement checkbox detection and clicking
        return False

    async def _handle_captcha_anti_captcha(self, captcha_type: str, **kwargs) -> Optional[str]:
        """
        Future method: Integration with Anti-Captcha service.
        """
        if not self.anti_captcha_key:
            return None
        # TODO: Implement Anti-Captcha integration
        return None

    async def _handle_captcha_capmonster(self, captcha_type: str, **kwargs) -> Optional[str]:
        """
        Future method: Integration with CapMonster service.
        """
        if not self.capmonster_key:
            return None
        # TODO: Implement CapMonster integration
        return None

    async def extract_site_key(self) -> Optional[str]:
        """
        Future method: Extract reCAPTCHA site key from the page.
        """
        if not self.dom_service:
            return None
        # TODO: Implement site key extraction
        return None

    async def inject_captcha_token(self, token: str) -> bool:
        """
        Future method: Inject solved CAPTCHA token into the page.
        """
        if not self.dom_service:
            return False
        # TODO: Implement token injection
        return False

    async def handle_puzzle_captcha(self) -> Optional[str]:
        """
        Future method: Handle advanced puzzle-based CAPTCHAs.
        """
        # TODO: Implement puzzle CAPTCHA handling
        return await self._handle_captcha_manual("puzzle_selector")

    async def verify_captcha_success(self) -> bool:
        """
        Future method: Verify if CAPTCHA was successfully solved.
        """
        if not self.dom_service:
            return False
        # TODO: Implement success verification
        return False

