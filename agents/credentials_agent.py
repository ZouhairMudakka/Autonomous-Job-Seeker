"""
Credentials Management Agent

This agent handles:
1. CAPTCHA challenges (via 2captcha if configured, else manual).
2. (Future) Login flows for various platforms (not active in MVP).
3. (Future) Secure or semi-secure credential storage (placeholder for keyring).

Required Modules:
- os: For environment variables (to fetch TWO_CAPTCHA_API_KEY)
- random: For random delays (to mimic human-like interactions)
- time: For manual sleeps
- requests: For 2captcha API calls
- playwright.sync_api (or async_api) for browser automation
- PIL: For image processing if needed for image-based captchas

Future Plans:
- Reintroduce keyring or more secure credential storage for user logins.
- Implement platform-specific or universal login flows (if user not manually logged in).
- Possibly support more captcha-solving services or reCAPTCHA if needed.
"""

import os
import random
import time
import requests
import base64
import uuid
from pathlib import Path
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from PIL import Image
from typing import Optional
from constants import TimingConstants, Selectors, Messages


class CredentialsAgent:
    def __init__(self, settings: dict):
        """
        Args:
            settings (dict): Configuration dictionary containing:
                {
                    "captcha_handler": "2captcha" or "manual",
                    "data_dir": "./data",  # Folder for saving temp captcha images
                    "linkedin": {
                        "email": str,       # LinkedIn email (if not using attach_mode)
                        "password": str,    # LinkedIn password (if not using attach_mode)
                        "default_timeout": int,
                        "min_delay": float,
                        "max_delay": float
                    },
                    "browser": {
                        "attach_existing": bool,  # Whether using existing browser session
                        ...
                    }
                }
        """
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

    def random_delay(self, min_sec: float = None, max_sec: float = None):
        """
        Introduce a short random delay to mimic human-like interaction.
        Uses settings-based delays if no specific range provided.
        """
        min_sec = min_sec if min_sec is not None else self.min_delay
        max_sec = max_sec if max_sec is not None else self.max_delay
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def handle_captcha(self, page: Page, captcha_selector: str) -> Optional[str]:
        """Main captcha handling logic."""
        try:
            page.wait_for_selector(captcha_selector, timeout=self.default_timeout)
            time.sleep(TimingConstants.ACTION_DELAY)
        except PlaywrightTimeoutError:
            print("[CredentialsAgent] No CAPTCHA detected.")
            return None

        print("[CredentialsAgent] CAPTCHA detected.")
        time.sleep(TimingConstants.MODAL_TRANSITION_DELAY)

        if self.captcha_handler == "2captcha" and self.two_captcha_key:
            solution = self._handle_captcha_2captcha(page, captcha_selector)
            if solution:
                time.sleep(TimingConstants.ACTION_DELAY)
                return solution

        return self._handle_captcha_manual(page, captcha_selector)

    def _handle_captcha_2captcha(self, page: Page, captcha_selector: str) -> Optional[str]:
        """Use 2captcha service to solve the captcha."""
        print("[CredentialsAgent] Attempting 2captcha solution...")
        time.sleep(TimingConstants.ACTION_DELAY)

        try:
            captcha_element = page.query_selector(captcha_selector)
            if not captcha_element:
                print("[CredentialsAgent] Captcha element not found for 2captcha.")
                return None

            time.sleep(TimingConstants.SCREENSHOT_DELAY)
            img_bytes = captcha_element.screenshot()

            solution_text = self._upload_to_2captcha(img_bytes)
            if solution_text:
                print(f"[CredentialsAgent] 2captcha solution: {solution_text}")
                time.sleep(TimingConstants.ACTION_DELAY)
                return solution_text
            else:
                print("[CredentialsAgent] 2captcha returned no solution.")
                return None

        except Exception as e:
            print(f"[CredentialsAgent] 2captcha solving error: {e}")
            return None

    def _upload_to_2captcha(self, image_data: bytes) -> Optional[str]:
        """Handle the 2captcha API calls."""
        if not self.two_captcha_key:
            print("[CredentialsAgent] No TWO_CAPTCHA_API_KEY provided.")
            return None

        print("[CredentialsAgent] Uploading captcha to 2captcha...")
        time.sleep(TimingConstants.ACTION_DELAY)

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
                time.sleep(TimingConstants.POLL_INTERVAL)
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
                    time.sleep(TimingConstants.ACTION_DELAY)
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

    def _handle_captcha_manual(self, page: Page, captcha_selector: str) -> Optional[str]:
        """Manual fallback for captcha solving."""
        print("[CredentialsAgent] Manual captcha solving selected.")
        time.sleep(TimingConstants.ACTION_DELAY)

        captcha_element = page.query_selector(captcha_selector)
        if not captcha_element:
            print("[CredentialsAgent] Captcha element not found for manual input.")
            return None

        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        unique_id = str(uuid.uuid4())
        captcha_path = Path(self.data_dir) / f"temp_captcha_{unique_id}.png"

        time.sleep(TimingConstants.SCREENSHOT_DELAY)
        captcha_element.screenshot(path=str(captcha_path))
        print(f"\nCAPTCHA image saved to: {captcha_path}")
        solution = input("Please enter CAPTCHA solution (or press Enter to skip): ").strip()

        try:
            captcha_path.unlink(missing_ok=True)
        except OSError:
            pass

        if solution:
            time.sleep(TimingConstants.ACTION_DELAY)
            return solution
        return None

    # ------------------------------------------------------------------------
    # Future / Placeholder Methods
    # ------------------------------------------------------------------------
    def login_to_platform(self, page: Page, platform_name: str):
        """
        Future method: automate login for a given platform (LinkedIn, Google, etc.).
        Currently not implemented in MVP because user logs in manually or uses existing session.
        """
        if self.attach_mode:
            print(f"[CredentialsAgent] Using existing {platform_name} session")
            return
            
        print(f"[CredentialsAgent] (Future) login flow for {platform_name} not implemented.")

    def verify_login_status(self, page: Page, success_selector: str) -> bool:
        """Verify if login was successful."""
        try:
            page.wait_for_selector(success_selector, timeout=self.default_timeout)
            time.sleep(TimingConstants.PAGE_TRANSITION_DELAY)
            return True
        except PlaywrightTimeoutError:
            return False
