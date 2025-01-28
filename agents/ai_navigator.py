"""
AI-driven navigation with confidence scoring, DOM interaction, and a minimal AI Master-Plan.

Architecture:
------------
This module provides intelligent navigation capabilities while maintaining a clear
separation of concerns:

1. Navigation Logic (This Module)
   - Confidence-based decision making
   - Fallback strategy orchestration
   - Minimal AI Master-Plan for multi-step flows (MVP)
   - Navigation outcome tracking
   - Error recovery management

2. DOM Interactions (via DomService)
   - Element discovery and interaction
   - Optional bounding-box annotation (in future expansions)
   - Basic DOM operations (click, fill, etc.)
   - DOM tree traversal if needed
   - Highlighting and visual feedback
   - Basic DOM operations

3. Selector Management (via LinkedInLocators or fallback)
   - Centralized selector definitions for site-specific interactions
   - Platform-specific element paths
   - Site-based fallback if Master-Plan or bounding-box fails
   - Selector versioning and fallbacks

Current Status: MVP with Basic Master-Plan
-----------------------------------------
- We have introduced a lightweight "AI Master-Plan" concept: a short list of steps
  that the agent tries to follow in order (e.g. "Open job page → Fill search → Apply → …")
- Each step uses confidence-based navigation logic from `ConfidenceScorer` or falls
  back to site-specific selectors if confidence is too low.
- Primary focus is on implementing robust DOM interaction patterns while
  maintaining AI-driven decision making capabilities.

TODO:
-----
Navigation Logic:
- Expand the Master-Plan to handle more advanced scenario branching
- Integrate with learning_pipeline.py for outcome tracking
- Add GPT-based decision making for highly dynamic pages
- Add robust error handling for multi-step flows
- Performance monitoring and metrics

DOM Integration:
- Migrate all direct DOM operations to DomService
- Implement confidence-based element selection
- Add telemetry for DOM operation success rates
- Setup proper error recovery patterns
- Test with various page layouts and states

Dependencies:
------------
- DomService: For all direct DOM interactions
- LinkedInLocators: Provides standardized selectors
- TelemetryManager: Tracks navigation performance and outcomes
- ConfidenceScorer / learning_pipeline: For confidence-based decisions

Usage:
------
The AINavigator should be instantiated with a page object and optional
confidence thresholds. All DOM interactions should be performed through
the DomService instance, while navigation logic and fallback strategies
remain in this module.

Example:
    navigator = AINavigator(page, min_confidence=0.8)
    success, confidence = await navigator.navigate(action, context)

Master-Plan Example:
    navigator = AINavigator(page)
    master_plan = ["check_login", "search_jobs", "click_apply_button"]
    success, confidence = await navigator.execute_master_plan(master_plan)
    
    if success:
        print("All plan steps completed successfully with confidence:", confidence)
    else:
        print("Master-Plan encountered an error or low confidence step.")
"""

from typing import Tuple
from utils.telemetry import TelemetryManager
from locators.linkedin_locators import LinkedInLocators
from utils.dom.dom_service import DomService

