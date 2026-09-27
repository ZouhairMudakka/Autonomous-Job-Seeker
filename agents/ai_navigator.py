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

from typing import Tuple, List, Dict, Any
from utils.telemetry import TelemetryManager
from locators.linkedin_locators import LinkedInLocators
from utils.dom.dom_service import DomService
from storage.logs_manager import LogsManager
import asyncio
import time
from datetime import datetime
from urllib.parse import urlsplit
from dataclasses import dataclass, field
from collections import defaultdict

# If you have them:
from agents.credentials_agent import CredentialsAgent
from agents.form_filler_agent import FormFillerAgent
from agents.user_profile_agent import UserProfileAgent
from agents.tracker_agent import TrackerAgent
from constants import TimingConstants
from agents.cv_parser_agent import CVParserAgent

@dataclass
class NavigationMetrics:
    """Tracks navigation-related metrics and history."""
    navigation_history: List[Dict[str, Any]] = field(default_factory=list)
    state_transitions: List[Dict[str, Any]] = field(default_factory=list)
    performance_metrics: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    last_state: str = "initialized"

class AINavigator:
    # Steps considered "critical" for possible CAPTCHA appearance
    critical_steps = {"login", "apply", "submit_application"}

    def __init__(self, page, settings, logs_manager: LogsManager, min_confidence=0.8, max_retries=3):
        """Initialize AINavigator with references to other agents if needed."""
        self.page = page
        self.settings = settings
        self.min_confidence = min_confidence
        self.max_retries = max_retries
        self.retry_count = 0
        self.logs_manager = logs_manager

        # Initialize metrics tracking
        self.metrics = NavigationMetrics()
        self.start_time = time.time()

        # Initialize services
        self.dom_service = DomService(page, settings=settings, logs_manager=logs_manager)
        self.telemetry = TelemetryManager(settings)
        self.locators = LinkedInLocators()

        # Initialize agents with proper parameters
        self.credentials_agent = CredentialsAgent(settings, self.dom_service, logs_manager)
        self.form_filler_agent = FormFillerAgent(self.dom_service, logs_manager, settings)
        self.user_profile_agent = UserProfileAgent(settings, logs_manager)
        self.tracker_agent = TrackerAgent(settings, logs_manager)
        self.cv_parser = CVParserAgent(settings, logs_manager)

    async def navigate(self, action, context) -> Tuple[bool, float]:
        """Execute one step with its own bounded retry budget."""
        context = context or {}
        step = context.get("step", "unknown")
        confidence = await self._calculate_confidence(action, context)
        if confidence < self.min_confidence:
            return await self._handle_low_confidence(action, confidence)
        # A submission can succeed remotely even if its confirmation times out.
        # Never automatically click Submit again after an uncertain result.
        attempts = 1 if step == "submit_application" else max(1, self.max_retries)
        self.retry_count = 0
        for attempt in range(attempts):
            started = time.monotonic()
            try:
                result = await action()
                if result is False:
                    raise RuntimeError(f"Step '{step}' reported failure")
            except Exception as exc:
                self.retry_count = attempt + 1
                self.metrics.error_counts[step] += 1
                await self._handle_error_with_context(exc, context)
                if attempt + 1 == attempts:
                    return await self._handle_failure(action, context, confidence, str(exc))
                await asyncio.sleep(TimingConstants.BASE_RETRY_DELAY / 1000 * (2 ** attempt))
                continue
            await self._track_performance(step, time.monotonic() - started)
            await self._log_success(action, context, confidence)
            self.retry_count = 0
            return True, confidence
        return False, confidence

    async def execute_master_plan(self, plan_steps: List[str], before_step=None) -> Tuple[bool, float]:
        """
        Execute a series of steps in order, with dynamic captcha checks for critical steps.

        Returns:
            Tuple[bool, float]: (success, overall_confidence)
        """
        start_time = time.time()
        await self.logs_manager.info(f"Starting master plan execution with {len(plan_steps)} steps")
        await self.logs_manager.debug(f"Plan steps: {', '.join(plan_steps)}")

        overall_confidence = 1.0
        self.current_plan = list(plan_steps)
        self.current_step = 0
        self.completed_steps = []
        executed_steps = self.completed_steps

        try:
            for index, step in enumerate(plan_steps, 1):
                self.current_step = index - 1
                if before_step is not None:
                    await before_step()
                step_start_time = time.time()
                await self.logs_manager.info(f"Executing step {index}/{len(plan_steps)}: {step}")

                try:
                    # Check CAPTCHA before critical steps
                    if step in self.critical_steps:
                        await self.logs_manager.debug(f"Performing CAPTCHA check for critical step: {step}")
                        captcha_detected = await self._check_for_captcha()
                        if captcha_detected:
                            await self.logs_manager.warning(f"CAPTCHA detected before step: {step}")
                            success, conf = await self.navigate(self._handle_captcha, {"step": "handle_captcha"})
                            if not success:
                                duration = time.time() - start_time
                                await self.logs_manager.error(f"Master plan failed at CAPTCHA handling after {duration:.2f}s")
                                return False, overall_confidence

                    # Execute the planned step
                    await self.logs_manager.debug(f"Starting execution of step: {step}")
                    success, confidence = await self._execute_step(step)
                    overall_confidence *= confidence

                    step_duration = time.time() - step_start_time
                    await self._track_performance(step, step_duration)

                    if not success:
                        await self.logs_manager.error(f"Step '{step}' failed with confidence {confidence:.2f}")
                        return False, overall_confidence

                    executed_steps.append(step)
                    self.current_step = index
                    await self.logs_manager.info(f"Step '{step}' completed with confidence {confidence:.2f} in {step_duration:.2f}s")

                except Exception as e:
                    await self.logs_manager.error(f"Error in step '{step}': {str(e)}")
                    await self._handle_error_with_context(e, {"step": step, "index": index})
                    return False, overall_confidence

            total_duration = time.time() - start_time
            await self.logs_manager.info(f"Master plan completed successfully in {total_duration:.2f}s")
            return True, overall_confidence

        except Exception as e:
            total_duration = time.time() - start_time
            await self.logs_manager.error(f"Master plan execution failed after {total_duration:.2f}s: {str(e)}")
            raise

    async def _track_performance(self, operation: str, duration: float):
        """Track performance metrics for operations."""
        self.metrics.performance_metrics[operation].append(duration)
        await self.logs_manager.debug(f"Performance: {operation} took {duration:.2f}s")

        # Log if operation took longer than expected
        if duration > (TimingConstants.DEFAULT_TIMEOUT / 1000):
            await self.logs_manager.warning(f"Operation {operation} took longer than expected: {duration:.2f}s")

    async def _handle_error_with_context(self, error: Exception, context: dict):
        """Log detailed error context."""
        await self.logs_manager.error(f"Error occurred: {str(error)}")
        await self.logs_manager.debug("Error context:")
        for key, value in context.items():
            await self.logs_manager.debug(f"- {key}: {value}")

        # Log current state
        current_url = getattr(self.page, "url", "unavailable")
        await self.logs_manager.debug(f"Current URL: {current_url}")
        await self.logs_manager.debug(f"Retry count: {self.retry_count}")
        await self.logs_manager.debug(f"Total errors: {sum(self.metrics.error_counts.values())}")

    async def _log_system_health(self):
        """Log system health metrics."""
        await self.logs_manager.debug("System health check:")
        await self.logs_manager.debug(f"- Retry count: {self.retry_count}")
        await self.logs_manager.debug(f"- Current confidence: {self.min_confidence}")
        await self.logs_manager.debug(f"- Total errors: {sum(self.metrics.error_counts.values())}")
        await self.logs_manager.debug(f"- Uptime: {time.time() - self.start_time:.2f}s")

        # Log performance statistics if available
        if self.metrics.performance_metrics:
            await self.logs_manager.debug("Performance metrics:")
            for operation, durations in self.metrics.performance_metrics.items():
                avg_duration = sum(durations) / len(durations)
                await self.logs_manager.debug(f"- {operation}: avg={avg_duration:.2f}s, count={len(durations)}")

    async def _handle_state_transition(self, from_state: str, to_state: str, context: dict = None):
        """Log and handle state transitions."""
        transition_time = datetime.now().isoformat()

        self.metrics.state_transitions.append({
            "from": from_state,
            "to": to_state,
            "timestamp": transition_time,
            "context": context or {}
        })

        await self.logs_manager.info(f"State transition: {from_state} -> {to_state}")
        if context:
            await self.logs_manager.debug("Transition context:")
            for key, value in context.items():
                await self.logs_manager.debug(f"- {key}: {value}")

        self.metrics.last_state = to_state

    async def _log_navigation_path(self, current_url: str, target_url: str):
        """Log navigation path changes."""
        timestamp = datetime.now().isoformat()

        self.metrics.navigation_history.append({
            "from_url": current_url,
            "to_url": target_url,
            "timestamp": timestamp
        })

        await self.logs_manager.info(f"Navigation path: {current_url} -> {target_url}")
        await self.logs_manager.debug(f"Navigation timestamp: {timestamp}")

    async def _monitor_rate_limits(self):
        """Monitor and log rate limiting status."""
        await self.logs_manager.debug("Checking rate limit status")
        try:
            rate_limited = await self.dom_service.check_element_present(
                '.rate-limit-message, .too-many-requests',
                timeout=1000
            )

            if rate_limited:
                await self.logs_manager.warning("Rate limiting detected")
                delay = self.settings.get('rate_limit_delay', TimingConstants.BASE_RETRY_DELAY)
                await self.logs_manager.info(f"Applying rate limit delay: {delay}ms")
                return True

            return False

        except Exception as e:
            await self.logs_manager.error(f"Error checking rate limits: {str(e)}")
            return False

    async def navigate_with_confidence(self, target: str):
        """Navigate to a URL and report the actual outcome."""
        success, confidence = await self.navigate(
            lambda: self.dom_service.goto(target), {"step": "navigate", "target": target}
        )
        await self.telemetry.track_event(
            "navigation_attempt",
            {"target": target},
            success=success,
            confidence=confidence,
        )
        return success, confidence

    # -----------------------------------------
    # Additional Step Implementations
    # -----------------------------------------
    async def _verify_login_status(self):
        """Verify user is logged in."""
        await self.logs_manager.info("Verifying login status...")
        if not await self.dom_service.check_element_present(
            ", ".join(self.locators.LOGGED_IN_INDICATOR), timeout=3000
        ):
            await self.logs_manager.error("User not logged in.")
            raise Exception("User not logged in.")

    async def _navigate_to_jobs_page(self):
        """Navigate to LinkedIn's jobs page."""
        await self.logs_manager.info("Navigating to jobs page...")
        target = self.settings.get('job_url') or "https://www.linkedin.com/jobs/"
        await self.dom_service.goto(target)
        found = await self.dom_service.check_element_present(
            self.locators.EASY_APPLY_BUTTON if self.settings.get('job_url') else ".jobs-search-results-list",
            timeout=5000
        )
        if not found:
            await self.logs_manager.error("Jobs page not loaded properly")
            raise Exception("Jobs page not loaded properly")

    async def _fill_search_form(self):
        """Fill out job search form."""
        await self.logs_manager.info("Filling search form...")
        await self.dom_service.type_text(
            self.locators.SEARCH_INPUT,
            self.settings.get('job_title', '')
        )
        await self.dom_service.type_text(
            self.locators.LOCATION_INPUT,
            self.settings.get('location', '')
        )
        await self.dom_service.click_element("button.jobs-search-box__submit-button")
        # Wait for results
        found = await self.dom_service.check_element_present(
            ".jobs-search-results-list",
            timeout=5000
        )
        if not found:
            await self.logs_manager.error("Search results not loaded")
            raise Exception("Search results not loaded")

    async def _click_apply_button(self):
        """Click the 'Apply' button on a job posting."""
        await self.logs_manager.info("Clicking apply button...")
        await self.dom_service.click_element(self.locators.EASY_APPLY_BUTTON)
        # Verify apply modal opened
        modal_open = await self.dom_service.check_element_present(
            ".jobs-easy-apply-modal",
            timeout=3000
        )
        if not modal_open:
            await self.logs_manager.error("Apply modal did not appear")
            raise Exception("Apply modal did not appear")

    async def _handle_user_profile(self):
        """Retrieve or update user profile data via user_profile_agent."""
        await self.logs_manager.info("Handling user profile...")
        # Example usage:
        if self.settings.get('form_data'):
            return True
        user_id = self.settings.get('user_id')
        if not user_id:
            raise ValueError('Configure a user_id or application form_data')
        profile = await self.user_profile_agent.get_profile(user_id)
        if not profile:
            await self.logs_manager.error("User profile not found or could not load.")
            raise Exception("User profile not found or could not load.")
        profile_data = profile.model_dump()
        self.settings['form_data'] = {
            key: value for key, value in {
                'full_name': profile_data.get('name'),
                'email': profile_data.get('email'),
                'phone': profile_data.get('phone'),
                'location': profile_data.get('location'),
                'cv_file': self.settings.get('cv_path') or profile_data.get('current_cv_path'),
            }.items() if value is not None
        }

    async def _fill_application_form(self):
        """Fill out the job application form (e.g., phone, address) with form_filler_agent."""
        await self.logs_manager.info("Filling application form with form_filler_agent...")
        form_data = self.settings.get("form_data")
        form_mapping = self.settings.get("form_mapping")
        if not isinstance(form_data, dict) or not form_data:
            raise ValueError("Application form_data is required")
        if not isinstance(form_mapping, dict) or not form_mapping:
            raise ValueError("Application form_mapping is required")
        success = await self.form_filler_agent.fill_form(form_data, form_mapping)
        if not success:
            await self.logs_manager.error("Form filling failed via form_filler_agent.")
            raise Exception("Form filling failed via form_filler_agent.")

    async def _validate_form(self):
        """Validate the form before submission (client-side checks)."""
        await self.logs_manager.info("Validating form data...")
        # Could check for error banners or missing fields:
        error_banner = await self.dom_service.check_element_present(
            ".artdeco-inline-feedback--error", timeout=2000
        )
        if error_banner:
            await self.logs_manager.error("Form validation error encountered")
            raise Exception("Form validation error encountered")
        if not await self._verify_form_state():
            raise ValueError("Required application fields are invalid")

    async def _submit_application(self):
        """Submit the application form."""
        await self.logs_manager.info("Submitting application form...")
        success = await self.form_filler_agent.submit_form(
            self.settings.get("submit_selector", "button[aria-label='Submit application']"),
            success_selector=self.settings.get(
                "application_success_selector", ".application-success, .artdeco-inline-feedback--success"
            ),
        )
        if not success:
            raise RuntimeError("Application submission was not confirmed")

    async def _track_application(self):
        """Track the application via tracker_agent."""
        await self.logs_manager.info("Tracking application with tracker_agent...")
        await self.tracker_agent.log_activity(
            activity_type="application_tracking",
            details="Tracked after final submission",
            status="info",
            agent_name="AINavigator"
        )

    async def _login_step(self):
        """Perform login if needed (placeholder)."""
        await self._verify_login_status()
        # e.g., credentials_agent usage:
        # success = await self.credentials_agent.login_to_platform("LinkedIn")
        # if not success: raise Exception("Login failed")

    # -----------------------------------------
    # CAPTCHA Handling
    # -----------------------------------------
    async def _check_for_captcha(self) -> bool:
        """Return True if a captcha is present on the page."""
        await self.logs_manager.debug("Checking for CAPTCHA presence")
        try:
            # e.g. self.locators.LINKEDIN_CAPTCHA_IMAGE or something
            captcha_present = await self.dom_service.check_element_present(
                "img.captcha__image", timeout=2000
            )
            if captcha_present:
                await self.logs_manager.warning("CAPTCHA detected on page")
            return captcha_present
        except Exception as e:
            await self.logs_manager.error(f"Error checking for CAPTCHA: {str(e)}")
            return False

    async def _ensure_no_captcha(self):
        if await self._check_for_captcha():
            await self._handle_captcha()

    async def _handle_captcha(self):
        """Solve or handle captcha with credentials_agent."""
        await self.logs_manager.info("Handling CAPTCHA...")
        try:
            # For example:
            solution = await self.credentials_agent.handle_captcha("img.captcha__image")
            if not solution:
                await self.logs_manager.error("CAPTCHA solving failed or user skipped")
                raise Exception("Captcha solving failed or user skipped")
            await self.logs_manager.info("CAPTCHA solved successfully")
        except Exception as e:
            await self.logs_manager.error(f"CAPTCHA handling failed: {str(e)}")
            raise

    # -----------------------------------------
    # Navigation Internals
    # -----------------------------------------
    async def _execute_step(self, step_name: str) -> Tuple[bool, float]:
        """Convert the step_name into an actual action method, then call `navigate`."""
        await self.logs_manager.debug(f"Preparing to execute step: {step_name}")

        step_actions = {
            # Navigation steps
            "check_login": self._verify_login_status,
            "login": self._login_step,
            "check_captcha": self._ensure_no_captcha,
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
            await self.logs_manager.error(f"Unknown step: '{step_name}'")
            return False, 0.0

        action_method = step_actions[step_name]
        await self.logs_manager.debug(f"Mapped step '{step_name}' to method: {action_method.__name__}")

        # Check for rate limiting before executing step
        if await self._monitor_rate_limits():
            await self.logs_manager.warning(f"Rate limiting detected before step: {step_name}")
            await self._handle_rate_limit_delay()

        # Track state transition
        await self._handle_state_transition(
            from_state=self.metrics.last_state,
            to_state=step_name,
            context={"action": action_method.__name__}
        )

        context = {"step": step_name}
        return await self.navigate(action_method, context)

    async def _calculate_confidence(self, action, context) -> float:
        """Naive confidence calculation example."""
        step = context.get("step", "")
        await self.logs_manager.debug(f"Calculating confidence for step: {step}")
        # For demonstration, a uniform confidence or a slight variation
        if step in ["handle_captcha", "submit_application"]:
            await self.logs_manager.debug(f"Using reduced confidence (0.85) for critical step: {step}")
            return 0.85
        return 1.0

    async def _log_success(self, action, context, confidence):
        step = context.get("step", "unknown")
        await self.logs_manager.info(f"Step '{step}' succeeded with confidence={confidence:.2f}")

    async def _handle_retry(self, action, context, confidence, error_msg):
        step = context.get("step", "unknown")
        await self.logs_manager.warning(f"Step '{step}' retry {self.retry_count}, error={error_msg}")
        return await self.navigate(action, context)

    async def _handle_failure(self, action, context, confidence, error_msg):
        step = context.get("step", "unknown")
        await self.logs_manager.error(f"Step '{step}' - max retries reached. Failing. Error={error_msg}")
        return False, confidence

    async def _handle_low_confidence(self, action, confidence):
        await self.logs_manager.warning(f"Low confidence={confidence:.2f}, skipping step.")
        return False, confidence

    # Add new step implementations
    async def _handle_rate_limit_delay(self):
        """Handle rate limit delay with exponential backoff."""
        delay = self.settings.get('rate_limit_delay', TimingConstants.BASE_RETRY_DELAY)
        await self.logs_manager.info(f"Rate limit delay: {delay}ms")
        await self.logs_manager.debug("Starting rate limit delay sleep")
        await asyncio.sleep(delay / 1000)  # Convert ms to seconds
        await self.logs_manager.debug("Completed rate limit delay")

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
        await self.logs_manager.info("Verifying previous action...")
        try:
            # 1. Check page responsiveness
            await self.logs_manager.debug("Checking page responsiveness")
            if not await self.dom_service.check_element_present('body', timeout=2000):
                return False

            # 2. Check for error banners/messages
            await self.logs_manager.debug("Checking for error banners")
            error_present = await self.dom_service.check_element_present(
                '.error-banner, .error-message, .alert-error, .notification-error',
                timeout=1000
            )
            if error_present:
                await self.logs_manager.warning("Error banner detected during verification")
                return False

            # 3. Check for CAPTCHA presence
            await self.logs_manager.debug("Checking for CAPTCHA presence")
            captcha_present = await self.dom_service.check_element_present(
                'img.captcha__image, .recaptcha-checkbox-border, iframe[title*="reCAPTCHA"]',
                timeout=1000
            )
            if captcha_present:
                await self.logs_manager.warning("CAPTCHA detected during verification")
                return False

            # 4. Verify DOM tree health
            await self.logs_manager.debug("Verifying DOM tree health")
            try:
                dom_tree = await self.dom_service.get_dom_tree(highlight=False)
                if not dom_tree or not dom_tree.children:
                    await self.logs_manager.warning("DOM tree appears corrupted")
                    return False
            except Exception as e:
                await self.logs_manager.error(f"DOM tree verification failed: {str(e)}")
                return False

            # 5. Check for rate limiting indicators
            await self.logs_manager.debug("Checking for rate limiting")
            rate_limited = await self.dom_service.check_element_present(
                '.rate-limit-message, .too-many-requests',
                timeout=1000
            )
            if rate_limited:
                await self.logs_manager.warning("Rate limiting detected during verification")
                return False

            # 6. Verify clickable elements are accessible
            await self.logs_manager.debug("Verifying clickable elements")
            try:
                clickable_elements = await self.dom_service.get_clickable_elements(highlight=False)
                if not clickable_elements:
                    await self.logs_manager.warning("No clickable elements found - possible page issue")
                    return False
            except Exception as e:
                await self.logs_manager.error(f"Clickable elements verification failed: {str(e)}")
                return False

            # 7. Basic DOM health check
            await asyncio.sleep(TimingConstants.VERIFICATION_DELAY / 1000)
            await self.logs_manager.info("Verification completed successfully")
            return True

        except Exception as e:
            await self.logs_manager.error(f"Verification failed: {str(e)}")
            return False

    async def _double_verify_action(self):
        """More thorough verification for critical steps."""
        await self.logs_manager.info("Double verification of previous action...")
        first_check = await self._verify_action()  # First verification
        if not first_check:
            return False

        await asyncio.sleep(TimingConstants.EXTENDED_VERIFICATION_DELAY / 1000)
        return await self._verify_action()  # Second verification

    async def _handle_extended_wait(self):
        """Handle extended wait period."""
        await self.logs_manager.info("Starting extended wait period...")
        try:
            await self.logs_manager.debug(f"Waiting for {TimingConstants.EXTENDED_WAIT_DELAY}ms")
            await asyncio.sleep(TimingConstants.EXTENDED_WAIT_DELAY / 1000)
            await self.logs_manager.info("Extended wait completed")
        except Exception as e:
            await self.logs_manager.error(f"Error during extended wait: {str(e)}")
            raise

    async def _handle_recovery_check(self):
        """
        Check if recovery is needed by verifying:
        1. Page state (not error/404)
        2. User session validity
        3. DOM health
        4. Network conditions
        """
        await self.logs_manager.info("Checking recovery status...")
        try:
            # 1. Check page state
            await self.logs_manager.debug("Checking page state")
            current_url = self.page.url
            if "error" in current_url.lower() or "404" in current_url:
                await self.logs_manager.warning("Error or 404 page detected")
                return False

            # 2. Verify user session
            await self.logs_manager.debug("Verifying user session")
            session_valid = await self.dom_service.check_element_present(
                ", ".join(self.locators.LOGGED_IN_INDICATOR),
                timeout=2000
            )
            if not session_valid:
                await self.logs_manager.warning("User session appears invalid")
                return False

            # 3. Check DOM health
            await self.logs_manager.debug("Checking DOM health")
            try:
                if not await self.dom_service.check_element_present('body', timeout=2000):
                    return False
            except Exception:
                await self.logs_manager.warning("DOM health check failed")
                return False

            # 4. Check for rate limiting indicators
            await self.logs_manager.debug("Checking for rate limiting")
            rate_limited = await self.dom_service.check_element_present(
                '.rate-limit-message, .too-many-requests',
                timeout=1000
            )
            if rate_limited:
                await self.logs_manager.warning("Rate limiting detected")
                return False

            await self.logs_manager.info("Recovery check completed successfully")
            return True

        except Exception as e:
            await self.logs_manager.error(f"Recovery check failed: {str(e)}")
            return False

    async def _handle_state_restoration(self):
        """
        Restore previous state by:
        1. Verifying page context
        2. Checking form state
        3. Validating navigation state
        4. Ensuring proper login state
        """
        await self.logs_manager.info("Restoring previous state...")
        try:
            # 1. Verify page context
            await self.logs_manager.debug("Verifying page context")
            current_url = self.page.url
            if not await self._verify_page_context(current_url):
                await self.logs_manager.warning("Page context verification failed")
                return False

            # 2. Check form state if applicable
            await self.logs_manager.debug("Checking form state")
            if await self.dom_service.check_element_present('form', timeout=1000):
                form_valid = await self._verify_form_state()
                if not form_valid:
                    await self.logs_manager.warning("Form state verification failed")
                    return False

            # 3. Validate navigation state
            await self.logs_manager.debug("Validating navigation state")
            nav_valid = await self._verify_navigation_state()
            if not nav_valid:
                await self.logs_manager.warning("Navigation state verification failed")
                return False

            # 4. Verify login state
            await self.logs_manager.debug("Verifying login state")
            login_valid = await self.dom_service.check_element_present(
                ", ".join(self.locators.LOGGED_IN_INDICATOR),
                timeout=2000
            )
            if not login_valid:
                await self.logs_manager.warning("Login state verification failed")
                return False

            await self.logs_manager.info("State restoration completed successfully")
            return True

        except Exception as e:
            await self.logs_manager.error(f"State restoration failed: {str(e)}")
            return False

    async def _verify_page_context(self, current_url: str) -> bool:
        """Helper to verify the current page context."""
        await self.logs_manager.debug(f"Verifying page context for URL: {current_url}")
        try:
            # Check if we're on an expected page type
            parsed_url = urlsplit(current_url)
            host = parsed_url.hostname or ""
            is_valid = (
                parsed_url.scheme == "https"
                and (host == "linkedin.com" or host.endswith(".linkedin.com"))
                and any(parsed_url.path.startswith(path) for path in ("/jobs", "/in/", "/feed"))
            )
            if not is_valid:
                await self.logs_manager.warning(f"Current URL does not match any expected patterns: {current_url}")
            return is_valid
        except Exception as e:
            await self.logs_manager.error(f"Error verifying page context: {str(e)}")
            return False

    async def _verify_form_state(self) -> bool:
        """Helper to verify form state if present."""
        await self.logs_manager.debug("Verifying form state")
        try:
            # Check for common form elements
            required_fields = await self.dom_service.query_selector_all(
                'input[required], select[required], textarea[required]'
            )

            await self.logs_manager.debug(f"Found {len(required_fields)} required form fields")

            # Verify required fields have values
            for field in required_fields:
                field_type = await field.get_attribute('type')
                if field_type in {'checkbox', 'radio'}:
                    if not await field.evaluate('element => element.checkValidity()'):
                        return False
                    continue
                value = await field.input_value()
                if not value:
                    await self.logs_manager.warning(f"Required field missing value: {await field.get_attribute('name')}")
                    return False

            return True
        except Exception as e:
            await self.logs_manager.error(f"Error verifying form state: {str(e)}")
            return False

    async def _verify_navigation_state(self) -> bool:
        """Helper to verify navigation state."""
        await self.logs_manager.debug("Verifying navigation state")
        try:
            # Check for common navigation elements
            nav_elements = [
                'nav',
                '.global-nav',
                '.navigation-bar'
            ]

            for selector in nav_elements:
                if await self.dom_service.check_element_present(selector, timeout=1000):
                    await self.logs_manager.debug(f"Found navigation element: {selector}")
                    return True

            await self.logs_manager.warning("No navigation elements found")
            return False
        except Exception as e:
            await self.logs_manager.error(f"Error verifying navigation state: {str(e)}")
            return False

    async def _handle_extended_verification(self):
        """
        More thorough verification for critical steps.
        Includes multiple checks and longer delays.
        """
        await self.logs_manager.info("Performing extended verification...")
        try:
            # First basic verification
            if not await self._verify_action():
                await self.logs_manager.warning("Initial verification check failed")
                return False

            # Additional delay
            await self.logs_manager.debug(f"Waiting {TimingConstants.EXTENDED_VERIFICATION_DELAY}ms for extended verification")
            await asyncio.sleep(TimingConstants.EXTENDED_VERIFICATION_DELAY / 1000)

            # Check for specific error conditions
            error_conditions = [
                '.error-notification',
                '.warning-message',
                '.validation-error',
                '.rate-limit-warning'
            ]

            for selector in error_conditions:
                if await self.dom_service.check_element_present(selector, timeout=1000):
                    await self.logs_manager.warning(f"Extended verification failed: found error condition '{selector}'")
                    return False

            # Final verification
            final_check = await self._verify_action()
            if final_check:
                await self.logs_manager.info("Extended verification completed successfully")
            else:
                await self.logs_manager.warning("Final verification check failed")
            return final_check

        except Exception as e:
            await self.logs_manager.error(f"Extended verification failed with error: {str(e)}")
            return False

    async def _execute_action(self, action):
        """Execute action with DOM-based fallback if primary action fails."""
        start_time = time.time()
        action_name = action.__name__

        await self.logs_manager.debug(f"Executing action: {action_name}")
        try:
            # Log current URL before action
            current_url = self.page.url

            result = await action()

            # Log URL after action if it changed
            new_url = self.page.url
            if new_url != current_url:
                await self._log_navigation_path(current_url, new_url)

            duration = time.time() - start_time
            await self._track_performance(action_name, duration)
            await self.logs_manager.debug(f"Action {action_name} completed successfully in {duration:.2f}s")
            return result

        except Exception as e:
            duration = time.time() - start_time
            await self.logs_manager.warning(f"Primary action failed after {duration:.2f}s, attempting DOM fallback: {str(e)}")

            # Track the error
            self.metrics.error_counts[action_name] += 1

            # fallback to DOM-based approach
            elements = await self.dom_service.get_clickable_elements(highlight=True)
            result = await self._handle_dom_fallback(elements, action)
            if result is None or result is False:
                raise
            return result

    async def _handle_dom_fallback(self, elements, action):
        """AI-driven fallback logic when primary action fails."""
        action_name = action.__name__
        await self.logs_manager.info(f"Fallback triggered for {action_name}. Checking clickable elements in DOM...")

        if not elements:
            await self.logs_manager.warning(f"No clickable elements found in DOM fallback for {action_name}")
            return None

        await self.logs_manager.debug(f"Found {len(elements)} potential elements for fallback")

        # Track state transition to fallback
        await self._handle_state_transition(
            from_state=self.metrics.last_state,
            to_state="dom_fallback",
            context={
                "action": action_name,
                "elements_found": len(elements)
            }
        )

        # You could add logic to pick the best element from `elements` if your plan is unclear
        return None
