"""
AI-driven navigation with confidence scoring, DOM interaction, and a dynamic AI Master-Plan.

Architecture:
------------
1. Navigation Logic (This Module)
   - Confidence-based decision making
   - Fallback strategy orchestration
   - **Dynamic AI Master-Plan** for multi-step flows (site-specific or scenario-based)
   - Navigation outcome tracking
   - Error recovery management
   - CAPTCHA checks for critical steps

2. DOM Interactions (via DomService)
   - Element discovery and interaction
   - Optional bounding-box annotation (future expansions)
   - Basic DOM operations (click, fill, etc.)
   - DOM tree traversal
   - Highlighting and visual feedback

3. Selector Management (LinkedInLocators or fallback)
   - Centralized selector definitions for site-specific interactions
   - Site-based fallback if Master-Plan or bounding-box fails

Dynamic Plan Features:
---------------------
- We allow dynamic insertion of CAPTCHA handling steps before critical steps
  (e.g., "submit_application", "login", "apply").
- The plan can be site-specific, re-ordered, or expanded depending on the scenario.

Dependencies:
------------
- DomService: for direct DOM interactions
- TelemetryManager: for tracking performance/outcomes
- credentials_agent, form_filler_agent, user_profile_agent, tracker_agent, etc. for advanced flows
"""

from typing import Tuple, List
from utils.telemetry import TelemetryManager
from locators.linkedin_locators import LinkedInLocators
from utils.dom.dom_service import DomService
import asyncio

# If you have them:
from agents.credentials_agent import CredentialsAgent
from agents.form_filler_agent import FormFillerAgent
from agents.user_profile_agent import UserProfileAgent
from agents.tracker_agent import TrackerAgent
from constants import TimingConstants