class AINavigator:
    def __init__(self, page, min_confidence=0.8, max_retries=3):
        """Initialize navigator with required services."""
        self.page = page
        self.min_confidence = min_confidence
        self.max_retries = max_retries
        self.retry_count = 0
        
        # Initialize services
        self.dom_service = DomService(page)
        self.telemetry = TelemetryManager()
        self.locators = LinkedInLocators()  # Added for fallback scenarios
        
    async def navigate(self, action, context):
        """
        Main navigation method with confidence scoring.
        Returns (success: bool, confidence: float).
        """
        confidence = await self._calculate_confidence(action, context)
        
        if confidence >= self.min_confidence:
            try:
                result = await self._execute_action(action)
                await self._log_success(action, context, confidence)
                return True, confidence
            except Exception as e:
                self.retry_count += 1
                if self.retry_count < self.max_retries:
                    return await self._handle_retry(action, context, confidence, str(e))
                return await self._handle_failure(action, context, confidence, str(e))
        else:
            return await self._handle_low_confidence(action, confidence)

    async def navigate_with_confidence(self, target):
        """Track navigation attempts with telemetry."""
        await self.telemetry.track_event(
            "navigation_attempt",
            {"target": target},
            success=True,
            confidence=self.min_confidence
        )

    async def _execute_action(self, action):
        """
        Execute action with DOM-based fallback if primary action fails.
        Uses DomService for all DOM interactions.
        """
        try:
            # Try primary action first
            result = await action()
            return result
        except Exception:
            # Fallback to DOM-based approach using DomService
            elements = await self.dom_service.get_clickable_elements(highlight=True)
            return await self._handle_dom_fallback(elements, action)

    async def _handle_dom_fallback(self, elements, action):
        """
        AI-driven fallback logic when primary action fails.
        Still uses DomService for actual DOM operations.
        """
        print("[AINavigator] Fallback triggered. Analyzing clickable elements...")
        # TODO: Implement AI selection logic here
        # Example: Filter elements, calculate confidence, then use dom_service to interact
        return None

    async def _calculate_confidence(self, action, context):
        """Calculate confidence score for navigation action."""
        # TODO: Implement real confidence calculation
        return 1.0

    async def _log_success(self, action, context, confidence):
        """Log successful navigation actions."""
        print(f"[AINavigator] Action succeeded with confidence={confidence}")

    async def _handle_retry(self, action, context, confidence, error_msg):
        """Handle retry attempts with exponential backoff."""
        print(f"[AINavigator] Retry attempt {self.retry_count}, error={error_msg}")
        return await self.navigate(action, context)

    async def _handle_failure(self, action, context, confidence, error_msg):
        """Handle final failure after max retries."""
        print(f"[AINavigator] Max retries reached. Failing. Error={error_msg}")
        return False, confidence

    async def _handle_low_confidence(self, action, confidence):
        """Handle cases where confidence is below threshold."""
        print(f"[AINavigator] Low confidence={confidence}. Aborting.")
        return False, confidence

    async def execute_master_plan(self, plan_steps) -> Tuple[bool, float]:
        """
        Execute a series of navigation steps in order.
        Returns (success: bool, confidence: float).
        """
        overall_confidence = 1.0
        
        # Step-to-action mapping
        step_actions = {
            "open_job_page": self._navigate_to_jobs_page,
            "fill_search": self._fill_search_form,
            "apply": self._click_apply_button,
            "check_login": self._verify_login_status
        }
        
        for step in plan_steps:
            try:
                if step not in step_actions:
                    print(f"[AINavigator] Unknown step: '{step}'")
                    return False, 0.0
                
                action_method = step_actions[step]
                context = {"step": step}
                
                success, confidence = await self.navigate(action_method, context)
                overall_confidence *= confidence
                
                if not success:
                    print(f"[AINavigator] Step failed: {step}")
                    return False, overall_confidence
                    
            except Exception as e:
                print(f"[AINavigator] Error in step '{step}': {str(e)}")
                return False, overall_confidence
        
        return True, overall_confidence

    async def _navigate_to_jobs_page(self):
        """Navigate to LinkedIn's jobs page."""
        print("[AINavigator] Navigating to jobs page...")
        try:
            await self.dom_service.goto(self.locators.JOBS_URL)
            found = await self.dom_service.check_element_present(
                self.locators.JOBS_SEARCH_RESULTS,
                timeout=5000
            )
            if not found:
                raise Exception("Jobs page not loaded properly")
            return True
        except Exception as e:
            print(f"[AINavigator] Jobs page navigation failed: {str(e)}")
            raise

    async def _fill_search_form(self):
        """Fill out job search form."""
        print("[AINavigator] Filling search form...")
        try:
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
            return True
        except Exception as e:
            print(f"[AINavigator] Search form fill failed: {str(e)}")
            raise

    async def _click_apply_button(self):
        """Click apply button on job posting."""
        print("[AINavigator] Clicking apply button...")
        try:
            await self.dom_service.click_element(self.locators.APPLY_BUTTON)
            
            # Verify apply modal opened
            modal_open = await self.dom_service.check_element_present(
                self.locators.APPLY_MODAL,
                timeout=3000
            )
            if not modal_open:
                raise Exception("Apply modal did not appear")
            return True
        except Exception as e:
            print(f"[AINavigator] Apply button click failed: {str(e)}")
            raise

    async def _verify_login_status(self):
        """Verify user is logged in."""
        print("[AINavigator] Verifying login status...")
        try:
            is_logged_in = await self.dom_service.check_element_present(
                self.locators.PROFILE_BUTTON,
                timeout=3000
            )
            if not is_logged_in:
                raise Exception("User not logged in")
            return True
        except Exception as e:
            print(f"[AINavigator] Login verification failed: {str(e)}")
            raise 