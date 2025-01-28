"""
Main Controller Module (Async, MVP Version)

Coordinates the automation flow across multiple agents using a lightweight AI Master-Plan.
Uses a TaskManager for concurrency or scheduling.

Architecture Overview:
--------------------
This module maintains separation of concerns across multiple agents while providing
centralized orchestration and error handling.

**New Master-Plan Integration (MVP)**
-------------------------------------
We add a minimal "AI Master-Plan" logic that outlines the major steps (e.g. "Login → 
Search → Apply"), while still relying on site-specific fallback (like LinkedInLocators).

1) We generate a short plan (list of steps) for each flow.
2) We pass it to the `ai_navigator` or handle it directly in the controller.
3) Each step can use confidence-based navigation or direct fallback.
4) On error or low confidence, the Master-Plan either retries or proceeds with site-specific logic.

TODO (AI Integration):
--------------------
- Initialize AI Navigator and Learning Pipeline
- Add confidence-based decision making
- Setup proper AI fallback mechanisms
- Add AI-specific session management
- Integrate with unified logging system
- (Future) Detailed GPT-based planning for each site

MVP Implementation:
-----------------
- The plan is small (2-4 steps).
- If a step fails (captcha or something else), we either retry or fallback to manual CredentialsAgent.
- Primary focus on robust error handling and fallback mechanisms
- Maintains compatibility with existing agent-based architecture

Example:
    plan = ["check_captcha", "search_jobs", "apply_jobs"]
    # Each step calls an agent or ai_navigator to do the actual actions.

Usage:
------
Controller is typically instantiated once per session:
    controller = Controller(settings, page)
    await controller.start_session()
    await controller.run_master_plan(["check_login", "search_jobs", "apply_form"])
    ...

(You can also call run_linkedin_flow, etc. as before.)

Dependencies:
------------
- TaskManager: For concurrency and scheduling
- Multiple Agents: LinkedIn, Credentials, Tracker, etc.
- AI Navigator: For confidence-based navigation
- DOM Service: For direct page interactions
"""

import asyncio
from agents.linkedin_agent import LinkedInAgent
from agents.credentials_agent import CredentialsAgent
from agents.tracker_agent import TrackerAgent
from constants import TimingConstants, Messages
from orchestrator.task_manager import TaskManager
from pathlib import Path
from utils.telemetry import TelemetryManager
from agents.ai_navigator import AINavigator
from datetime import datetime, timedelta
from agents.cv_parser_agent import CVParserAgent

