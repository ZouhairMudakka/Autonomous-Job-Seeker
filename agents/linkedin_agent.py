"""
LinkedIn Agent

Vision:
-------
An autonomous AI agent capable of intelligently navigating LinkedIn's job ecosystem with minimal human intervention. 
The agent should understand natural language instructions, make intelligent decisions, and fall back to systematic 
approaches only when needed.

Autonomy Levels:
---------------
1. Basic Automation (Current)
   - Systematic approach to job search and application
   - Pre-defined patterns and workflows
   - Direct user control for major decisions

2. Enhanced Pattern Recognition (Next)
   - Learning from successful interactions
   - Basic decision-making capabilities
   - Systematic approaches as primary fallback

3. Guided Autonomy (Short-term)
   - Natural language instruction processing
   - Context-aware decision making
   - Proactive error prevention
   - Systematic approaches as secondary fallback

4. Full Autonomy (Long-term)
   - Independent strategy formulation
   - Self-optimizing workflows
   - Predictive problem solving
   - Systematic approaches as last resort

Current Functionality:
--------------------
1. Navigation to the 'Jobs' page
2. Searching & filtering jobs
3. Checking if a job posting offers 'Easy Apply'
4. Basic error handling and recovery
5. Session management and verification
6. CSV logging of activities

Progressive AI Enhancement Plan:
-----------------------------
1. Intelligent Decision Making
   - Natural language understanding
   - Context-aware actions
   - Learning from past interactions
   - Autonomous strategy adjustment
   - Self-diagnostic capabilities

2. Autonomous Navigation
   - Self-optimizing search patterns
   - Dynamic layout adaptation
   - Intelligent element detection
   - Progressive learning from interactions
   - Fallback to systematic navigation

3. Smart Application Strategy
   - Autonomous application decisions
   - Intelligent form filling
   - Dynamic response generation
   - Self-improving success rates
   - Systematic fallback for critical steps

4. Intelligent Engagement
   - Smart recruiter interaction
   - Context-aware company engagement
   - Autonomous follow-up planning
   - Strategic relationship building
   - Fallback to basic engagement patterns

5. Adaptive Error Recovery
   - Self-diagnostic capabilities
   - Autonomous problem resolution
   - Dynamic fallback strategy selection
   - Progressive learning from errors
   - Systematic approach fallback when needed

6. Intelligent Search & Discovery
   - Self-optimizing search strategies
   - Dynamic pagination handling
   - Intelligent filter adjustment
   - Pattern recognition in search results
   - Learning from search effectiveness

7. Smart Data Collection & Analytics
   - Autonomous data gathering and analysis
   - Pattern recognition in successful applications
   - Strategic insights generation
   - Predictive analytics for job success
   - Self-improving recommendation system

8. Adaptive Error Handling
   - Self-diagnostic capabilities
   - Autonomous problem resolution
   - Dynamic fallback strategy selection
   - Progressive learning from errors
   - Systematic approach fallback when needed

9. User Preference Learning
   - Natural language preference understanding
   - Dynamic strategy adaptation
   - Learning from user feedback
   - Autonomous preference refinement
   - Fallback to explicit settings when needed

Implementation Strategy:
----------------------
1. Progressive Enhancement
   - Start with robust systematic approaches as foundation
   - Gradually layer AI capabilities on top
   - Maintain systematic approaches as reliable fallbacks
   - Continuous learning and improvement

2. Fallback Mechanism
   - AI-first approach for all operations
   - Monitoring of AI performance and decisions
   - Graceful degradation to systematic approaches
   - Learning from fallback incidents

3. User Control
   - Natural language instruction processing
   - Configurable autonomy levels
   - Override capabilities for user control
   - Transparent decision reporting

Dependencies & Requirements:
--------------------------
- Premium membership for certain features
- Stable internet connection
- Valid LinkedIn login
- Proper permissions setup
- AI processing capabilities
- Learning model integration

Notes:
------
- Features vary between Premium/Free accounts
- AI capabilities will be progressively enhanced
- Systematic approaches remain as fallbacks
- User can always override AI decisions
- Continuous learning from interactions

Assumes user is already logged in. If user is forcibly logged out, the agent raises an exception.

TODO (AI Integration):
- Replace direct page.click() calls with ai_navigator.navigate()
- Add confidence scoring for critical actions
- Integrate with learning pipeline for outcome tracking
- Add fallback to systematic approach when AI confidence is low
- Setup proper error handling for AI navigation
"""

import asyncio
import random
import csv
from pathlib import Path
from typing import Dict, Optional, Any, List
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from constants import TimingConstants, Selectors, Messages
from time import perf_counter
from storage.logs_manager import LogsManager

# We'll also import your GeneralAgent or FormFillerAgent if needed:
# from agents.general_agent import GeneralAgent
# from agents.form_filler_agent import FormFillerAgent

