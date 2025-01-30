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
- LogsManager: For asynchronous logging

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
   - hCaptcha capability

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
from typing import Optional, Tuple
from PIL import Image
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from constants import TimingConstants, Selectors, Messages
from utils.dom.dom_service import DomService
from locators.linkedin_locators import LinkedInLocators
from storage.logs_manager import LogsManager

class CredentialsAgent:
    def __init__(self, settings: dict, dom_service: Optional[DomService] = None, logs_manager: Optional[LogsManager] = None):
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

        # Store LogsManager instance
        self.logs_manager = logs_manager

        # Define success selectors for different scenarios
        self.success_selectors = {
            'login': LinkedInLocators.LOGGED_IN_INDICATOR,
            'captcha': LinkedInLocators.CAPTCHA_SUCCESS,
            'form': LinkedInLocators.FORM_SUCCESS
        }

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

    async def handle_captcha(self, captcha_selector: str, success_selector: str = None) -> Optional[str]:
        """
        Main captcha handling logic with AI Navigator coordination.
        
        Args:
            captcha_selector (str): Selector for the CAPTCHA element
            success_selector (str, optional): Selector to verify CAPTCHA success. 
                                           If not provided, uses default from LinkedInLocators
        """
        if not self.dom_service:
            if self.logs_manager:
                await self.logs_manager.error("[CredentialsAgent] No DomService provided. Cannot handle captcha.")
            return None

        # Use provided success selector or default from locators
        success_selector = success_selector or self.success_selectors['captcha']
        if self.logs_manager:
            await self.logs_manager.debug(f"[CredentialsAgent] Using success selector: {success_selector}")

        try:
            # 1. Initial detection
            await self.dom_service.wait_for_selector(captcha_selector, timeout=self.default_timeout)
            await asyncio.sleep(TimingConstants.ACTION_DELAY)
            
            # 2. Check if it's a rate-limit related CAPTCHA
            rate_limited = await self.dom_service.check_element_present(
                '.rate-limit-message, .too-many-requests',
                timeout=1000
            )
            if rate_limited:
                if self.logs_manager:
                    await self.logs_manager.warning("[CredentialsAgent] Rate limiting detected with CAPTCHA")
                await asyncio.sleep(TimingConstants.RATE_LIMIT_DELAY)

            # 3. Determine CAPTCHA type
            captcha_type = await self._detect_captcha_type()
            if self.logs_manager:
                await self.logs_manager.info(f"[CredentialsAgent] Detected CAPTCHA type: {captcha_type}")

            # 4. Try automated solution based on type
            solution = None
            if captcha_type == "recaptcha_v2":
                site_key = await self.extract_site_key()
                if site_key:
                    solution = await self.handle_recaptcha_v2(site_key, await self.dom_service.page.url)
            elif captcha_type == "image":
                if self.captcha_handler == "2captcha" and self.two_captcha_key:
                    solution = await self._handle_captcha_2captcha(captcha_selector)

            # 5. If automated solution failed, try manual
            if not solution:
                solution = await self._handle_captcha_manual(captcha_selector)

            # 6. Verify solution success
            if solution:
                await asyncio.sleep(TimingConstants.ACTION_DELAY)
                success = await self.verify_captcha_success(success_selector)
                if not success:
                    if self.logs_manager:
                        await self.logs_manager.warning("[CredentialsAgent] CAPTCHA solution verification failed")
                    return None

            return solution

        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"[CredentialsAgent] CAPTCHA handling error: {str(e)}")
            return None

    async def _detect_captcha_type(self) -> str:
        """
        Detect the type of CAPTCHA present on the page.
        
        Returns:
            str: 'image', 'recaptcha_v2', 'recaptcha_v3', 'hcaptcha', or 'unknown'
        """
        try:
            # Check for reCAPTCHA v2
            recaptcha_v2 = await self.dom_service.check_element_present(
                '.g-recaptcha, iframe[title*="reCAPTCHA"]',
                timeout=1000
            )
            if recaptcha_v2:
                return "recaptcha_v2"

            # Check for reCAPTCHA v3
            recaptcha_v3 = await self.dom_service.evaluate_script(
                'document.querySelector("script[src*=\'recaptcha/releases/v3\']") !== null'
            )
            if recaptcha_v3:
                return "recaptcha_v3"

            # Check for hCaptcha
            hcaptcha = await self.dom_service.check_element_present(
                '.h-captcha, iframe[src*="hcaptcha.com"]',
                timeout=1000
            )
            if hcaptcha:
                return "hcaptcha"

            # Check for image CAPTCHA
            image_captcha = await self.dom_service.check_element_present(
                'img[alt*="CAPTCHA"], img.captcha__image',
                timeout=1000
            )
            if image_captcha:
                return "image"

            return "unknown"

        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"[CredentialsAgent] Error detecting CAPTCHA type: {str(e)}")
            return "unknown"

    async def verify_captcha_success(self, success_selector: str = None) -> bool:
        """
        Verify if CAPTCHA was successfully solved.
        
        Args:
            success_selector (str, optional): Selector to verify CAPTCHA success.
                                           If not provided, uses default from LinkedInLocators
        """
        if not self.dom_service:
            if self.logs_manager:
                await self.logs_manager.error("[CredentialsAgent] No DomService - cannot verify login properly.")
            return False

        # Use provided success selector or default from locators
        success_selector = success_selector or self.success_selectors['captcha']
        if self.logs_manager:
            await self.logs_manager.debug(f"[CredentialsAgent] Verifying captcha with selector: {success_selector}")

        try:
            await self.dom_service.wait_for_selector(success_selector, timeout=self.default_timeout)
            await asyncio.sleep(TimingConstants.PAGE_TRANSITION_DELAY)
            
            if self.logs_manager:
                await self.logs_manager.info("[CredentialsAgent] CAPTCHA verification successful")
            return True
            
        except PlaywrightTimeoutError:
            if self.logs_manager:
                await self.logs_manager.warning("[CredentialsAgent] CAPTCHA verification failed - success selector not found")
            return False

    async def _handle_captcha_2captcha(self, captcha_selector: str) -> Optional[str]:
        """Use 2captcha service to solve the captcha."""
        if not self.dom_service:
            return None

        if self.logs_manager:
            await self.logs_manager.info("[CredentialsAgent] Attempting 2captcha solution...")
        await asyncio.sleep(TimingConstants.ACTION_DELAY)

        try:
            # Get the captcha element screenshot
            await asyncio.sleep(TimingConstants.SCREENSHOT_DELAY)
            img_bytes = await self.dom_service.screenshot_element(captcha_selector)
            if not img_bytes:
                if self.logs_manager:
                    await self.logs_manager.error("[CredentialsAgent] Could not screenshot captcha.")
                return None

            solution_text = await self._upload_to_2captcha(img_bytes)
            if solution_text:
                if self.logs_manager:
                    await self.logs_manager.info(f"[CredentialsAgent] 2captcha solution: {solution_text}")
                await asyncio.sleep(TimingConstants.ACTION_DELAY)
                return solution_text
            else:
                if self.logs_manager:
                    await self.logs_manager.warning("[CredentialsAgent] 2captcha returned no solution.")
                return None

        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"[CredentialsAgent] 2captcha solving error: {e}")
            return None

    async def _upload_to_2captcha(self, image_data: bytes) -> Optional[str]:
        """Handle the 2captcha API calls."""
        if not self.two_captcha_key:
            if self.logs_manager:
                await self.logs_manager.error("[CredentialsAgent] No TWO_CAPTCHA_API_KEY provided.")
            return None

        if self.logs_manager:
            await self.logs_manager.info("[CredentialsAgent] Uploading captcha to 2captcha...")
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
                if self.logs_manager:
                    await self.logs_manager.error(f"[CredentialsAgent] 2captcha upload error: {upload_resp['request']}")
                return None

            captcha_id = upload_resp["request"]
            if self.logs_manager:
                await self.logs_manager.debug(f"[CredentialsAgent] 2captcha captcha_id: {captcha_id}")

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
                    if self.logs_manager:
                        await self.logs_manager.debug(f"[CredentialsAgent] 2captcha still solving, attempt: {attempt + 1}")
                    continue

                if self.logs_manager:
                    await self.logs_manager.error(f"[CredentialsAgent] 2captcha error: {check_resp['request']}")
                return None

            if self.logs_manager:
                await self.logs_manager.error(f"[CredentialsAgent] 2captcha timed out after {max_attempts} attempts.")
            return None

        except Exception as ex:
            if self.logs_manager:
                await self.logs_manager.error(f"[CredentialsAgent] 2captcha exception: {ex}")
            return None

    async def _handle_captcha_manual(self, captcha_selector: str) -> Optional[str]:
        """Manual fallback for captcha solving."""
        if not self.dom_service:
            return None

        if self.logs_manager:
            await self.logs_manager.info("[CredentialsAgent] Manual captcha solving selected.")
        await asyncio.sleep(TimingConstants.ACTION_DELAY)

        # Check if the captcha element exists
        element_exists = await self.dom_service.query_selector(captcha_selector)
        if not element_exists:
            if self.logs_manager:
                await self.logs_manager.error("[CredentialsAgent] Captcha element not found for manual input.")
            return None

        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        unique_id = str(uuid.uuid4())
        captcha_path = Path(self.data_dir) / f"temp_captcha_{unique_id}.png"

        await asyncio.sleep(TimingConstants.SCREENSHOT_DELAY)
        await self.dom_service.screenshot_element(captcha_selector, path=str(captcha_path))
        
        if self.logs_manager:
            await self.logs_manager.info(f"\nCAPTCHA image saved to: {captcha_path}")
        
        # This print must remain as it's a user prompt
        solution = input("Please enter CAPTCHA solution (or press Enter to skip): ").strip()

        try:
            captcha_path.unlink(missing_ok=True)
        except OSError:
            if self.logs_manager:
                await self.logs_manager.warning(f"[CredentialsAgent] Could not delete temporary captcha file: {captcha_path}")

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
            if self.logs_manager:
                await self.logs_manager.info(f"[CredentialsAgent] Using existing {platform_name} session")
            return
            
        if self.logs_manager:
            await self.logs_manager.info(f"[CredentialsAgent] (Future) login flow for {platform_name} not implemented.")

    async def verify_login_status(self, success_selector: str = None) -> bool:
        """
        Verify if login was successful.
        
        Args:
            success_selector (str, optional): Selector to verify login success.
                                           If not provided, uses default from LinkedInLocators
        """
        if not self.dom_service:
            if self.logs_manager:
                await self.logs_manager.error("[CredentialsAgent] No DomService - cannot verify login properly.")
            return False

        # Use provided success selector or default from locators
        success_selector = success_selector or self.success_selectors['login']
        if self.logs_manager:
            await self.logs_manager.debug(f"[CredentialsAgent] Verifying login with selector: {success_selector}")

        try:
            await self.dom_service.wait_for_selector(success_selector, timeout=self.default_timeout)
            await asyncio.sleep(TimingConstants.PAGE_TRANSITION_DELAY)
            
            if self.logs_manager:
                await self.logs_manager.info("[CredentialsAgent] Login verification successful")
            return True
            
        except PlaywrightTimeoutError:
            if self.logs_manager:
                await self.logs_manager.warning("[CredentialsAgent] Login verification failed - success selector not found")
            return False

    async def verify_form_submission(self, success_selector: str = None) -> bool:
        """
        Verify if a form submission was successful.
        
        Args:
            success_selector (str, optional): Selector to verify form submission success.
                                           If not provided, uses default from LinkedInLocators
        """
        if not self.dom_service:
            if self.logs_manager:
                await self.logs_manager.error("[CredentialsAgent] No DomService - cannot verify form submission.")
            return False

        # Use provided success selector or default from locators
        success_selector = success_selector or self.success_selectors['form']
        if self.logs_manager:
            await self.logs_manager.debug(f"[CredentialsAgent] Verifying form submission with selector: {success_selector}")

        try:
            await self.dom_service.wait_for_selector(success_selector, timeout=self.default_timeout)
            await asyncio.sleep(TimingConstants.PAGE_TRANSITION_DELAY)
            
            if self.logs_manager:
                await self.logs_manager.info("[CredentialsAgent] Form submission verification successful")
            return True
            
        except PlaywrightTimeoutError:
            if self.logs_manager:
                await self.logs_manager.warning("[CredentialsAgent] Form submission verification failed - success selector not found")
            return False

    async def handle_recaptcha_v2(self, site_key: str, page_url: str) -> Optional[str]:
        """
        Future method: Handle reCAPTCHA v2 using 2captcha or alternative services.
        """
        if self.captcha_handler == "2captcha" and self.two_captcha_key:
            if self.logs_manager:
                await self.logs_manager.info("[CredentialsAgent] Attempting reCAPTCHA v2 solution...")
            # TODO: Implement reCAPTCHA v2 handling
            pass
        return None

    async def handle_recaptcha_checkbox(self) -> bool:
        """
        Future method: Handle simple reCAPTCHA checkbox clicking.
        Returns True if successful, False if puzzle appears.
        """
        if not self.dom_service:
            if self.logs_manager:
                await self.logs_manager.error("[CredentialsAgent] No DomService - cannot handle reCAPTCHA checkbox.")
            return False
        # TODO: Implement checkbox detection and clicking
        return False

    async def _handle_captcha_anti_captcha(self, captcha_type: str, **kwargs) -> Optional[str]:
        """
        Future method: Integration with Anti-Captcha service.
        """
        if not self.anti_captcha_key:
            if self.logs_manager:
                await self.logs_manager.error("[CredentialsAgent] No ANTI_CAPTCHA_API_KEY provided.")
            return None
        # TODO: Implement Anti-Captcha integration
        return None

    async def _handle_captcha_capmonster(self, captcha_type: str, **kwargs) -> Optional[str]:
        """
        Future method: Integration with CapMonster service.
        """
        if not self.capmonster_key:
            if self.logs_manager:
                await self.logs_manager.error("[CredentialsAgent] No CAPMONSTER_API_KEY provided.")
            return None
        # TODO: Implement CapMonster integration
        return None

    async def extract_site_key(self) -> Optional[str]:
        """
        Future method: Extract reCAPTCHA site key from the page.
        """
        if not self.dom_service:
            if self.logs_manager:
                await self.logs_manager.error("[CredentialsAgent] No DomService - cannot extract site key.")
            return None
        # TODO: Implement site key extraction
        return None

    async def inject_captcha_token(self, token: str) -> bool:
        """
        Future method: Inject solved CAPTCHA token into the page.
        """
        if not self.dom_service:
            if self.logs_manager:
                await self.logs_manager.error("[CredentialsAgent] No DomService - cannot inject token.")
            return False
        # TODO: Implement token injection
        return False

    async def handle_puzzle_captcha(self) -> Optional[str]:
        """
        Future method: Handle advanced puzzle-based CAPTCHAs.
        """
        if self.logs_manager:
            await self.logs_manager.info("[CredentialsAgent] Attempting to solve puzzle CAPTCHA...")
        # TODO: Implement puzzle CAPTCHA handling
        return await self._handle_captcha_manual("puzzle_selector")