class Controller:
    def __init__(self, settings, page):
        """Initialize the controller with settings and browser page."""
        self.settings = settings
        self.page = page
        self.max_retries = settings.get('max_retries', 3)  # Default to 3 if not specified
        
        # Initialize all agents with settings
        self.tracker_agent = TrackerAgent(settings)
        self.credentials_agent = CredentialsAgent(settings)
        
        # Initialize LinkedIn agent with page and controller
        self.linkedin_agent = LinkedInAgent(
            page=self.page,
            controller=self,
            default_timeout=settings.get('default_timeout', TimingConstants.DEFAULT_TIMEOUT),
            min_delay=settings.get('min_delay', TimingConstants.HUMAN_DELAY_MIN),
            max_delay=settings.get('max_delay', TimingConstants.HUMAN_DELAY_MAX)
        )

        # Initialize AI Navigator
        self.ai_navigator = AINavigator(
            page=self.page,
            settings=self.settings,
            min_confidence=settings.get('min_confidence', 0.8),
            max_retries=self.max_retries
        )

        # Task management and timing configurations
        self.task_manager = TaskManager(self)
        self.retry_delay = TimingConstants.BASE_RETRY_DELAY
        self.action_delay = TimingConstants.ACTION_DELAY
        self.poll_interval = TimingConstants.POLL_INTERVAL

        # State management
        self.pause_state = {}

        self.telemetry = TelemetryManager(settings)

        # Replace doc_processor with cv_parser
        self.cv_parser = CVParserAgent(settings)

    async def start_session(self):
        """
        Prepare or initialize the automation session.
        Logs the session start.
        (User is already logged into LinkedIn for MVP).
        """
        try:
            await asyncio.sleep(TimingConstants.ACTION_DELAY)
            await self.tracker_agent.log_activity(
                activity_type='session',
                details='Session started',
                status='success',
                agent_name='Controller'
            )
        except Exception as e:
            await asyncio.sleep(TimingConstants.ERROR_DELAY)
            await self.tracker_agent.log_activity(
                activity_type='session',
                details=f'Session failed to start: {str(e)}',
                status='error',
                agent_name='Controller'
            )
            raise

    async def run_linkedin_flow(self, job_title: str, location: str):
        """Example method to orchestrate searching & applying on LinkedIn."""
        attempt = 0
        while attempt < self.max_retries:
            try:
                await asyncio.sleep(TimingConstants.ACTION_DELAY)
                
                # Use AI Master-Plan for the flow
                plan_steps = ["check_login", "open_job_page", "fill_search", "apply"]
                success = await self.run_master_plan(plan_steps)
                
                if success:
                    await self.tracker_agent.log_activity(
                        activity_type='job_search_apply',
                        details=Messages.SUCCESS_MESSAGE,
                        status='success',
                        agent_name='Controller'
                    )
                    break
                else:
                    # Fallback to traditional flow if master plan fails
                    task = await self.task_manager.create_task(
                        self.linkedin_agent.search_jobs_and_apply(job_title, location)
                    )
                    result = await self.task_manager.run_task(task)
                    break

            except Exception as e:
                attempt += 1
                await asyncio.sleep(TimingConstants.ERROR_DELAY)
                await self.tracker_agent.log_activity(
                    activity_type='job_search_apply',
                    details=Messages.RETRY_MESSAGE.format(
                        attempt, self.max_retries, str(e)
                    ),
                    status='error',
                    agent_name='Controller'
                )
                
                if attempt >= self.max_retries:
                    await self.tracker_agent.log_activity(
                        activity_type='job_search_apply',
                        details='Max retries reached. Stopping flow.',
                        status='failed',
                        agent_name='Controller'
                    )
                    raise e
                else:
                    # Exponential backoff delay before next attempt
                    retry_delay = TimingConstants.BASE_RETRY_DELAY * (TimingConstants.RETRY_BACKOFF_FACTOR ** attempt)
                    await asyncio.sleep(retry_delay)

    async def end_session(self):
        """
        Clean up and end the session.
        Note: Browser cleanup is now handled at a higher level.
        """
        try:
            await asyncio.sleep(TimingConstants.ACTION_DELAY)
            await self.tracker_agent.log_activity(
                activity_type='session',
                details='Session ended by user or completion of tasks',
                status='success',
                agent_name='Controller'
            )
        except Exception as e:
            await asyncio.sleep(TimingConstants.ERROR_DELAY)
            await self.tracker_agent.log_activity(
                activity_type='session',
                details=f'Error ending session: {str(e)}',
                status='error',
                agent_name='Controller'
            )
            raise

    async def pause_session(self):
        """
        Pause the current tasks or flows. 
        For MVP, we simply log it. 
        """
        await asyncio.sleep(TimingConstants.ACTION_DELAY)
        await self.tracker_agent.log_activity(
            activity_type='session',
            details=Messages.PAUSE_MESSAGE,
            status='info',
            agent_name='Controller'
        )

    async def resume_session(self):
        """
        Resume tasks from a paused state. 
        For MVP, we log it, but real logic is needed to continue from partial steps.
        """
        await asyncio.sleep(TimingConstants.ACTION_DELAY)
        await self.tracker_agent.log_activity(
            activity_type='session',
            details=Messages.RESUME_MESSAGE,
            status='info',
            agent_name='Controller'
        )

    async def handle_job_application(self, job_url: str, cv_path: str | Path):
        """
        Handle complete job application process including CV processing and form submission.
        
        Args:
            job_url: URL of the job posting
            cv_path: Path to the CV file
            
        Returns:
            bool: True if application was successful, False otherwise
        """
        try:
            # Use cv_parser instead of doc_processor
            cv_path, cv_data = await self.cv_parser.prepare_cv(cv_path)
            
            # Log CV processing
            await self.tracker_agent.log_activity(
                activity_type='document',
                details=f'Processed CV: {cv_path.name}',
                status='info',
                agent_name='Controller'
            )
            
            # Create a plan for application submission
            application_plan = [
                "check_login",
                "open_job_page",
                "handle_user_profile",
                "fill_application_form",
                "validate_form",
                "submit_application",
                "track_application"
            ]
            
            # Set application context in settings
            self.settings.update({
                'job_url': job_url,
                'cv_path': cv_path,
                'cv_data': cv_data
            })
            
            # Execute the application plan
            success = await self.run_master_plan(application_plan)
            
            # Log the final result
            await self.tracker_agent.log_activity(
                activity_type='application',
                details=f'Application {"submitted" if success else "failed"}: {job_url}',
                status='success' if success else 'error',
                agent_name='Controller'
            )
            
            return success
            
        except Exception as e:
            await self.tracker_agent.log_activity(
                activity_type='application',
                details=f'Error in application: {str(e)}',
                status='error',
                agent_name='Controller'
            )
            # Log detailed error for debugging
            print(f"[Controller] Application error: {str(e)}")
            return False

    async def run_master_plan(self, plan_steps: list[str]) -> bool:
        """
        Execute the AI Master-Plan with proper error handling and retries.
        
        Args:
            plan_steps: List of steps to execute
            
        Returns:
            bool: True if plan executed successfully
        """
        try:
            # 1. Validate and modify plan based on conditions
            modified_plan = await self._modify_plan_for_conditions(plan_steps)
            
            # 2. Log plan execution start
            await self.tracker_agent.log_activity(
                activity_type='master_plan',
                details=f'Starting plan execution: {modified_plan}',
                status='info',
                agent_name='Controller'
            )
            
            # 3. Execute plan with AI Navigator
            attempt = 0
            last_error = None
            
            while attempt < self.max_retries:
                try:
                    success, confidence = await self.ai_navigator.execute_master_plan(modified_plan)
                    
                    if success:
                        await self.tracker_agent.log_activity(
                            activity_type='master_plan',
                            details=f'Plan completed successfully with confidence {confidence}',
                            status='success',
                            agent_name='Controller'
                        )
                        return True
                        
                    # If not successful but no exception, try again with delay
                    attempt += 1
                    if attempt < self.max_retries:
                        retry_delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        await asyncio.sleep(retry_delay / 1000)  # Convert ms to seconds
                        
                except Exception as e:
                    last_error = str(e)
                    attempt += 1
                    
                    await self.tracker_agent.log_activity(
                        activity_type='master_plan',
                        details=f'Plan attempt {attempt} failed: {last_error}',
                        status='error',
                        agent_name='Controller'
                    )
                    
                    if attempt < self.max_retries:
                        retry_delay = self.retry_delay * (2 ** attempt)
                        await asyncio.sleep(retry_delay / 1000)
                        
                        # Check if we need to modify plan after error
                        modified_plan = await self._handle_rate_limiting(modified_plan)
            
            # If we're here, we've exhausted retries
            await self.tracker_agent.log_activity(
                activity_type='master_plan',
                details=f'Plan failed after {attempt} attempts. Last error: {last_error}',
                status='failed',
                agent_name='Controller'
            )
            return False
            
        except Exception as e:
            await self.tracker_agent.log_activity(
                activity_type='master_plan',
                details=f'Critical error in plan execution: {str(e)}',
                status='error',
                agent_name='Controller'
            )
            return False

    async def _handle_rate_limiting(self, plan_steps: list[str]) -> list[str]:
        """
        Add delays or modify plan when rate limiting is detected.
        
        Args:
            plan_steps: Original list of steps
            
        Returns:
            list[str]: Modified plan with rate limiting handling
        """
        try:
            modified_plan = []
            base_delay = self.settings.get('rate_limit_delay', TimingConstants.BASE_RETRY_DELAY)
            
            for step in plan_steps:
                # Add the original step
                modified_plan.append(step)
                
                # Add delay and verification after critical operations
                if step in self.ai_navigator.critical_steps:
                    # Add rate limit delay step
                    modified_plan.append("rate_limit_delay")
                    
                    # Add verification step
                    modified_plan.append("verify_action")
                    
                    # Log the modification
                    await self.tracker_agent.log_activity(
                        activity_type='rate_limit',
                        details=f'Added rate limit handling after step: {step}',
                        status='info',
                        agent_name='Controller'
                    )
                    
                    # Increase delay for subsequent critical operations
                    base_delay *= TimingConstants.RETRY_BACKOFF_FACTOR
            
            # Update settings with new delay
            self.settings['rate_limit_delay'] = base_delay
            
            return modified_plan
            
        except Exception as e:
            print(f"[Controller] Error handling rate limiting: {str(e)}")
            # On error, return original plan
            return plan_steps

    async def _is_high_activity_period(self) -> bool:
        """
        Check if we're in a high-activity period based on:
        1. Recent application count
        2. Time of day (peak hours)
        3. Site response times
        4. Recent rate limiting or CAPTCHA encounters
        
        Returns:
            bool: True if current period is considered high activity
        """
        try:
            # 1. Check recent activity count
            recent_activities = await self.tracker_agent.get_recent_activities(
                timeframe_minutes=30,
                activity_type='application'
            )
            
            activity_threshold = self.settings.get('activity_threshold', 10)
            if len(recent_activities) > activity_threshold:
                print("[Controller] High activity detected: Recent applications exceed threshold")
                return True
            
            # 2. Check if we're in peak hours (e.g., 9 AM to 5 PM local time)
            current_hour = datetime.now().hour
            peak_hours = range(9, 17)  # 9 AM to 5 PM
            if current_hour in peak_hours:
                print("[Controller] High activity period: Peak hours")
                return True
            
            # 3. Check recent response times (if available)
            recent_response_times = await self.telemetry.get_recent_metrics(
                metric_type='response_time',
                timeframe_minutes=15
            )
            
            if recent_response_times:
                avg_response_time = sum(recent_response_times) / len(recent_response_times)
                if avg_response_time > self.settings.get('slow_response_threshold', 2000):
                    print("[Controller] High activity detected: Slow response times")
                    return True
            
            # 4. Check recent CAPTCHA or rate limit encounters
            recent_issues = await self.tracker_agent.get_recent_activities(
                timeframe_minutes=30,
                activity_type=['captcha', 'rate_limit']
            )
            
            if len(recent_issues) > self.settings.get('issue_threshold', 2):
                print("[Controller] High activity detected: Recent CAPTCHA/rate limiting")
                return True
            
            return False
            
        except Exception as e:
            print(f"[Controller] Error checking activity period: {str(e)}")
            # On error, assume it's not a high activity period
            return False

    async def _save_session_state(self) -> bool:
        """
        Save the current session state for possible restoration later.

        The session state includes:
          - A 'session_version' for compatibility checks.
          - Timestamps and plan progress (current_plan, current_step, completed_steps).
          - Job search context (title, location, job_url, cv_path).
          - Application progress (form_data, uploaded_files, validation_status).
          - Basic metrics (start_time, attempts, success_rate).

        Steps:
          1. Check if current state needs recovery
          2. Build and validate state object
          3. Save state with version info
          4. Verify saved state

        Returns:
            bool: True if the session state was saved successfully, False otherwise.
        """
        try:
            # Check if we need recovery before saving
            recovery_success, _ = await self.ai_navigator.execute_master_plan(["recovery_check"])
            if not recovery_success:
                await self.tracker_agent.log_activity(
                    activity_type='session_state',
                    details='Cannot save state: recovery needed',
                    status='error',
                    agent_name='Controller'
                )
                print("[Controller] Cannot save state: recovery needed")
                return False

            # Build state object
            self.pause_state = {
                # Add a version key so we can detect mismatches if we change the schema
                'session_version': "1.0",
                
                'timestamp': datetime.now().isoformat(),
                
                # Plan execution state
                'current_plan': getattr(self, 'current_plan', []),
                'current_step': getattr(self, 'current_step', 0),
                'completed_steps': getattr(self, 'completed_steps', []),
                
                # Job search context
                'job_data': {
                    'title': self.settings.get('job_title'),
                    'location': self.settings.get('location'),
                    'url': self.settings.get('job_url'),
                    'cv_path': str(self.settings.get('cv_path', '')),
                },
                
                # Application progress
                'application_state': {
                    'form_data': self.settings.get('form_data', {}),
                    'uploaded_files': self.settings.get('uploaded_files', []),
                    'validation_status': self.settings.get('validation_status', {})
                },
                
                # Metrics and timing
                'metrics': {
                    'start_time': self.settings.get('start_time'),
                    'attempts': self.settings.get('attempts', 0),
                    'success_rate': self.settings.get('success_rate', 0.0)
                }
            }

            # Verify the state we're about to save
            is_valid, error_msg = await self._validate_session_state(self.pause_state)
            if not is_valid:
                await self.tracker_agent.log_activity(
                    activity_type='session_state',
                    details=f'Cannot save invalid state: {error_msg}',
                    status='error',
                    agent_name='Controller'
                )
                print(f"[Controller] Cannot save invalid state: {error_msg}")
                return False
            
            # Verify save with AI Navigator
            verify_success, confidence = await self.ai_navigator.execute_master_plan(["verify_action"])
            if not verify_success:
                await self.tracker_agent.log_activity(
                    activity_type='session_state',
                    details='State save verification failed',
                    status='error',
                    agent_name='Controller'
                )
                print("[Controller] State save verification failed")
                return False
            
            # Log successful save
            await self.tracker_agent.log_activity(
                activity_type='session_state',
                details=f'Session state saved and verified successfully (confidence: {confidence:.2f})',
                status='success',
                agent_name='Controller'
            )
            
            print("[Controller] Session state saved and verified successfully.")
            return True
            
        except Exception as e:
            await self.tracker_agent.log_activity(
                activity_type='session_state',
                details=f'Failed to save session state: {str(e)}',
                status='error',
                agent_name='Controller'
            )
            print(f"[Controller] Error saving session state: {str(e)}")
            return False

    async def _validate_session_state(self, state: dict) -> tuple[bool, str]:
        """
        Validate session state before restoration.

        This method checks:
          1. Required fields (e.g., session_version, timestamp, current_plan, job_data).
          2. session_version compatibility.
          3. Timestamp freshness (older than 1 hour is considered stale).
          4. Minimal job data fields (title, location).
          5. Existence of CV path if specified.
          6. Plan/step consistency.
          7. Data-type checks for lists/dicts in sub-fields.
        
        Args:
            state (dict): The dictionary containing the saved session state.

        Returns:
            (bool, str): (is_valid, error_message) 
                         is_valid = True if state is usable, 
                         error_message = '' or reason why invalid.
        """
        try:
            # 1. Check required top-level fields
            required_fields = ['session_version', 'timestamp', 'current_plan', 'job_data']
            for field in required_fields:
                if field not in state:
                    return False, f"Missing required field '{field}' in session state"

            # 2. Check session_version
            # If we bump to '2.0' in future, we can do a basic compare
            if state['session_version'] != "1.0":
                return False, f"Incompatible session version: {state['session_version']}"

            # 3. Validate timestamp not older than 1 hour
            saved_time = datetime.fromisoformat(state['timestamp'])
            time_diff = datetime.now() - saved_time
            if time_diff > timedelta(hours=1):
                return False, "State is too old (> 1 hour)"

            # 4. Minimal job data check
            job_data = state.get('job_data', {})
            if not job_data.get('title') or not job_data.get('location'):
                return False, "Missing job search parameters ('title'/'location')"

            # 5. Validate file paths
            cv_path = job_data.get('cv_path')
            if cv_path:
                path_obj = Path(cv_path)
                # It's optional to require existence, but let's keep it
                if not path_obj.exists():
                    return False, f"CV file no longer exists at saved path: {cv_path}"

            # 6. Plan/step consistency
            current_plan = state['current_plan']
            current_step = state.get('current_step', 0)
            if not isinstance(current_plan, list):
                return False, "current_plan must be a list"
            if current_step > len(current_plan):
                return False, "Invalid step index for saved plan (current_step > plan length)"

            # 7. Check data types for completed_steps, metrics, and application_state
            if not isinstance(state.get('completed_steps', []), list):
                return False, "Data corruption in 'completed_steps' (not a list)"

            if not isinstance(state.get('metrics', {}), dict):
                return False, "Data corruption in 'metrics' (not a dict)"

            app_state = state.get('application_state', {})
            if not isinstance(app_state, dict):
                return False, "Data corruption in 'application_state' (not a dict)"

            # Inside app_state, check subfields
            if not isinstance(app_state.get('form_data', {}), dict):
                return False, "Invalid 'form_data' format"
            if not isinstance(app_state.get('uploaded_files', []), list):
                return False, "Invalid 'uploaded_files' format"
            if not isinstance(app_state.get('validation_status', {}), dict):
                return False, "Invalid 'validation_status' format"

            return True, "State validation successful."
        
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    async def _restore_session_state(self) -> bool:
        """
        Restore session state from self.pause_state (if any), 
        after validating the data.

        Steps:
         1. Check if self.pause_state is non-empty.
         2. Validate the stored state with _validate_session_state(...).
         3. If valid, restore:
            - Plan execution state (current_plan, current_step, completed_steps).
            - Job data (title, location, job_url, cv_path).
            - Application progress (form_data, etc.)
            - Metrics (start_time, attempts, success_rate).
         4. Verify restoration with AI Navigator.
         5. Log success/failure.

        Returns:
            bool: True if restoration succeeded, False otherwise.
        """
        try:
            if not self.pause_state:
                print("[Controller] No saved state to restore.")
                return False

            # Validate state
            is_valid, error_msg = await self._validate_session_state(self.pause_state)
            if not is_valid:
                await self.tracker_agent.log_activity(
                    activity_type='session_state',
                    details=f'Invalid session state: {error_msg}',
                    status='error',
                    agent_name='Controller'
                )
                print(f"[Controller] State validation failed: {error_msg}")
                return False

            # If valid, restore data
            self.current_plan = self.pause_state.get('current_plan', [])
            self.current_step = self.pause_state.get('current_step', 0)
            self.completed_steps = self.pause_state.get('completed_steps', [])

            job_data = self.pause_state.get('job_data', {})
            self.settings.update({
                'job_title': job_data.get('title'),
                'location': job_data.get('location'),
                'job_url': job_data.get('url'),
                'cv_path': Path(job_data.get('cv_path', '')) if job_data.get('cv_path') else None
            })

            app_state = self.pause_state.get('application_state', {})
            self.settings.update({
                'form_data': app_state.get('form_data', {}),
                'uploaded_files': app_state.get('uploaded_files', []),
                'validation_status': app_state.get('validation_status', {})
            })

            metrics = self.pause_state.get('metrics', {})
            self.settings.update({
                'start_time': metrics.get('start_time'),
                'attempts': metrics.get('attempts', 0),
                'success_rate': metrics.get('success_rate', 0.0)
            })

            # Verify restoration with AI Navigator
            success, confidence = await self.ai_navigator.execute_master_plan([
                "recovery_check",
                "state_restoration",
                "verify_action"
            ])

            if not success:
                await self.tracker_agent.log_activity(
                    activity_type='session_state',
                    details='State restored but verification failed',
                    status='warning',
                    agent_name='Controller'
                )
                print("[Controller] State restored but verification failed.")
                return False

            # Log success
            await self.tracker_agent.log_activity(
                activity_type='session_state',
                details=f'Session state restored and verified successfully (confidence: {confidence:.2f})',
                status='success',
                agent_name='Controller'
            )
            print("[Controller] Session state restored and verified successfully.")
            return True

        except Exception as e:
            await self.tracker_agent.log_activity(
                activity_type='session_state',
                details=f'Failed to restore session state: {str(e)}',
                status='error',
                agent_name='Controller'
            )
            print(f"[Controller] Error restoring session state: {str(e)}")
            return False

    async def _modify_plan_for_conditions(self, plan_steps: list[str]) -> list[str]:
        """
        Modify plan based on various conditions including:
        - Site performance
        - User preferences
        - Previous success rates
        - Time constraints
        - Session history
        
        Args:
            plan_steps: Original list of steps
            
        Returns:
            list[str]: Modified plan with additional steps or checks
        """
        try:
            modified_plan = plan_steps.copy()
            
            # 1. Check site performance and add verification steps
            for i, step in enumerate(plan_steps):
                if step in self.ai_navigator.critical_steps:
                    # Add verification after critical steps
                    modified_plan.insert(i + 1, "verify_action")
                    
                    # Log modification
                    await self.tracker_agent.log_activity(
                        activity_type='plan_modification',
                        details=f'Added verification after {step}',
                        status='info',
                        agent_name='Controller'
                    )
            
            # 2. Check session history for problematic steps
            recent_failures = await self.tracker_agent.get_recent_activities(
                timeframe_minutes=30,
                status='error'
            )
            
            problem_steps = set(
                activity.get('step') 
                for activity in recent_failures 
                if activity.get('step')
            )
            
            # Add extra verification for problematic steps
            for i, step in enumerate(modified_plan):
                if step in problem_steps:
                    modified_plan.insert(i + 1, "double_verify_action")
                    modified_plan.insert(i + 1, "extended_wait")
                    
                    await self.tracker_agent.log_activity(
                        activity_type='plan_modification',
                        details=f'Added extra verification for problematic step: {step}',
                        status='info',
                        agent_name='Controller'
                    )
            
            # 3. Time-based modifications
            if await self._is_high_activity_period():
                modified_plan = await self._handle_rate_limiting(modified_plan)
            
            # 4. User preference based modifications
            if self.settings.get('careful_mode', False):
                # Add extra verification steps throughout
                modified_plan = self._add_careful_mode_steps(modified_plan)
            
            # 5. Add recovery steps if needed
            if self.settings.get('needs_recovery', False):
                modified_plan.insert(0, "recovery_check")
                modified_plan.insert(1, "state_restoration")
            
            return modified_plan
            
        except Exception as e:
            print(f"[Controller] Error modifying plan: {str(e)}")
            # On error, return original plan
            return plan_steps

    def _add_careful_mode_steps(self, plan_steps: list[str]) -> list[str]:
        """Add extra verification steps for careful mode."""
        careful_plan = []
        for step in plan_steps:
            careful_plan.append(step)
            careful_plan.append("verify_action")
            if step in self.ai_navigator.critical_steps:
                careful_plan.append("extended_verification")
        return careful_plan

    async def handle_site_specific_behavior(self, site: str, action: str) -> tuple[bool, dict]:
        """
        Handle different site-specific behaviors and quirks.
        
        Args:
            site: The site identifier (e.g., 'linkedin', 'indeed')
            action: The action being performed (e.g., 'login', 'apply')
            
        Returns:
            tuple[bool, dict]: (success, context_data)
        """
        try:
            # Site-specific behavior mappings
            site_behaviors = {
                'linkedin': {
                    'login': self._handle_linkedin_login,
                    'apply': self._handle_linkedin_apply,
                    'captcha': self._handle_linkedin_captcha,
                    'rate_limit': self._handle_linkedin_rate_limit
                },
                'indeed': {
                    'login': self._handle_indeed_login,
                    'apply': self._handle_indeed_apply,
                    'captcha': self._handle_indeed_captcha
                },
                # Add more sites as needed
            }
            
            # Get the appropriate handler
            site_handlers = site_behaviors.get(site, {})
            handler = site_handlers.get(action)
            
            if not handler:
                await self.tracker_agent.log_activity(
                    activity_type='site_behavior',
                    details=f'No handler for {site}/{action}',
                    status='warning',
                    agent_name='Controller'
                )
                return False, {}
                
            # Execute the handler and get result
            success, context = await handler()
            
            # Log the result
            await self.tracker_agent.log_activity(
                activity_type='site_behavior',
                details=f'{site}/{action} handled with result: {success}',
                status='success' if success else 'error',
                agent_name='Controller'
            )
            
            return success, context
            
        except Exception as e:
            await self.tracker_agent.log_activity(
                activity_type='site_behavior',
                details=f'Error handling {site}/{action}: {str(e)}',
                status='error',
                agent_name='Controller'
            )
            return False, {'error': str(e)}

    # Example site-specific handlers
    async def _handle_linkedin_login(self) -> tuple[bool, dict]:
        """Handle LinkedIn-specific login behavior."""
        try:
            # Check for LinkedIn-specific elements
            await self.ai_navigator.wait_for_element('.linkedin-login-form')
            # Handle potential two-factor auth
            if await self.ai_navigator.check_element_present('.two-factor-auth'):
                await self.credentials_agent.handle_2fa('linkedin')
            return True, {'platform': 'linkedin', 'action': 'login'}
        except Exception as e:
            return False, {'error': str(e)}

    async def _handle_linkedin_rate_limit(self) -> tuple[bool, dict]:
        """Handle LinkedIn-specific rate limiting."""
        try:
            await asyncio.sleep(TimingConstants.RATE_LIMIT_DELAY)
            return True, {'platform': 'linkedin', 'action': 'rate_limit'}
        except Exception as e:
            return False, {'error': str(e)}

    async def monitor_performance(self) -> dict:
        """
        Monitor and analyze performance metrics for the automation session.
        Tracks:
        - Success rates
        - Response times
        - Error frequencies
        - Resource usage
        - Rate limiting incidents
        
        Returns:
            dict: Performance metrics and analysis
        """
        try:
            # Get recent activities
            recent_activities = await self.tracker_agent.get_recent_activities(
                timeframe_minutes=30
            )
            
            # Calculate success rate
            total_actions = len(recent_activities)
            successful_actions = len([
                a for a in recent_activities 
                if a.get('status') == 'success'
            ])
            success_rate = successful_actions / total_actions if total_actions > 0 else 0
            
            # Get response times
            response_times = await self.telemetry.get_recent_metrics(
                metric_type='response_time',
                timeframe_minutes=15
            )
            avg_response_time = (
                sum(response_times) / len(response_times) 
                if response_times else 0
            )
            
            # Analyze error patterns
            error_activities = [
                a for a in recent_activities 
                if a.get('status') == 'error'
            ]
            error_types = {}
            for activity in error_activities:
                error_type = activity.get('details', '').split(':')[0]
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            # Check rate limiting
            rate_limit_incidents = len([
                a for a in recent_activities 
                if 'rate_limit' in a.get('details', '').lower()
            ])
            
            # Compile metrics
            performance_metrics = {
                'timestamp': datetime.now().isoformat(),
                'success_rate': success_rate,
                'total_actions': total_actions,
                'avg_response_time_ms': avg_response_time,
                'error_frequency': len(error_activities) / total_actions if total_actions > 0 else 0,
                'error_patterns': error_types,
                'rate_limit_incidents': rate_limit_incidents,
                'performance_score': self._calculate_performance_score(
                    success_rate, 
                    avg_response_time,
                    rate_limit_incidents
                )
            }
            
            # Log performance data
            await self.tracker_agent.log_activity(
                activity_type='performance',
                details=f'Performance metrics collected: {performance_metrics}',
                status='info',
                agent_name='Controller'
            )
            
            return performance_metrics
            
        except Exception as e:
            await self.tracker_agent.log_activity(
                activity_type='performance',
                details=f'Error monitoring performance: {str(e)}',
                status='error',
                agent_name='Controller'
            )
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def _calculate_performance_score(
        self, 
        success_rate: float, 
        avg_response_time: float,
        rate_limit_incidents: int
    ) -> float:
        """Calculate a normalized performance score (0-1)."""
        # Weight factors
        SUCCESS_WEIGHT = 0.5
        RESPONSE_WEIGHT = 0.3
        RATE_LIMIT_WEIGHT = 0.2
        
        # Normalize response time (assuming 2000ms is poor, 200ms is good)
        response_score = max(0, min(1, (2000 - avg_response_time) / 1800))
        
        # Normalize rate limit incidents (0 is good, 5+ is poor)
        rate_limit_score = max(0, min(1, (5 - rate_limit_incidents) / 5))
        
        # Calculate weighted score
        return (
            success_rate * SUCCESS_WEIGHT +
            response_score * RESPONSE_WEIGHT +
            rate_limit_score * RATE_LIMIT_WEIGHT
        )