class LinkedInAgent:
    def __init__(
        self,
        page: Page,
        controller,
        default_timeout: float = TimingConstants.DEFAULT_TIMEOUT,
        min_delay: float = TimingConstants.HUMAN_DELAY_MIN,
        max_delay: float = TimingConstants.HUMAN_DELAY_MAX,
        logs_manager: Optional[LogsManager] = None
    ):
        """
        Args:
            page (Page): A Playwright Page object where the user is already logged in.
            controller: A controller object.
            default_timeout (float): Default wait in ms for elements.
            min_delay (float): Minimum random delay for human-like interactions.
            max_delay (float): Maximum random delay for human-like interactions.
            logs_manager (LogsManager, optional): Instance of LogsManager for async logging.
        """
        self.page = page
        self.controller = controller
        self.logs_manager = logs_manager or controller.logs_manager
        self.default_timeout = min(default_timeout, TimingConstants.MAX_WAIT_TIME)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.is_paused = False

        # A CSV to log applied jobs
        self.applied_jobs_csv = "jobs_applied.csv"

    async def pause(self):
        """Pause the agent's operations."""
        await self._log_state_change("running", "paused", "User requested pause")
        await self._log_info(Messages.PAUSE_MESSAGE)
        self.is_paused = True

    async def resume(self):
        """Resume the agent's operations."""
        await self._log_state_change("paused", "running", "User requested resume")
        await self._log_info(Messages.RESUME_MESSAGE)
        self.is_paused = False

    async def _check_if_paused(self):
        """Check pause state with proper async handling."""
        while self.is_paused:
            try:
                await asyncio.sleep(TimingConstants.POLL_INTERVAL)
                # Check for cancellation during pause
                if asyncio.current_task().cancelled():
                    raise asyncio.CancelledError()
            except asyncio.CancelledError:
                await self._log_state_change("paused", "cancelled", "Operation cancelled while paused")
                raise

    async def _verify_url_is_jobs(self) -> bool:
        """Verify current URL is a LinkedIn jobs page."""
        try:
            current_url = self.page.url.lower()
            
            # Valid jobs URLs patterns
            jobs_patterns = [
                "linkedin.com/jobs",
                "linkedin.com/my-items/saved-jobs",
                "linkedin.com/job/",
                "/jobs/collections/",
                "/jobs/search",
                "/jobs/view"
            ]
            
            return any(pattern in current_url for pattern in jobs_patterns)
        except Exception as e:
            await self._log_error(f"Error checking URL: {e}")
            return False

    async def _log_navigation(self, from_url: str, to_url: str, method: str = None, success: bool = True, error: Exception = None):
        """Log page navigation attempts and results"""
        nav_msg = f"Navigation: {from_url} -> {to_url}"
        if method:
            nav_msg += f" | Method: {method}"
        if error:
            nav_msg += f" | Error: {str(error)}"
        
        if success:
            await self._log_info(nav_msg)
        else:
            await self._log_error(nav_msg)

    async def _log_selector_strategy(self, element_type: str, selectors: list, successful_selector: str = None, context: dict = None):
        """Log selector strategy attempts and results"""
        strategy_msg = f"Selector Strategy for '{element_type}'"
        if context:
            strategy_msg += f" | Context: {context}"
        await self._log_debug(strategy_msg)
        
        # Log all attempted selectors
        for selector in selectors:
            status = "✓" if selector == successful_selector else "✗"
            await self._log_debug(f"  {status} Tried: {selector}")
        
        if successful_selector:
            await self._log_info(f"Found {element_type} with: {successful_selector}")
        else:
            await self._log_warning(f"Failed to find {element_type} after trying {len(selectors)} selectors")

    async def go_to_jobs_tab(self):
        """Click the 'Jobs' button in the top LinkedIn nav bar or navigate directly as fallback."""
        try:
            current_url = self.page.url
            # First check if we're already on a jobs page
            if await self._verify_url_is_jobs():
                await self._log_info("Already on a LinkedIn jobs page")
                return True
            
            await self._log_info("Attempting to navigate to Jobs tab...")
            
            # Try clicking the jobs tab first with improved visibility handling
            try:
                # Track navigation attempt
                await self._log_navigation(
                    from_url=current_url,
                    to_url="linkedin.com/jobs",
                    method="jobs_tab_click"
                )
                
                # Define selectors for jobs tab
                jobs_tab_selectors = [
                    Selectors.LINKEDIN_JOBS_TAB,
                    "a[href='/jobs/']",
                    "a[data-link-to='jobs']",
                    "a[href*='/jobs']"
                ]
                
                # Get the jobs tab element
                jobs_tab = None
                successful_selector = None
                
                for selector in jobs_tab_selectors:
                    try:
                        jobs_tab = await self.page.query_selector(selector)
                        if jobs_tab:
                            successful_selector = selector
                            break
                    except Exception:
                        continue
                
                await self._log_selector_strategy(
                    element_type="jobs_tab",
                    selectors=jobs_tab_selectors,
                    successful_selector=successful_selector,
                    context={"current_url": current_url}
                )
                
                if jobs_tab:
                    # First ensure it's in view
                    try:
                        await jobs_tab.scroll_into_view_if_needed()
                        await self._human_delay(0.5, 1)  # Brief pause after scroll
                    except Exception as e:
                        await self._log_error("Scroll into view failed", error=e)

                    # Try to hover first (can help with dynamic menus)
                    try:
                        await jobs_tab.hover()
                        await self._human_delay(0.3, 0.7)  # Brief pause after hover
                    except Exception as e:
                        await self._log_error("Hover failed", error=e)

                    # Now attempt the click
                    await jobs_tab.click()
                    
                    # Wait for URL to change and verify
                    try:
                        await self.page.wait_for_url("**/jobs/**", timeout=5000)
                        if await self._verify_url_is_jobs():
                            await self._log_navigation(
                                from_url=current_url,
                                to_url=self.page.url,
                                method="jobs_tab_click",
                                success=True
                            )
                            return True
                    except PlaywrightTimeoutError:
                        await self._log_navigation(
                            from_url=current_url,
                            to_url=self.page.url,
                            method="jobs_tab_click",
                            success=False
                        )
                else:
                    await self._log_info("Jobs tab element not found")
                
            except Exception as e:
                await self._log_error("Failed to click jobs tab", error=e)

            # If clicking failed, try direct URL navigation
            await self._log_info("Attempting direct navigation to jobs page...")
            try:
                direct_url = "https://www.linkedin.com/jobs/"
                await self._log_navigation(
                    from_url=self.page.url,
                    to_url=direct_url,
                    method="direct_navigation"
                )
                
                await self.page.goto(direct_url, timeout=30000)
                await self._human_delay(2, 3)  # Give page time to load
                
                if await self._verify_url_is_jobs():
                    await self._log_navigation(
                        from_url=current_url,
                        to_url=self.page.url,
                        method="direct_navigation",
                        success=True
                    )
                    return True
                else:
                    await self._log_navigation(
                        from_url=current_url,
                        to_url=self.page.url,
                        method="direct_navigation",
                        success=False
                    )
            except Exception as e:
                await self._log_error("Direct URL navigation failed", error=e)
                
            raise Exception("Failed to navigate to Jobs page through any method")
            
        except Exception as e:
            await self._log_error("Error navigating to Jobs tab", error=e)
            raise

    async def process_job_listings(self, max_jobs: int = 10):
        """Process job listings with standardized timing and cancellation support."""
        try:
            job_card_count = 0
            page_number = 1

            while job_card_count < max_jobs:
                await self._check_if_paused()
                
                # First try to find the two-column layout
                left_pane = await self.page.query_selector('.jobs-search-results-list')
                
                if left_pane:
                    # Handle two-column layout (existing code remains the same)
                    await self._log_info("Processing two-column layout")
                    # ... existing two-column layout code ...
                else:
                    # Try single feed layout
                    await self._log_info("Attempting to process single feed layout")
                    jobs_data = await self._handle_single_feed_layout()
                    
                    if not jobs_data:
                        await self._log_info("No jobs found in either layout")
                        break
                    
                    for job_data in jobs_data:
                        if job_card_count >= max_jobs:
                            break
                            
                        await self._check_if_paused()
                        job_card_count += 1
                        
                        try:
                            # Click the card to show details
                            card_element = job_data.pop("card_element")
                            await card_element.scroll_into_view_if_needed()
                            await card_element.click()
                            await self._human_delay(1, 2)
                            
                            # Wait for job details to load
                            detail_selectors = [
                                ".jobs-search__right-rail",
                                ".jobs-details",
                                "[data-job-detail-container]"
                            ]
                            
                            details_loaded = False
                            for selector in detail_selectors:
                                try:
                                    await self.page.wait_for_selector(selector, timeout=5000)
                                    details_loaded = True
                                    break
                                except:
                                    continue
                            
                            if details_loaded:
                                full_job_data = await self._extract_job_details()
                                apply_status = await self._apply_to_job(full_job_data)
                                full_job_data["application_status"] = apply_status
                                await self._save_job_record(full_job_data)
                            else:
                                await self._log_info("Job details failed to load")
                                
                        except Exception as e:
                            await self._log_info(f"Error processing job in single feed: {e}")
                            continue
                    
                    # Check if we need to load more jobs
                    if job_card_count < max_jobs:
                        try:
                            # Scroll to bottom to trigger more jobs loading
                            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                            await self._human_delay(2, 3)
                        except Exception as e:
                            await self._log_info(f"Error scrolling for more jobs: {e}")
                            break

            await self._log_info(f"Finished processing {job_card_count} job listings")
            
        except asyncio.CancelledError:
            await self._log_info("Job processing cancelled gracefully")
            raise
        except Exception as e:
            await self._log_info(f"Error in process_job_listings: {e}")
            raise

    # -------------------------------------------------------------------------
    # Extract & Apply
    # -------------------------------------------------------------------------
    async def _extract_job_details(self) -> dict:
        """
        Extract relevant job info from the currently selected job detail pane.
        e.g., job title, company, location, recruiter link if visible, easy apply check.
        """
        # Example selectors, might vary if LinkedIn changes the DOM
        job_title_sel = '.jobs-details-top-card__job-title'
        company_sel = '.jobs-details-top-card__company-url'
        location_sel = '.jobs-details-top-card__bullet'
        easy_apply_sel = 'button.jobs-apply-button'  # sometimes there's text "Easy Apply" on the button
        recruiter_sel = '.jobs-poster__name'  # might be a link to the recruiter

        job_title = await self._safe_get_text(job_title_sel)
        company_name = await self._safe_get_text(company_sel)
        location = await self._safe_get_text(location_sel)

        # Check if the "Easy Apply" button exists
        easy_apply_button = await self.page.query_selector(easy_apply_sel)

        # Attempt to find recruiter name or link
        recruiter_name = await self._safe_get_text(recruiter_sel)
        # If there's a link, you might do:
        recruiter_link = None
        rec_elem = await self.page.query_selector(recruiter_sel)
        if rec_elem:
            recruiter_link = await rec_elem.get_attribute("href")  # or something if it's clickable

        return {
            "job_title": job_title,
            "company": company_name,
            "location": location,
            "is_easy_apply": True if easy_apply_button else False,
            "recruiter_name": recruiter_name,
            "recruiter_link": recruiter_link
        }

    async def _apply_to_job(self, job_data: dict) -> str:
        """
        Decide how to apply:
        - If is_easy_apply, do the "Easy Apply" flow.
        - Otherwise, see if there's a link to an external site.
        Returns a string: "applied", "redirected", "skipped", or "failed"
        """
        method = "_apply_to_job"
        context = {
            "job_title": job_data.get("job_title"),
            "company": job_data.get("company"),
            "is_easy_apply": job_data.get("is_easy_apply")
        }
        
        await self._log_debug(f"Entering {method}", context)
        
        try:
            async with self._timed_operation(method):
                await self._log_info(f"Attempting to apply to {job_data['job_title']} at {job_data['company']}")
                
                if job_data.get("is_easy_apply"):
                    await self._log_info(f"Using Easy Apply for {job_data['job_title']}")
                    try:
                        result = await self._handle_easy_apply()
                        await self._log_outcome(method, result == "applied", f"Easy Apply result: {result}")
                        return result
                    except Exception as e:
                        await self._log_error("Failed easy apply", error=e, context=context)
                        return "failed"
                else:
                    apply_button = await self.page.query_selector('a[data-control-name="jobdetails_topcard_inapply"]')
                    if apply_button:
                        await self._log_info(f"External link apply for {job_data['job_title']}")
                        result = await self._handle_external_apply(apply_button)
                        await self._log_outcome(method, result == "redirected", f"External apply result: {result}")
                        return result
                    else:
                        await self._log_info(f"No apply button found for {job_data['job_title']}, skipping.")
                        return "skipped"
                    
        except Exception as e:
            await self._log_error(f"Error in {method}", error=e, context=context)
            return "failed"

    async def _handle_easy_apply(self) -> str:
        """
        Click "Easy Apply" and fill out the form with a FormFillerAgent or direct multi-step approach.
        """
        method = "_handle_easy_apply"
        context = {}
        
        await self._log_debug(f"Entering {method}", context)
        
        try:
            async with self._timed_operation(method):
                easy_apply_btn_sel = 'button.jobs-apply-button'
                await self.page.click(easy_apply_btn_sel)
                await asyncio.sleep(TimingConstants.EASY_APPLY_MODAL_DELAY)

                # Initialize FormFillerAgent if needed
                if not hasattr(self, 'form_filler_agent'):
                    from agents.form_filler_agent import FormFillerAgent
                    self.form_filler_agent = FormFillerAgent(
                        dom_service=self.dom_service,
                        logs_manager=self.logs_manager,
                        settings=self.settings
                    )

                result = await self._multi_step_easy_apply()
                await self._log_outcome(method, result == "applied", f"Easy Apply result: {result}")
                return result
        except PlaywrightTimeoutError:
            await self._log_error("Timed out waiting for Easy Apply button", context=context)
            return "failed"
        except Exception as e:
            await self._log_error("Failed easy apply", error=e, context=context)
            return "failed"

    async def _multi_step_easy_apply(self) -> str:
        """
        Handle multi-step Easy Apply form filling.
        Returns 'applied' if successful, 'failed' otherwise.
        """
        method = "_multi_step_easy_apply"
        context = {}
        
        await self._log_debug(f"Entering {method}", context)
        
        try:
            # Step 1: Upload CV if required
            upload_selector = 'input[type="file"][name="fileId"]'
            upload_input = await self.page.query_selector(upload_selector)
            if upload_input and hasattr(self, 'cv_path'):
                await self._log_info("Uploading CV...")
                await upload_input.set_input_files(self.cv_path)
                await asyncio.sleep(TimingConstants.FILE_UPLOAD_DELAY)

            # Step 2: Handle each form step until we find the submit button
            while True:
                submit_btn_sel = 'button[aria-label="Submit application"]'
                submit_btn = await self.page.query_selector(submit_btn_sel)
                if submit_btn:
                    await submit_btn.click()
                    await asyncio.sleep(TimingConstants.FORM_SUBMIT_DELAY)
                    return "applied"

                next_btn_sel = 'button[aria-label="Continue to next step"]'
                next_btn = await self.page.query_selector(next_btn_sel)
                if next_btn:
                    await next_btn.click()
                    await asyncio.sleep(TimingConstants.FORM_FIELD_DELAY)
                else:
                    await self._log_warning("No next or submit button found.", context=context)
                    return "failed"

        except Exception as e:
            await self._log_error("Multi-step easy apply failed", error=e, context=context)
            return "failed"

    async def _handle_external_apply(self, apply_button) -> str:
        """
        Clicking an external apply link might open a new tab or redirect in the same tab.
        We'll handle a new tab scenario, pass it off to a general agent, then close the tab.
        """
        method = "_handle_external_apply"
        context = {}
        current_url = self.page.url
        
        await self._log_debug(f"Entering {method}", context)
        
        try:
            [popup] = await asyncio.gather(
                self.page.wait_for_event("popup"),
                apply_button.click()
            )
            if popup:
                popup_url = popup.url
                await self._log_navigation(
                    from_url=current_url,
                    to_url=popup_url,
                    method="popup_external_apply",
                    success=True
                )
                await self._log_info("A new tab opened for external application.")
                await popup.close()
                return "redirected"
            else:
                new_url = self.page.url
                await self._log_navigation(
                    from_url=current_url,
                    to_url=new_url,
                    method="same_tab_external_apply",
                    success=True
                )
                await self._log_info("The same tab was redirected. Handle with general agent or skip for now.")
                await asyncio.sleep(TimingConstants.PAGE_TRANSITION_DELAY)
                await self.page.go_back()
                return "redirected"
        except PlaywrightTimeoutError:
            await self._log_warning("Timed out waiting for external apply popup.", context=context)
            return "failed"
        except Exception as e:
            await self._log_error("External apply error", error=e, context=context)
            return "failed"

    # -------------------------------------------------------------------------
    # CSV Logging
    # -------------------------------------------------------------------------
    async def _save_job_record(self, job_data: dict):
        """
        Append job data to a CSV file for record-keeping.
        """
        csv_file = Path(self.applied_jobs_csv)
        file_exists = csv_file.exists()
        fieldnames = [
            "job_title", "company", "location", 
            "is_easy_apply", "recruiter_name", "recruiter_link",
            "application_status"
        ]
        try:
            with open(csv_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(job_data)
        except Exception as e:
            await self._log_error("Error saving job record", error=e)

    # -------------------------------------------------------------------------
    # Handling Missing Elements / Refresh
    # -------------------------------------------------------------------------
    async def _handle_missing_elements(self):
        """
        If we fail to find certain elements, we refresh once, 
        wait, then if it fails again, skip the job.
        """
        await self._log_info("Attempting page refresh due to missing elements.")
        await self.page.reload()
        await asyncio.sleep(TimingConstants.PAGE_TRANSITION_DELAY)

    # -------------------------------------------------------------------------
    # Captcha / Logout Detection (Placeholder)
    # -------------------------------------------------------------------------
    async def check_captcha_or_logout(self):
        """
        If LinkedIn logs out or shows a captcha, we raise an exception 
        so the orchestrator can handle user/manual intervention.
        """
        # First check login state
        if not await self._verify_login_state():
            raise Exception(f"[LinkedInAgent] {Messages.LOGOUT_MESSAGE}")
        
        # Then check for captcha (existing code)
        captcha_sel = Selectors.LINKEDIN_CAPTCHA_IMAGE
        if await self.page.query_selector(captcha_sel):
            raise Exception(f"[LinkedInAgent] {Messages.CAPTCHA_MESSAGE}")

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------
    async def _safe_get_text(self, selector: str) -> str:
        """
        Attempt to get text content from a selector; return empty string if not found.
        """
        try:
            el = await self.page.query_selector(selector)
            if el:
                txt = await el.text_content()
                return txt.strip() if txt else ""
        except:
            pass
        return ""

    async def _human_delay(self, min_sec: float = None, max_sec: float = None):
        """
        Insert a short random delay to mimic human interactions.
        Defaults to class-level min_delay/max_delay if not provided.
        """
        if min_sec is None:
            min_sec = self.min_delay
        if max_sec is None:
            max_sec = self.max_delay
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    async def handle_application_form(self, cv_path: str | Path) -> bool:
        """
        Handle job application form including CV upload.
        Skips cover letter for MVP.
        """
        try:
            # Wait for application form to load
            await self.page.wait_for_selector(Selectors.APPLICATION_FORM, 
                                            timeout=self.default_timeout)
            
            # Handle CV upload if upload field exists
            cv_upload = self.page.locator(Selectors.CV_UPLOAD_INPUT)
            if await cv_upload.count() > 0:
                await self._log_info("Uploading CV...")
                await cv_upload.set_input_files(str(cv_path))
                await self.random_delay()  # Wait for upload
            
            # Skip cover letter if requested
            cover_letter = self.page.locator(Selectors.COVER_LETTER_INPUT)
            if await cover_letter.count() > 0:
                await self._log_info("Skipping cover letter (MVP)")
                # Future: Implement cover letter handling
                pass
            
            # Submit form if possible
            submit_button = self.page.locator(Selectors.SUBMIT_APPLICATION)
            if await submit_button.count() > 0:
                await submit_button.click()
                await self.page.wait_for_load_state('networkidle')
                return True
                
            return False
            
        except Exception as e:
            await self._log_error("Error in application form", error=e)
            return False

    async def search_jobs_and_apply(self, job_title: str, location: str):
        """Main method to orchestrate searching & applying on LinkedIn."""
        method = "search_jobs_and_apply"
        context = {"job_title": job_title, "location": location}
        await self._log_debug(f"Entering {method}", context)
        
        try:
            async with self._timed_operation(method):
                await self._log_info(f"Starting job search for: '{job_title}' in '{location}'")
                
                # Check for captcha/logout
                await self.check_captcha_or_logout()
                
                # Track current URL before navigation
                current_url = self.page.url
                
                # Ensure we're on jobs page
                if not await self._verify_url_is_jobs():
                    await self.go_to_jobs_tab()
                await self._human_delay(1.5, 2.5)
                
                # Log navigation result
                await self._log_navigation(
                    from_url=current_url,
                    to_url=self.page.url,
                    method="ensure_jobs_page",
                    success=await self._verify_url_is_jobs()
                )
                
                # Check if we're in a narrow layout
                if await self._is_narrow_layout():
                    await self._log_info("Detected narrow/responsive layout")
                    if await self._handle_responsive_search(job_title, location):
                        await self._log_info("Successfully handled search in responsive layout")
                    else:
                        await self._log_info("Failed to handle responsive search, trying standard approach")
                
                # Define search selectors
                job_search_selectors = [
                    "input.jobs-search-box__text-input",
                    "input[aria-label='Search by title...']",
                    "input[aria-label*='Search jobs']",
                    "input[placeholder*='Search jobs']",
                    "input[type='text'][name*='keywords']"
                ]
                
                location_search_selectors = [
                    "input.jobs-search-box__location-input",
                    "input[aria-label*='location']",
                    "input[aria-label='City, state, or zip code']",
                    "input[placeholder*='Location']"
                ]
                
                # Track selector attempts for job title
                successful_job_selector = None
                job_filled = False
                
                for selector in job_search_selectors:
                    try:
                        await self.page.fill(selector, "")  # Clear first
                        await self.page.fill(selector, job_title)
                        await self._human_delay(0.5, 1)
                        job_filled = True
                        successful_job_selector = selector
                        break
                    except Exception as e:
                        continue
                
                await self._log_selector_strategy(
                    element_type="job_title_input",
                    selectors=job_search_selectors,
                    successful_selector=successful_job_selector,
                    context={"job_title": job_title}
                )
                
                # Track selector attempts for location
                successful_location_selector = None
                location_filled = False
                
                for selector in location_search_selectors:
                    try:
                        await self.page.fill(selector, "")  # Clear first
                        await self.page.fill(selector, location)
                        await self._human_delay(0.5, 1)
                        location_filled = True
                        successful_location_selector = selector
                        break
                    except Exception as e:
                        continue
                
                await self._log_selector_strategy(
                    element_type="location_input",
                    selectors=location_search_selectors,
                    successful_selector=successful_location_selector,
                    context={"location": location}
                )

                # Trigger search
                if job_filled or location_filled:
                    try:
                        # Try clicking search button first
                        search_button_selectors = [
                            "button[type='submit']",
                            ".jobs-search-box__submit-button",
                            "button[data-tracking-control-name='public_jobs_jobs-search-bar_base-search-bar-search-submit']"
                        ]
                        
                        button_clicked = False
                        for selector in search_button_selectors:
                            try:
                                await self.page.click(selector)
                                button_clicked = True
                                await self._log_info("Clicked search button")
                                break
                            except:
                                continue
                        
                        # If button click failed, try pressing Enter in the search fields
                        if not button_clicked:
                            await self._log_info("Search button not found, trying Enter key")
                            if job_filled:
                                await self.page.keyboard.press("Enter")
                            elif location_filled:
                                await self.page.keyboard.press("Enter")
                        
                        # Wait for results
                        await self._human_delay(2, 3)
                        await self.page.wait_for_selector(
                            ".jobs-search-results-list",
                            timeout=self.default_timeout
                        )
                        
                        await self._log_info("Search results loaded successfully")
                        await self.process_job_listings()
                        
                    except Exception as e:
                        await self._log_error("Error triggering search", error=e, context=context)
                        raise
                
                else:
                    raise Exception("Could not fill either job title or location")
                
                await self._log_outcome(method, True, f"Completed search for {job_title}")
                await self._log_debug(f"Exiting {method} successfully")
                
        except Exception as e:
            await self._log_error(f"Error in {method}", error=e, context=context)
            raise

    async def _retry_operation(self, operation, max_retries: int = 3):
        """Retry an async operation with exponential backoff."""
        for attempt in range(max_retries):
            try:
                return await operation()
            except PlaywrightTimeoutError as e:
                if attempt == max_retries - 1:
                    raise
                delay = TimingConstants.BASE_RETRY_DELAY * (TimingConstants.RETRY_BACKOFF_FACTOR ** attempt)
                await asyncio.sleep(delay)

    async def cleanup(self):
        """Cleanup resources when agent is done."""
        try:
            # Cancel any pending operations
            if hasattr(self, 'current_task'):
                self.current_task.cancel()
            
            # Close any open dialogs
            try:
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(TimingConstants.MODAL_TRANSITION_DELAY)
            except:
                pass
            
            await self.controller.tracker_agent.log_activity(
                activity_type='cleanup',
                details='Agent cleanup completed',
                status='success',
                agent_name='LinkedInAgent'
            )
        except Exception as e:
            await self._log_error("Cleanup error", error=e)

    async def _recover_from_error(self, error_type: str) -> bool:
        """Enhanced error recovery with validation."""
        try:
            if error_type == 'navigation':
                await self.page.goto('https://www.linkedin.com/jobs')
                await self.page.wait_for_load_state('networkidle')
                # Verify navigation succeeded
                current_url = self.page.url
                return 'jobs' in current_url.lower()
                
            elif error_type == 'modal':
                return await self._close_modal()
                
            elif error_type == 'session':
                return await self._refresh_session()
                
            return False
            
        except Exception as e:
            await self._log_error("Recovery failed", error=e)
            return False

    async def _close_modal(self):
        """Attempt to close any open modal dialogs."""
        try:
            close_button = await self.page.wait_for_selector(
                Selectors.LINKEDIN_MODAL_CLOSE,
                timeout=TimingConstants.DEFAULT_TIMEOUT
            )
            if close_button:
                await close_button.click()
                await asyncio.sleep(TimingConstants.MODAL_TRANSITION_DELAY)
        except PlaywrightTimeoutError:
            pass

    async def _check_session_health(self):
        """Verify session is healthy before operations."""
        try:
            # Check if still logged in
            await self.check_captcha_or_logout()
            
            # Check if page is responsive
            await self.page.evaluate('() => document.readyState')
            
            # Check for error banners
            error_banner = await self.page.query_selector(Selectors.LINKEDIN_FORM_ERROR)
            if error_banner:
                error_text = await error_banner.text_content()
                raise Exception(f"Session error: {error_text}")
            
            return True
        except Exception as e:
            await self._log_error("Session health check failed", error=e)
            return False

    async def _monitor_operation(self, operation_name: str):
        """Context manager to monitor operation performance."""
        start_time = perf_counter()
        try:
            yield
        finally:
            duration = perf_counter() - start_time
            await self.controller.tracker_agent.log_activity(
                activity_type='performance',
                details=f'{operation_name} took {duration:.2f}s',
                status='info',
                agent_name='LinkedInAgent'
            )

    async def _safe_interaction(self, element, action_type: str):
        """Safely interact with elements using proper async context."""
        try:
            async with self._monitor_operation(f"{action_type}_interaction"):
                # Verify element is still valid
                await element.wait_for_element_state('stable')
                
                if action_type == 'click':
                    await element.click()
                elif action_type == 'fill':
                    await element.fill()
                # ... other action types
                
                await self._human_delay()
                return True
                
        except PlaywrightTimeoutError:
            await self._log_warning(f"Element not stable for {action_type}")
            return False
        except Exception as e:
            await self._log_error(f"Error during {action_type}", error=e)
            return False

    async def _log_info(self, message: str):
        """Consistent logging wrapper using LogsManager"""
        await self.logs_manager.info(f"[LinkedInAgent] {message}")

    async def _log_error(self, message: str, error: Exception = None, context: dict = None):
        """Enhanced error logging with optional context"""
        error_msg = f"[LinkedInAgent] {message}"
        if error:
            error_msg += f" | Error: {str(error)}"
        if context:
            error_msg += f" | Context: {context}"
        await self.logs_manager.error(error_msg)

    async def _log_warning(self, message: str, context: dict = None):
        """Log warning messages with optional context"""
        warning_msg = f"[LinkedInAgent] {message}"
        if context:
            warning_msg += f" | Context: {context}"
        await self.logs_manager.warning(warning_msg)

    async def _log_debug(self, message: str, context: dict = None):
        """Log debug messages with optional context"""
        debug_msg = f"[LinkedInAgent] {message}"
        if context:
            debug_msg += f" | Context: {context}"
        await self.logs_manager.debug(debug_msg)

    async def _log_performance(self, operation: str, duration: float, context: dict = None):
        """Log performance metrics"""
        perf_msg = f"Performance: {operation} took {duration:.2f}s"
        if context:
            perf_msg += f" | Context: {context}"
        await self._log_debug(perf_msg)

    async def _log_state_change(self, from_state: str, to_state: str, details: str = None):
        """Log state transitions"""
        msg = f"State change: {from_state} -> {to_state}"
        if details:
            msg += f" ({details})"
        await self._log_info(msg)

    async def _log_outcome(self, operation: str, success: bool, details: str = None):
        """Log operation outcomes"""
        status = "Success" if success else "Failed"
        msg = f"Outcome: {operation} - {status}"
        if details:
            msg += f" | {details}"
        log_method = self._log_info if success else self._log_warning
        await log_method(msg)

    async def _timed_operation(self, operation_name: str):
        """Context manager for timing operations"""
        start_time = perf_counter()
        try:
            yield
        finally:
            duration = perf_counter() - start_time
            await self._log_performance(operation_name, duration)

    async def _verify_jobs_page(self) -> bool:
        """Verify we're actually on the jobs page."""
        try:
            # Check URL first (fastest check)
            if "/jobs" not in self.page.url:
                return False
            
            # Check for jobs-specific elements
            jobs_indicators = [
                Selectors.LINKEDIN_JOBS_CONTAINER,
                ".jobs-search-results",
                "[data-test-jobs-search]",
                "div[data-job-search-results]"
            ]
            
            for selector in jobs_indicators:
                try:
                    await self.page.wait_for_selector(selector, timeout=3000)
                    return True
                except:
                    continue
                
            return False
        except Exception as e:
            await self._log_error("Error verifying jobs page", error=e)
            return False

    async def _retry_with_backoff(self, operation, max_retries: int = 3):
        """Execute operation with exponential backoff."""
        for attempt in range(max_retries):
            try:
                return await operation()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                delay = TimingConstants.BASE_RETRY_DELAY * (2 ** attempt)
                await self._log_info(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)

    async def _ensure_jobs_search_ready(self) -> bool:
        """Ensure we're on jobs page and search is ready."""
        try:
            # First verify we're on jobs page
            if not await self._verify_jobs_page():
                await self.go_to_jobs_tab()
                await self._human_delay()
                
            # Wait for search box to be interactive
            search_selectors = [
                "input[aria-label*='Search jobs']",
                "input[placeholder*='Search jobs']",
                "input[type='text'][name*='keywords']",
                "input.jobs-search-box__text-input"
            ]
            
            for selector in search_selectors:
                try:
                    await self.page.wait_for_selector(selector, state="visible", timeout=3000)
                    return True
                except:
                    continue
                
            return False
        except Exception as e:
            await self._log_error("Error ensuring jobs search ready", error=e)
            return False

    async def _handle_responsive_search(self, job_title: str = None, location: str = None) -> bool:
        """Handle search when the layout is collapsed/narrow."""
        try:
            # Try to find and click the magnifier icon/button
            magnifier_selectors = [
                "button[aria-label='Search']",
                ".jobs-search-box__container button[type='button']",
                ".jobs-search-box__search-icon",
                "[data-control-name='search_icon']"
            ]
            
            # Try each selector until we find the search icon
            search_icon = None
            for selector in magnifier_selectors:
                try:
                    search_icon = await self.page.query_selector(selector)
                    if search_icon:
                        await self._log_info(f"Found search icon with selector: {selector}")
                        break
                except Exception:
                    continue
            
            if search_icon:
                # Click the search icon to expand the search interface
                await search_icon.scroll_into_view_if_needed()
                await self._human_delay(0.3, 0.7)
                await search_icon.click()
                await self._human_delay(1, 1.5)  # Wait for expansion animation
                
                # Now look for the expanded search inputs
                search_input_selectors = [
                    "input.jobs-search-box__text-input",
                    "input[aria-label='Search by title, skill, or company']",
                    "input[placeholder*='Search jobs']",
                    "input[type='text'][name*='keywords']"
                ]
                
                location_input_selectors = [
                    "input.jobs-search-box__location-input",
                    "input[aria-label*='location']",
                    "input[aria-label='City, state, or zip code']",
                    "input[placeholder*='Location']"
                ]
                
                # Try to fill job title if provided
                if job_title:
                    for selector in search_input_selectors:
                        try:
                            await self.page.fill(selector, "")  # Clear first
                            await self.page.fill(selector, job_title)
                            await self._human_delay(0.5, 1)
                            await self._log_info(f"Filled job title in responsive layout: {job_title}")
                            break
                        except Exception:
                            continue
                
                # Try to fill location if provided
                if location:
                    for selector in location_input_selectors:
                        try:
                            await self.page.fill(selector, "")  # Clear first
                            await self.page.fill(selector, location)
                            await self._human_delay(0.5, 1)
                            await self._log_info(f"Filled location in responsive layout: {location}")
                            break
                        except Exception:
                            continue
                
                # Try to submit the search
                submit_selectors = [
                    "button[type='submit']",
                    ".jobs-search-box__submit-button",
                    "button[data-tracking-control-name*='search-submit']"
                ]
                
                for selector in submit_selectors:
                    try:
                        submit_btn = await self.page.query_selector(selector)
                        if submit_btn:
                            await submit_btn.click()
                            await self._human_delay(1, 2)
                            return True
                    except Exception:
                        continue
                
                # If no submit button found, try pressing Enter
                await self.page.keyboard.press("Enter")
                await self._human_delay(1, 2)
                return True
                
            return False
            
        except Exception as e:
            await self._log_error("Error handling responsive search", error=e)
            return False

    async def _is_narrow_layout(self) -> bool:
        """Check if we're in a narrow/collapsed layout."""
        try:
            # Check if any of the collapsed layout indicators are present
            narrow_indicators = [
                "button[aria-label='Search']",  # Magnifier icon
                ".jobs-search-box--collapsed",
                ".jobs-search-box__container--responsive"
            ]
            
            for selector in narrow_indicators:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    return True
            
            # Also check viewport width as a fallback
            viewport_width = await self.page.evaluate('window.innerWidth')
            return viewport_width < 768  # Common breakpoint for mobile layouts
            
        except Exception as e:
            await self._log_error("Error checking layout width", error=e)
            return False

    async def _handle_single_feed_layout(self) -> List[Dict]:
        """Handle the single feed layout when no search is active."""
        try:
            job_cards = []
            feed_selectors = [
                "div[data-job-id]",
                ".jobs-job-board-list__item",
                ".jobs-collection-card",
                "ul.jobs-list > li"
            ]
            
            # Try each selector pattern
            for selector in feed_selectors:
                try:
                    cards = await self.page.query_selector_all(selector)
                    if cards:
                        await self._log_info(f"Found {len(cards)} jobs in single feed layout")
                        job_cards = cards
                        break
                except Exception:
                    continue
            
            if not job_cards:
                return []
            
            jobs_data = []
            for card in job_cards:
                try:
                    # Extract basic info from card
                    title = await self._safe_get_text("h3", card)
                    company = await self._safe_get_text(".job-card-container__company-name", card)
                    location = await self._safe_get_text(".job-card-container__metadata-item", card)
                    
                    jobs_data.append({
                        "title": title,
                        "company": company,
                        "location": location,
                        "card_element": card
                    })
                except Exception as e:
                    await self._log_error("Error extracting card data", error=e)
                    continue
                
            return jobs_data
            
        except Exception as e:
            await self._log_error("Error handling single feed layout", error=e)
            return []

    async def _verify_login_state(self) -> bool:
        """Verify that we're properly logged into LinkedIn."""
        try:
            # Check for user navigation menu (indicates logged in state)
            nav_selectors = [
                "button[data-control-name='nav.settings']",
                "#global-nav-profile",
                "div.nav-settings__member-profile-button"
            ]
            
            for selector in nav_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        return True
                except Exception:
                    continue
            
            # Check for sign-in button (indicates logged out state)
            sign_in_indicators = [
                "a.nav__button-secondary",
                "a[data-tracking-control-name='guest_homepage-basic_sign-in-button']",
                "a[href*='signup']"
            ]
            
            for selector in sign_in_indicators:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await self._log_info("Found sign-in button - user is logged out")
                        return False
                except Exception:
                    continue
                
            # If we can't definitively determine state, check profile URL
            try:
                await self.page.goto("https://www.linkedin.com/feed/", timeout=5000)
                current_url = self.page.url.lower()
                return "feed" in current_url or "mynetwork" in current_url
            except Exception as e:
                await self._log_error("Error checking feed URL", error=e)
                
            return False
            
        except Exception as e:
            await self._log_error("Error verifying login state", error=e)
            return False
