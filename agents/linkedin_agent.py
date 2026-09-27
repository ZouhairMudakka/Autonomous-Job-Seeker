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
import math
import csv
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from pathlib import Path
from typing import Dict, Optional, Any, List
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from constants import TimingConstants, Selectors, Messages
from time import perf_counter
from storage.logs_manager import LogsManager
from utils.dom.dom_service import DomService
from locators.linkedin_locators import LinkedInLocators

# We'll also import your GeneralAgent or FormFillerAgent if needed:
# from agents.general_agent import GeneralAgent
# from agents.form_filler_agent import FormFillerAgent

class LinkedInAgent:
    def __init__(
        self,
        page: Page,
        controller,
        default_timeout: Optional[float] = None,
        min_delay: Optional[float] = None,
        max_delay: Optional[float] = None,
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
        self.settings = controller.settings
        self.dom_service = DomService(page, settings=self.settings, logs_manager=self.logs_manager)
        linkedin_settings = self.settings.get('linkedin', {})
        self.default_timeout = float(default_timeout if default_timeout is not None else linkedin_settings.get('default_timeout', TimingConstants.DEFAULT_TIMEOUT))
        self.min_delay = float(min_delay if min_delay is not None else linkedin_settings.get('min_delay', TimingConstants.HUMAN_DELAY_MIN / 1000))
        self.max_delay = float(max_delay if max_delay is not None else linkedin_settings.get('max_delay', TimingConstants.HUMAN_DELAY_MAX / 1000))
        if (not all(math.isfinite(value) for value in (self.default_timeout, self.min_delay, self.max_delay))
                or self.default_timeout <= 0 or not 0 <= self.min_delay <= self.max_delay):
            raise ValueError('Timeout must be positive and delays must satisfy 0 <= min_delay <= max_delay')
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
                await asyncio.sleep(TimingConstants.POLL_INTERVAL / 1000)
                # Check for cancellation during pause
                if asyncio.current_task().cancelled():
                    raise asyncio.CancelledError()
            except asyncio.CancelledError:
                await self._log_state_change("paused", "cancelled", "Operation cancelled while paused")
                raise

    async def _verify_url_is_jobs(self) -> bool:
        """Verify current URL is a LinkedIn jobs page."""
        try:
            parsed = urlparse(self.page.url)
            if parsed.scheme != 'https' or not (parsed.hostname == 'linkedin.com' or (parsed.hostname or '').endswith('.linkedin.com')):
                return False
            current_url = parsed.path.lower()

            # Valid jobs URLs patterns
            jobs_patterns = [
                "/jobs",
                "/my-items/saved-jobs",
                "/job/",
                "/jobs/collections/",
                "/jobs/search",
                "/jobs/view"
            ]

            return any(current_url == pattern or current_url.startswith(pattern.rstrip('/') + '/') for pattern in jobs_patterns)
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

    def _job_search_limit(self, max_jobs: Optional[int] = None) -> int:
        """Apply the configured ceiling to every listing layout and caller."""
        limit = self.settings.get('linkedin', {}).get('job_search_limit', 50)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError('linkedin.job_search_limit must be a positive integer')
        if max_jobs is None:
            return limit
        if isinstance(max_jobs, bool) or not isinstance(max_jobs, int) or max_jobs < 0:
            raise ValueError('max_jobs must be a nonnegative integer')
        return min(max_jobs, limit)

    async def process_job_listings(self, max_jobs: Optional[int] = None):
        """Process each discovered listing once, stopping when the feed stops growing."""
        max_jobs = self._job_search_limit(max_jobs)
        processed = 0
        seen = set()
        selectors = (
            '.jobs-search-results-list [data-job-id]',
            Selectors.LINKEDIN_JOB_CARD,
            'div[data-job-id]',
            '.jobs-job-board-list__item',
            '.jobs-collection-card',
            'ul.jobs-list > li',
        )
        while processed < max_jobs:
            await self._check_if_paused()
            cards = []
            for selector in selectors:
                cards = await self.page.query_selector_all(selector)
                if cards:
                    break
            new_cards = 0
            for card in cards:
                if processed >= max_jobs:
                    break
                await self._check_if_paused()
                key = await card.get_attribute('data-job-id')
                if not key:
                    link = await card.query_selector('a[href*="/jobs/view/"]')
                    key = await link.get_attribute('href') if link else None
                if not key:
                    key = (await card.text_content() or '').strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                new_cards += 1
                processed += 1
                data = {'job_title': '', 'company': '', 'location': '', 'is_easy_apply': False,
                        'recruiter_name': '', 'recruiter_link': ''}
                try:
                    await card.scroll_into_view_if_needed()
                    await card.click()
                    await self.page.wait_for_selector(
                        '.jobs-search__right-rail, .jobs-details, [data-job-detail-container]',
                        timeout=self.default_timeout,
                    )
                    data = await self._extract_job_details()
                    data['application_status'] = await self._apply_to_job(data)
                except Exception as error:
                    await self._log_error('Error processing job listing', error=error)
                    data['application_status'] = 'failed'
                await self._save_job_record(data)
            if new_cards == 0:
                break
            if processed < max_jobs:
                pane = await self.page.query_selector('.jobs-search-results-list')
                if pane:
                    await pane.evaluate('(element) => element.scrollTo(0, element.scrollHeight)')
                else:
                    await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await self._human_delay(0.3, 0.5)
        await self._log_info(f'Finished processing {processed} job listings')
        return processed

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
        easy_apply_sel = 'button.jobs-apply-button:has-text("Easy Apply")'
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
        # Bulk search is read-only unless automatic application was explicitly
        # enabled. Explicit single-application entry points remain available.
        if self.settings.get('linkedin', {}).get('auto_apply_enabled', False) is not True:
            await self._log_info('Automatic application is disabled; recording this job as skipped')
            return 'skipped'

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
                easy_apply_btn_sel = 'button.jobs-apply-button:has-text("Easy Apply")'
                await self.page.click(easy_apply_btn_sel)
                await asyncio.sleep(TimingConstants.EASY_APPLY_MODAL_DELAY / 1000)

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
        """Use the same bounded and confirmed form workflow as the form agent."""
        if not hasattr(self, 'form_filler_agent'):
            from agents.form_filler_agent import FormFillerAgent
            self.form_filler_agent = FormFillerAgent(self.dom_service, self.logs_manager, self.settings)
        form_data = dict(self.settings.get('form_data', {}))
        cv_path = getattr(self, 'cv_path', None) or self.settings.get('cv_path')
        if cv_path:
            form_data.setdefault('cv_path', str(cv_path))
        return await self.form_filler_agent.fill_easy_apply(form_data)

    async def _handle_external_apply(self, apply_button) -> str:
        """Observe either a popup or same-tab navigation and restore the jobs page."""
        current_url = self.page.url
        popups = []
        self.page.on('popup', popups.append)
        try:
            await apply_button.click()
            deadline = asyncio.get_running_loop().time() + self.default_timeout / 1000
            while not popups and self.page.url == current_url:
                if asyncio.get_running_loop().time() >= deadline:
                    return 'failed'
                await asyncio.sleep(0.05)
            return 'redirected'
        except Exception as error:
            await self._log_error('External apply error', error=error)
            return 'failed'
        finally:
            self.page.remove_listener('popup', popups.append)
            for popup in popups:
                try:
                    await popup.close()
                except Exception as error:
                    await self._log_error('Could not close external application tab', error=error)
            if self.page.url != current_url:
                try:
                    await self.page.go_back(timeout=self.default_timeout)
                except Exception as error:
                    await self._log_error('Could not restore job results page', error=error)

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
                writer.writerow({key: job_data.get(key, '') for key in fieldnames})
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
        await asyncio.sleep(TimingConstants.PAGE_TRANSITION_DELAY / 1000)

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
    async def _safe_get_text(self, selector: str, root=None) -> str:
        """
        Attempt to get text content from a selector; return empty string if not found.
        """
        try:
            el = await (root if root is not None else self.page).query_selector(selector)
            if el:
                txt = await el.text_content()
                return txt.strip() if txt else ""
        except Exception:
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
                await self._human_delay()  # Wait for upload

            # Skip cover letter if requested
            cover_letter = self.page.locator(Selectors.COVER_LETTER_INPUT)
            if await cover_letter.count() > 0:
                await self._log_info("Skipping cover letter (MVP)")
                # Future: Implement cover letter handling
                pass

            # Submit form if possible
            submit_button = self.page.locator(Selectors.SUBMIT_APPLICATION)
            if await submit_button.count() > 0:
                success_selector = ', '.join(LinkedInLocators.FORM_SUCCESS)
                existing = await self.page.query_selector(success_selector)
                if existing is not None and await existing.is_visible():
                    return False
                await submit_button.click()
                confirmation = await self.page.wait_for_selector(success_selector, timeout=self.default_timeout)
                return confirmation is not None

            return False

        except Exception as e:
            await self._log_error("Error in application form", error=e)
            return False

    async def search_jobs_and_apply(self, job_title: str, location: str):
        """Main method to orchestrate searching & applying on LinkedIn."""
        if not isinstance(job_title, str) or not job_title.strip() or not isinstance(location, str) or not location.strip():
            raise ValueError('A nonempty job title and location are required')
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
                if job_filled and location_filled:
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
                            except Exception:
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
                            '.jobs-search-results-list, div[data-job-id], .jobs-job-board-list__item, .jobs-collection-card, ul.jobs-list > li',
                            timeout=self.default_timeout
                        )

                        await self._log_info("Search results loaded successfully")
                        await self.process_job_listings(max_jobs=self._job_search_limit())

                    except Exception as e:
                        await self._log_error("Error triggering search", error=e, context=context)
                        raise

                else:
                    missing = []
                    if not job_filled:
                        missing.append('job title')
                    if not location_filled:
                        missing.append('location')
                    raise RuntimeError(f"Could not set requested search criteria: {', '.join(missing)}")

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
                await asyncio.sleep(delay / 1000)

    async def cleanup(self):
        """Cleanup resources when agent is done."""
        try:
            # Cancel any pending operations
            if hasattr(self, 'current_task'):
                self.current_task.cancel()

            # Close any open dialogs
            try:
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(TimingConstants.MODAL_TRANSITION_DELAY / 1000)
            except Exception:
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
                return await self._verify_url_is_jobs()

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
                await asyncio.sleep(TimingConstants.MODAL_TRANSITION_DELAY / 1000)
                return True
        except PlaywrightTimeoutError:
            pass
        return False

    async def _refresh_session(self) -> bool:
        await self.page.reload(timeout=self.default_timeout)
        return await self._verify_login_state()

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

    @asynccontextmanager
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

    async def _safe_interaction(self, element, action_type: str, value: str = ""):
        """Safely interact with elements using proper async context."""
        try:
            async with self._monitor_operation(f"{action_type}_interaction"):
                # Verify element is still valid
                await element.wait_for_element_state('stable')

                if action_type == 'click':
                    await element.click()
                elif action_type == 'fill':
                    await element.fill(value)
                else:
                    raise ValueError(f"Unsupported interaction: {action_type}")
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

    @asynccontextmanager
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
            if not await self._verify_url_is_jobs():
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
                except Exception:
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
                await asyncio.sleep(delay / 1000)

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
                except Exception:
                    continue

            return False
        except Exception as e:
            await self._log_error("Error ensuring jobs search ready", error=e)
            return False

    async def _handle_responsive_search(self, job_title: str = None, location: str = None) -> bool:
        """Handle search when the layout is collapsed/narrow."""
        if not isinstance(job_title, str) or not job_title.strip() or not isinstance(location, str) or not location.strip():
            return False
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

                # Both criteria must be populated before a responsive search
                # may submit; a partial search must never lead to applications.
                job_filled = False
                location_filled = False
                # Try to fill job title if provided
                if job_title:
                    for selector in search_input_selectors:
                        try:
                            await self.page.fill(selector, "")  # Clear first
                            await self.page.fill(selector, job_title)
                            await self._human_delay(0.5, 1)
                            await self._log_info(f"Filled job title in responsive layout: {job_title}")
                            job_filled = True
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
                            location_filled = True
                            break
                        except Exception:
                            continue

                if not job_filled or not location_filled:
                    await self._log_warning('Responsive search could not set both job title and location')
                    return False

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

    async def _handle_single_feed_layout(self, max_jobs: Optional[int] = None) -> List[Dict]:
        """Handle the single feed layout when no search is active."""
        max_jobs = self._job_search_limit(max_jobs)
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
            for card in job_cards[:max_jobs]:
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
                "div.nav-settings__member-profile-button",
                *LinkedInLocators.LOGGED_IN_INDICATOR,
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

            # Unknown state must not navigate away from an in-progress application.
            return False

        except Exception as e:
            await self._log_error("Error verifying login state", error=e)
            return False