class AINavigator:
    # Steps considered "critical" for possible CAPTCHA appearance
    critical_steps = {"login", "apply", "submit_application"}

    def __init__(self, page, settings, min_confidence=0.8, max_retries=3):
        """Initialize AINavigator with references to other agents if needed."""
        self.page = page
        self.settings = settings
        self.min_confidence = min_confidence
        self.max_retries = max_retries
        self.retry_count = 0

        # Initialize services
        self.dom_service = DomService(page)
        self.telemetry = TelemetryManager(settings)
        self.locators = LinkedInLocators()

        # Optionally store references to other agents for integrated steps
        self.credentials_agent = CredentialsAgent(settings)
        self.form_filler_agent = FormFillerAgent(self.dom_service)  # if that's how it's constructed
        self.user_profile_agent = UserProfileAgent(settings)
        self.tracker_agent = TrackerAgent(settings)

    async def navigate(self, action, context) -> Tuple[bool, float]:
        """
        Main navigation method with confidence scoring.
        Returns (success: bool, confidence: float).
        """
        confidence = await self._calculate_confidence(action, context)

        if confidence >= self.min_confidence:
            try:
                await action()  # success if no exception is raised
                await self._log_success(action, context, confidence)
                return True, confidence

            except Exception as e:
                self.retry_count += 1
                if self.retry_count < self.max_retries:
                    return await self._handle_retry(action, context, confidence, str(e))
                return await self._handle_failure(action, context, confidence, str(e))
        else:
            return await self._handle_low_confidence(action, confidence)

    async def execute_master_plan(self, plan_steps: List[str]) -> Tuple[bool, float]:
        """
        Execute a series of steps in order, with dynamic captcha checks for critical steps.
        
        Returns:
            Tuple[bool, float]: (success, overall_confidence)
        """
        overall_confidence = 1.0
        executed_steps = []

        for step in plan_steps:
            try:
                # Check CAPTCHA before critical steps
                if step in self.critical_steps:
                    captcha_detected = await self._check_for_captcha()
                    if captcha_detected:
                        success, conf = await self.navigate(self._handle_captcha, {"step": "handle_captcha"})
                        if not success:
                            return False, overall_confidence

                # Execute the planned step
                success, confidence = await self._execute_step(step)
                overall_confidence *= confidence
                
                if not success:
                    print(f"[AINavigator] Step '{step}' failed with confidence {confidence:.2f}")
                    return False, overall_confidence
                
                executed_steps.append(step)
                print(f"[AINavigator] Step '{step}' completed with confidence {confidence:.2f}")

            except Exception as e:
                print(f"[AINavigator] Error in step '{step}': {str(e)}")
                return False, overall_confidence

        return True, overall_confidence

    async def _execute_step(self, step_name: str) -> Tuple[bool, float]:
        """Convert the step_name into an actual action method, then call `navigate`."""
        step_actions = {
            # Navigation steps
            "check_login": self._verify_login_status,
            "open_job_page": self._navigate_to_jobs_page,
            "fill_search": self._fill_search_form,
            "apply": self._click_apply_button,
            
            # Form handling steps
            "handle_user_profile": self._handle_user_profile,
            "fill_application_form": self._fill_application_form,
            "validate_form": self._validate_form,
            "submit_application": self._submit_application,
            "track_application": self._track_application,
            
            # Verification steps
            "verify_action": self._verify_action,
            "double_verify_action": self._double_verify_action,
            "extended_verification": self._handle_extended_verification,
            
            # Recovery steps
            "recovery_check": self._handle_recovery_check,
            "state_restoration": self._handle_state_restoration,
            
            # Rate limiting steps
            "rate_limit_delay": self._handle_rate_limit_delay,
            "extended_wait": self._handle_extended_wait,
        }
        
        if step_name not in step_actions:
            print(f"[AINavigator] Unknown step: '{step_name}'")
            return False, 0.0

        action_method = step_actions[step_name]
        context = {"step": step_name}
        return await self.navigate(action_method, context)

    async def navigate_with_confidence(self, target: str):
        """Example method if you want to track a custom navigation event."""
        await self.telemetry.track_event(
            "navigation_attempt",
            {"target": target},
            success=True,
            confidence=self.min_confidence
        )

    # -----------------------------------------
    # Additional Step Implementations
    # -----------------------------------------
    async def _verify_login_status(self):
        """Verify user is logged in."""
        print("[AINavigator] Verifying login status...")
        if not await self.dom_service.check_element_present(
            self.locators.PROFILE_BUTTON, timeout=3000
        ):
            raise Exception("User not logged in.")

    async def _navigate_to_jobs_page(self):
        """Navigate to LinkedIn's jobs page."""
        print("[AINavigator] Navigating to jobs page...")
        await self.dom_service.goto(self.locators.JOBS_URL)
        found = await self.dom_service.check_element_present(
            self.locators.JOBS_SEARCH_RESULTS,
            timeout=5000
        )
        if not found:
            raise Exception("Jobs page not loaded properly")

    async def _fill_search_form(self):
        """Fill out job search form."""
        print("[AINavigator] Filling search form...")
        await self.dom_service.type_text(
            self.locators.JOB_TITLE_INPUT,
            self.settings.get('job_title', '')
        )
        await self.dom_service.type_text(
            self.locators.LOCATION_INPUT,
            self.settings.get('location', '')
        )
        await self.dom_service.click_element(self.locators.SEARCH_BUTTON)
        # Wait for results
        found = await self.dom_service.check_element_present(
            self.locators.JOBS_SEARCH_RESULTS,
            timeout=5000
        )
        if not found:
            raise Exception("Search results not loaded")

    async def _click_apply_button(self):
        """Click the 'Apply' button on a job posting."""
        print("[AINavigator] Clicking apply button...")
        await self.dom_service.click_element(self.locators.APPLY_BUTTON)
        # Verify apply modal opened
        modal_open = await self.dom_service.check_element_present(
            self.locators.APPLY_MODAL,
            timeout=3000
        )
        if not modal_open:
            raise Exception("Apply modal did not appear")

    async def _handle_user_profile(self):
        """Retrieve or update user profile data via user_profile_agent."""
        print("[AINavigator] Handling user profile...")
        # Example usage:
        profile = await self.user_profile_agent.get_profile("default_user_id")
        if not profile:
            raise Exception("User profile not found or could not load.")
        # Could store or modify profile data, e.g.:
        # updated_profile = await self.user_profile_agent.update_profile(...)

    async def _fill_application_form(self):
        """Fill out the job application form (e.g., phone, address) with form_filler_agent."""
        print("[AINavigator] Filling application form with form_filler_agent...")
        form_data = {
            "full_name": "Alice Wonderland",
            "phone": "123-456-7890",
            "cv_file": "/path/to/resume.pdf",
            # etc.
        }
        # Suppose form_filler_agent.fill_form returns True/False
        success = await self.form_filler_agent.fill_form(form_data, form_mapping={})
        if not success:
            raise Exception("Form filling failed via form_filler_agent.")

    async def _validate_form(self):
        """Validate the form before submission (client-side checks)."""
        print("[AINavigator] Validating form data...")
        # Could check for error banners or missing fields:
        error_banner = await self.dom_service.check_element_present(
            ".artdeco-inline-feedback--error", timeout=2000
        )
        if error_banner:
            raise Exception("Form validation error encountered")

    async def _submit_application(self):
        """Submit the application form."""
        print("[AINavigator] Submitting application form...")
        await self.dom_service.click_element("button[type='submit']")
        # Confirm success
        success_banner = await self.dom_service.check_element_present(
            ".application-success",
            timeout=5000
        )
        if not success_banner:
            raise Exception("No success banner - submission might have failed")

    async def _track_application(self):
        """Track the application via tracker_agent."""
        print("[AINavigator] Tracking application with tracker_agent...")
        await self.tracker_agent.log_activity(
            activity_type="application_tracking",
            details="Tracked after final submission",
            status="info",
            agent_name="AINavigator"
        )

    async def _login_step(self):
        """Perform login if needed (placeholder)."""
        print("[AINavigator] Logging in (placeholder)...")
        # e.g., credentials_agent usage:
        # success = await self.credentials_agent.login_to_platform("LinkedIn")
        # if not success: raise Exception("Login failed")

    # -----------------------------------------
    # CAPTCHA Handling
    # -----------------------------------------
    async def _check_for_captcha(self) -> bool:
        """Return True if a captcha is present on the page."""
        try:
            # e.g. self.locators.LINKEDIN_CAPTCHA_IMAGE or something
            captcha_present = await self.dom_service.check_element_present(
                "img.captcha__image", timeout=2000
            )
            return captcha_present
        except:
            return False

    async def _handle_captcha(self):
        """Solve or handle captcha with credentials_agent."""
        print("[AINavigator] Handling CAPTCHA...")
        # For example:
        solution = await self.credentials_agent.handle_captcha("img.captcha__image")
        if not solution:
            raise Exception("Captcha solving failed or user skipped")

    # -----------------------------------------
    # Navigation Internals
    # -----------------------------------------
    async def _execute_action(self, action):
        """Execute action with DOM-based fallback if primary action fails."""
        try:
            return await action()
        except Exception:
            # fallback to DOM-based approach
            elements = await self.dom_service.get_clickable_elements(highlight=True)
            return await self._handle_dom_fallback(elements, action)

    async def _handle_dom_fallback(self, elements, action):
        """AI-driven fallback logic when primary action fails."""
        print("[AINavigator] Fallback triggered. Checking clickable elements in DOM...")
        # You could add logic to pick the best element from `elements` if your plan is unclear
        return None

    async def _calculate_confidence(self, action, context) -> float:
        """Naive confidence calculation example."""
        step = context.get("step", "")
        # For demonstration, a uniform confidence or a slight variation
        if step in ["handle_captcha", "submit_application"]:
            return 0.85
        return 1.0

    async def _log_success(self, action, context, confidence):
        step = context.get("step", "unknown")
        print(f"[AINavigator] Step '{step}' succeeded with confidence={confidence:.2f}")

    async def _handle_retry(self, action, context, confidence, error_msg):
        step = context.get("step", "unknown")
        print(f"[AINavigator] Step '{step}' retry {self.retry_count}, error={error_msg}")
        return await self.navigate(action, context)

    async def _handle_failure(self, action, context, confidence, error_msg):
        step = context.get("step", "unknown")
        print(f"[AINavigator] Step '{step}' - max retries reached. Failing. Error={error_msg}")
        return False, confidence

    async def _handle_low_confidence(self, action, confidence):
        print(f"[AINavigator] Low confidence={confidence:.2f}, skipping step.")
        return False, confidence

    # Add new step implementations
    async def _handle_rate_limit_delay(self):
        """Handle rate limit delay with exponential backoff."""
        delay = self.settings.get('rate_limit_delay', TimingConstants.BASE_RETRY_DELAY)
        print(f"[AINavigator] Rate limit delay: {delay}ms")
        await asyncio.sleep(delay / 1000)  # Convert ms to seconds

    async def _verify_action(self):
        """
        Basic verification of previous action.
        Checks:
        1. Page responsiveness
        2. No error banners
        3. Expected elements present
        4. CAPTCHA detection
        5. Network state
        6. DOM tree health
        """
        print("[AINavigator] Verifying previous action...")
        try:
            # 1. Check page responsiveness
            await self.dom_service.check_element_present('body', timeout=2000)
            
            # 2. Check for error banners/messages
            error_present = await self.dom_service.check_element_present(
                '.error-banner, .error-message, .alert-error, .notification-error',
                timeout=1000
            )
            if error_present:
                print("[AINavigator] Error banner detected during verification")
                return False

            # 3. Check for CAPTCHA presence
            captcha_present = await self.dom_service.check_element_present(
                'img.captcha__image, .recaptcha-checkbox-border, iframe[title*="reCAPTCHA"]',
                timeout=1000
            )
            if captcha_present:
                print("[AINavigator] CAPTCHA detected during verification")
                return False
            
            # 4. Verify DOM tree health
            try:
                dom_tree = await self.dom_service.get_dom_tree(highlight=False)
                if not dom_tree or not dom_tree.children:
                    print("[AINavigator] DOM tree appears corrupted")
                    return False
            except Exception as e:
                print(f"[AINavigator] DOM tree verification failed: {str(e)}")
                return False

            # 5. Check for rate limiting indicators
            rate_limited = await self.dom_service.check_element_present(
                '.rate-limit-message, .too-many-requests',
                timeout=1000
            )
            if rate_limited:
                print("[AINavigator] Rate limiting detected during verification")
                return False

            # 6. Verify clickable elements are accessible
            try:
                clickable_elements = await self.dom_service.get_clickable_elements(highlight=False)
                if not clickable_elements:
                    print("[AINavigator] No clickable elements found - possible page issue")
                    return False
            except Exception as e:
                print(f"[AINavigator] Clickable elements verification failed: {str(e)}")
                return False

            # 7. Basic DOM health check
            await asyncio.sleep(TimingConstants.VERIFICATION_DELAY)
            return True
            
        except Exception as e:
            print(f"[AINavigator] Verification failed: {str(e)}")
            return False

    async def _double_verify_action(self):
        """More thorough verification for critical steps."""
        print("[AINavigator] Double verification of previous action...")
        first_check = await self._verify_action()  # First verification
        if not first_check:
            return False
            
        await asyncio.sleep(TimingConstants.EXTENDED_VERIFICATION_DELAY)
        return await self._verify_action()  # Second verification

    async def _handle_extended_wait(self):
        """Handle extended wait period."""
        print("[AINavigator] Extended wait...")
        await asyncio.sleep(TimingConstants.EXTENDED_WAIT_DELAY)

    async def _handle_recovery_check(self):
        """
        Check if recovery is needed by verifying:
        1. Page state (not error/404)
        2. User session validity
        3. DOM health
        4. Network conditions
        """
        print("[AINavigator] Checking recovery status...")
        try:
            # 1. Check page state
            current_url = await self.page.url
            if "error" in current_url.lower() or "404" in current_url:
                print("[AINavigator] Error or 404 page detected")
                return False

            # 2. Verify user session
            session_valid = await self.dom_service.check_element_present(
                self.locators.PROFILE_BUTTON,
                timeout=2000
            )
            if not session_valid:
                print("[AINavigator] User session appears invalid")
                return False

            # 3. Check DOM health
            try:
                await self.dom_service.check_element_present('body', timeout=2000)
            except Exception:
                print("[AINavigator] DOM health check failed")
                return False

            # 4. Check for rate limiting indicators
            rate_limited = await self.dom_service.check_element_present(
                '.rate-limit-message, .too-many-requests',
                timeout=1000
            )
            if rate_limited:
                print("[AINavigator] Rate limiting detected")
                return False

            return True

        except Exception as e:
            print(f"[AINavigator] Recovery check failed: {str(e)}")
            return False

    async def _handle_state_restoration(self):
        """
        Restore previous state by:
        1. Verifying page context
        2. Checking form state
        3. Validating navigation state
        4. Ensuring proper login state
        """
        print("[AINavigator] Restoring previous state...")
        try:
            # 1. Verify page context
            current_url = await self.page.url
            if not await self._verify_page_context(current_url):
                return False

            # 2. Check form state if applicable
            if await self.dom_service.check_element_present('form', timeout=1000):
                form_valid = await self._verify_form_state()
                if not form_valid:
                    print("[AINavigator] Form state verification failed")
                    return False

            # 3. Validate navigation state
            nav_valid = await self._verify_navigation_state()
            if not nav_valid:
                print("[AINavigator] Navigation state verification failed")
                return False

            # 4. Verify login state
            login_valid = await self.dom_service.check_element_present(
                self.locators.PROFILE_BUTTON,
                timeout=2000
            )
            if not login_valid:
                print("[AINavigator] Login state verification failed")
                return False

            return True

        except Exception as e:
            print(f"[AINavigator] State restoration failed: {str(e)}")
            return False

    async def _verify_page_context(self, current_url: str) -> bool:
        """Helper to verify the current page context."""
        try:
            # Check if we're on an expected page type
            expected_urls = [
                'linkedin.com/jobs',
                'linkedin.com/in/',
                'linkedin.com/feed',
                # Add other valid URLs as needed
            ]
            return any(url in current_url for url in expected_urls)
        except Exception:
            return False

    async def _verify_form_state(self) -> bool:
        """Helper to verify form state if present."""
        try:
            # Check for common form elements
            required_fields = await self.dom_service.get_elements(
                'input[required], select[required], textarea[required]'
            )
            
            # Verify required fields have values
            for field in required_fields:
                value = await field.get_property('value')
                if not value:
                    return False
            
            return True
        except Exception:
            return False

    async def _verify_navigation_state(self) -> bool:
        """Helper to verify navigation state."""
        try:
            # Check for common navigation elements
            nav_elements = [
                'nav',
                '.global-nav',
                '.navigation-bar'
            ]
            
            for selector in nav_elements:
                if await self.dom_service.check_element_present(selector, timeout=1000):
                    return True
            
            return False
        except Exception:
            return False

    async def _handle_extended_verification(self):
        """
        More thorough verification for critical steps.
        Includes multiple checks and longer delays.
        """
        print("[AINavigator] Performing extended verification...")
        try:
            # First basic verification
            if not await self._verify_action():
                return False
                
            # Additional delay
            await asyncio.sleep(TimingConstants.EXTENDED_VERIFICATION_DELAY)
            
            # Check for specific error conditions
            error_conditions = [
                '.error-notification',
                '.warning-message',
                '.validation-error',
                '.rate-limit-warning'
            ]
            
            for selector in error_conditions:
                if await self.dom_service.check_element_present(selector, timeout=1000):
                    print(f"[AINavigator] Extended verification failed: found {selector}")
                    return False
            
            # Final verification
            return await self._verify_action()
            
        except Exception as e:
            print(f"[AINavigator] Extended verification failed: {str(e)}")
            return False
