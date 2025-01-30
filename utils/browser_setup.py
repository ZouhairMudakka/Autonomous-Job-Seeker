"""
Browser Setup Module

Handles browser initialization and configuration for the LinkedIn automation tool.
Supports multiple browsers with special handling for Edge, Chrome, Firefox,
and (optionally) attaching to an existing browser (Chromium-based only).

Features:
- Browser selection (chromium/firefox/edge)
- Attach to existing browser or launch new one
- Headless mode toggle
- Custom user agent
- Cookie persistence (via user data dir)
- Custom viewport size
"""

from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from typing import Optional, Dict, Tuple, Union
import asyncio
from pathlib import Path
import json
import platform
import os
from storage.logs_manager import LogsManager
from utils.telemetry import TelemetryManager

class BrowserSetup:
    # Default paths for different browsers based on OS
    BROWSER_PATHS = {
        'Windows': {
            'edge': r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
            'chrome': r"C:/Program Files/Google/Chrome/Application/chrome.exe",
            # Brave removed per your request
        },
        'Darwin': {  # macOS
            'edge': r"/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            'chrome': r"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            # Brave removed
        },
        'Linux': {
            'edge': '/usr/bin/microsoft-edge',
            'chrome': '/usr/bin/google-chrome'
            # Brave removed
        }
    }

    def __init__(self, settings: Dict, logs_manager: LogsManager):
        """
        Initialize browser configuration.

        Args:
            settings (Dict): 
                Typically loaded from config/settings, containing:
                {
                  "browser": {
                     "type": "edge" or "chrome" or "firefox",
                     "headless": false,
                     "user_agent": "...",
                     "viewport": {"width":1280,"height":720},
                     "cdp_port": 9222,
                     "attach_existing": false,
                     "data_dir": "./data"
                  },
                  "system": {
                     "data_dir": "./data"
                  }
                }
            logs_manager (LogsManager): Instance of LogsManager for async logging
        """
        self.settings = settings.get('browser', {})
        self.telemetry = TelemetryManager(settings)
        self.logs_manager = logs_manager

        # Determine data directory
        data_dir = (
            self.settings.get('data_dir')
            or settings.get('system', {}).get('data_dir')
            or './data'
        )
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Directory for persistent profiles
        self.profiles_dir = self.data_dir / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        # Path for saving cookies (if desired)
        self.cookies_path = self.data_dir.joinpath('cookies/browser_cookies.json')
        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)

        # Basic settings
        self.browser_type: Optional[str] = None
        self.executable_path: Optional[str] = None
        self.headless = self.settings.get('headless', False)
        self.user_agent = self.settings.get('user_agent', '')
        self.viewport = self.settings.get('viewport', {'width': 1280, 'height': 720})

        # For attaching to an existing browser
        self.cdp_port = int(self.settings.get('cdp_port', 9222))
        self.cdp_url = f"http://127.0.0.1:{self.cdp_port}"

    async def _log_info(self, message: str):
        """Helper to log with file/line reference."""
        await self.logs_manager.info(f"[BrowserSetup] {message}")

    def _get_browser_path(self) -> Optional[str]:
        """Get the appropriate browser executable path based on OS and self.browser_type."""
        os_name = platform.system()
        if os_name not in self.BROWSER_PATHS:
            return None
        path = self.BROWSER_PATHS[os_name].get(self.browser_type)
        return path if path and os.path.exists(path) else None

    async def _attach_to_browser(self, playwright) -> Browser:
        """
        Connect to an existing (Chromium-based) browser session via CDP.
        Must have launched with e.g. --remote-debugging-port=9222.
        """
        try:
            await self.logs_manager.info(f"Attempting to connect to existing {self.browser_type} browser...")
            await self.logs_manager.debug(f"CDP URL: {self.cdp_url}")
            
            # Only chromium-based attach is fully supported
            if self.browser_type in ['edge', 'chrome']:
                await self.logs_manager.info(f"Initiating CDP connection to {self.browser_type}...")
                browser = await playwright.chromium.connect_over_cdp(self.cdp_url)
                await self.logs_manager.info("CDP connection established successfully")
                return browser
            elif self.browser_type == 'firefox':
                msg = "Attaching to existing Firefox is not supported by Playwright"
                await self.logs_manager.error(msg)
                raise NotImplementedError(msg)
            else:
                msg = f"Browser attachment only supported for edge/chrome, got: {self.browser_type}"
                await self.logs_manager.error(msg)
                raise NotImplementedError(msg)
        except Exception as e:
            error_msg = f"Failed to attach to browser at {self.cdp_url}: {str(e)}"
            await self.logs_manager.error(error_msg)
            await self.logs_manager.debug(f"Full error details: {repr(e)}")
            raise Exception(error_msg)

    async def _launch_firefox_persistent(self, playwright) -> Tuple[BrowserContext, Page]:
        """
        Launch persistent Firefox context with NO incognito, returning (context, page).
        """
        try:
            profile_dir = self.profiles_dir / "firefox"
            profile_dir.mkdir(parents=True, exist_ok=True)
            await self.logs_manager.info(f"Created/verified Firefox profile directory: {profile_dir}")

            # Some user prefs
            firefox_prefs = {
                'browser.privatebrowsing.autostart': False,
                'network.cookie.cookieBehavior': 0  # 0=Accept all cookies
            }
            await self.logs_manager.debug("Configuring Firefox preferences...")

            await self.logs_manager.info("Launching Firefox with persistent profile...")
            context = await playwright.firefox.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=self.headless,
                args=["--no-sandbox"],
                firefox_user_prefs=firefox_prefs
            )
            await self.logs_manager.info("Firefox context created successfully")

            if context.pages:
                page = context.pages[0]
                await self.logs_manager.debug("Using existing page from Firefox context")
            else:
                page = await context.new_page()
                await self.logs_manager.debug("Created new page in Firefox context")

            await self.logs_manager.info("Firefox browser setup completed successfully")
            return context, page
        except Exception as e:
            error_msg = f"Failed to launch Firefox: {str(e)}"
            await self.logs_manager.error(error_msg)
            await self.logs_manager.debug(f"Full error details: {repr(e)}")
            raise Exception(error_msg)

    async def _launch_chromium_persistent(self, playwright) -> Tuple[BrowserContext, Page]:
        """Launch a persistent Edge/Chrome context with no incognito."""
        try:
            profile_dir = self.profiles_dir / (self.browser_type or "chromium")
            profile_dir.mkdir(parents=True, exist_ok=True)
            await self.logs_manager.info(f"Created/verified {self.browser_type} profile directory: {profile_dir}")

            await self.logs_manager.info(f"Preparing to launch {self.browser_type} with persistent profile...")

            launch_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
            ignore_args = [
                "--enable-automation"
            ]
            await self.logs_manager.debug(f"Browser launch arguments: {launch_args}")
            await self.logs_manager.debug(f"Ignored arguments: {ignore_args}")

            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=self.headless,
                args=launch_args,
                ignore_default_args=ignore_args
            )
            await self.logs_manager.info(f"{self.browser_type} context created successfully")

            if context.pages:
                page = context.pages[0]
                await self.logs_manager.debug("Using existing page from context")
            else:
                page = await context.new_page()
                await self.logs_manager.debug("Created new page in context")

            await self.logs_manager.info(f"{self.browser_type} browser setup completed successfully")
            return context, page
        except Exception as e:
            error_msg = f"Failed to launch {self.browser_type}: {str(e)}"
            await self.logs_manager.error(error_msg)
            await self.logs_manager.debug(f"Full error details: {repr(e)}")
            raise Exception(error_msg)

    async def initialize(self, attach_existing: bool = False) -> Tuple[Union[Browser, BrowserContext], Page]:
        """
        Initialize and configure the browser instance. 
        Returns (browser_or_context, page).
        If attach_existing=True, attempt to connect to an existing session (Edge/Chrome).
        """
        await self.logs_manager.info("Starting browser initialization process...")

        # Handle browser selection if needed
        should_prompt = self.settings.get('should_prompt', True)
        if should_prompt or not self.settings.get('type'):
            await self.logs_manager.info("Browser selection required")
            
            # Print options for user interaction
            print("\nSelect Browser:")  # Keep print for user interface
            print("1) Edge (recommended)")
            print("2) Chrome")
            print("3) Firefox")
            print("4) Attach to existing browser (Chromium-based)")
            
            while True:
                try:
                    choice = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input("\nSelect browser (1-4): ").strip()
                    )
                    await self.logs_manager.debug(f"User input received: {choice}")
                    
                    if choice == '1':
                        self.browser_type = 'edge'
                        attach_existing = False
                        await self.logs_manager.info("Edge browser selected")
                        break
                    elif choice == '2':
                        self.browser_type = 'chrome'
                        attach_existing = False
                        await self.logs_manager.info("Chrome browser selected")
                        break
                    elif choice == '3':
                        self.browser_type = 'firefox'
                        attach_existing = False
                        await self.logs_manager.info("Firefox browser selected")
                        break
                    elif choice == '4':
                        self.browser_type = 'chrome'
                        attach_existing = True
                        await self.logs_manager.info("Attaching to existing Chrome browser")
                        break
                    else:
                        print("Invalid choice. Please select 1-4.")  # Keep print for immediate user feedback
                        await self.logs_manager.warning(f"Invalid browser choice: {choice}")
                except Exception as e:
                    print(f"Error: {str(e)}. Please try again.")  # Keep print for immediate user feedback
                    await self.logs_manager.error(f"Browser selection error: {str(e)}")
        else:
            self.browser_type = self.settings.get('type')
            attach_existing = self.settings.get('attach_existing', attach_existing)
            await self.logs_manager.info(f"Using configured browser: {self.browser_type}")

        await self.logs_manager.info(f"Browser type: {self.browser_type}, Attach existing: {attach_existing}")

        # Derive executable path
        self.executable_path = self._get_browser_path()
        if self.executable_path:
            await self.logs_manager.info(f"Using browser executable: {self.executable_path}")
        else:
            await self.logs_manager.debug("No explicit executable path required - using system default")

        await self.logs_manager.info("Starting Playwright...")
        playwright = await async_playwright().start()
        await self.logs_manager.debug("Playwright started successfully")

        try:
            if attach_existing:
                await self.logs_manager.info("Initiating attachment to existing browser session...")
                browser = await self._attach_to_browser(playwright)
                await self.logs_manager.info("Creating new page in attached browser...")
                page = await browser.new_page()
                await self.logs_manager.info("Successfully created new page in attached browser")
                await self._configure_page(page)
                await self.telemetry.track_browser_setup(
                    browser_type=self.browser_type,
                    headless=self.headless,
                    success=True
                )
                return browser, page

            # Otherwise, launch a persistent context
            if self.browser_type == 'firefox':
                await self.logs_manager.info("Initiating Firefox browser launch...")
                context, page = await self._launch_firefox_persistent(playwright)
            elif self.browser_type in ['edge', 'chrome']:
                await self.logs_manager.info(f"Initiating {self.browser_type} browser launch...")
                context, page = await self._launch_chromium_persistent(playwright)
            else:
                error_msg = f"Unsupported browser type: {self.browser_type}"
                await self.logs_manager.error(error_msg)
                raise ValueError(error_msg)

            await self._configure_page(page)
            await self.telemetry.track_browser_setup(
                browser_type=self.browser_type,
                headless=self.headless,
                success=True
            )
            await self.logs_manager.info("Browser initialization completed successfully")
            return context, page

        except Exception as e:
            error_msg = f"Browser initialization failed: {str(e)}"
            await self.logs_manager.error(error_msg)
            await self.logs_manager.debug(f"Full error details: {repr(e)}")
            await self.logs_manager.info("Stopping Playwright due to initialization failure...")
            await playwright.stop()
            await self.telemetry.track_browser_setup(
                browser_type=self.browser_type,
                headless=self.headless,
                success=False,
                error=str(e)
            )
            raise Exception(error_msg)

    async def _configure_page(self, page: Page):
        """Configure page settings (viewport, user agent, cookies)."""
        try:
            await self.logs_manager.info("Starting page configuration...")

            # Set viewport
            w = self.viewport.get('width', 1280)
            h = self.viewport.get('height', 720)
            await self.logs_manager.debug(f"Setting viewport size to {w}x{h}")
            await page.set_viewport_size({'width': w, 'height': h})
            await self.logs_manager.debug("Viewport size set successfully")

            # Set user agent if specified
            if self.user_agent:
                await self.logs_manager.debug(f"Setting custom user agent: {self.user_agent}")
                await page.set_extra_http_headers({'User-Agent': self.user_agent})
                await self.logs_manager.debug("User agent set successfully")

            # Load cookies if available
            if self.cookies_path.exists():
                await self.logs_manager.info("Found existing cookies file, attempting to load...")
                try:
                    cookies = json.loads(self.cookies_path.read_text())
                    if cookies:
                        await self.logs_manager.debug(f"Loading {len(cookies)} cookies...")
                        await page.context.add_cookies(cookies)
                        await self.logs_manager.info(f"Successfully loaded {len(cookies)} cookies")
                    else:
                        await self.logs_manager.debug("Cookies file exists but is empty")
                except Exception as e:
                    await self.logs_manager.error(f"Failed to load cookies: {str(e)}")
                    await self.logs_manager.debug(f"Full cookie error details: {repr(e)}")
            else:
                await self.logs_manager.info("No existing cookies file found - starting fresh session")

            await self.logs_manager.info("Page configuration completed successfully")
        except Exception as e:
            error_msg = f"Error during page configuration: {str(e)}"
            await self.logs_manager.error(error_msg)
            await self.logs_manager.debug(f"Full error details: {repr(e)}")
            raise Exception(error_msg)

    async def save_cookies(self, page: Page):
        """Save cookies for future sessions."""
        try:
            await self.logs_manager.info("Starting cookie save process...")
            await self.logs_manager.debug(f"Cookie save path: {self.cookies_path}")
            
            cookies = await page.context.cookies()
            await self.logs_manager.debug(f"Retrieved {len(cookies)} cookies from browser")
            
            self.cookies_path.write_text(json.dumps(cookies, indent=2))
            await self.logs_manager.info(f"Successfully saved {len(cookies)} cookies to disk")
        except Exception as e:
            error_msg = f"Failed to save cookies: {str(e)}"
            await self.logs_manager.error(error_msg)
            await self.logs_manager.debug(f"Full error details: {repr(e)}")
            raise Exception(error_msg)

    async def cleanup(self, browser_or_context: Union[Browser, BrowserContext], page: Page):
        """Clean up browser resources, persisting cookies if possible."""
        try:
            await self.logs_manager.info("Starting browser cleanup process...")
            
            # Try to save cookies first
            try:
                await self.save_cookies(page)
            except Exception as cookie_error:
                await self.logs_manager.warning(f"Cookie save during cleanup failed: {str(cookie_error)}")
                await self.logs_manager.debug("Continuing with cleanup despite cookie save failure")
            
            if hasattr(browser_or_context, 'close'):
                await self.logs_manager.info("Closing browser/context...")
                await browser_or_context.close()
                await self.logs_manager.info("Browser cleanup completed successfully")
            else:
                await self.logs_manager.warning(f"Unknown browser object type ({type(browser_or_context)}), cannot close properly")
        except Exception as e:
            error_msg = f"Error during browser cleanup: {str(e)}"
            await self.logs_manager.error(error_msg)
            await self.logs_manager.debug(f"Full error details: {repr(e)}")
            raise Exception(error_msg)
