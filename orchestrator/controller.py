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
        """Handle complete job application process."""
        try:
            # First prepare and parse CV
            cv_path, cv_data = await self.doc_processor.prepare_cv_for_upload(cv_path)
            
            # Log CV processing
            await self.tracker_agent.log_activity(
                activity_type='document',
                details=f'Processed CV: {cv_path.name}',
                status='info',
                agent_name='Controller'
            )
            
            # Handle the actual application
            success = await self.linkedin_agent.handle_application_form(cv_path)
            
            # Log the result
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
            return False

    async def run_master_plan(self, plan_steps: list[str]):
        """
        Execute a series of steps according to the AI Master-Plan.
        
        Args:
            plan_steps: List of step names to execute (e.g., ["check_login", "search_jobs"])
        
        Returns:
            bool: True if all steps completed successfully, False otherwise
        """
        try:
            await self.tracker_agent.log_activity(
                activity_type='master_plan',
                details=f'Starting master plan execution: {plan_steps}',
                status='info',
                agent_name='Controller'
            )

            # Execute the plan using AI Navigator
            success, confidence = await self.ai_navigator.execute_master_plan(plan_steps)

            # Log the result
            status = 'success' if success else 'error'
            await self.tracker_agent.log_activity(
                activity_type='master_plan',
                details=f'Master plan {"completed" if success else "failed"} with confidence: {confidence}',
                status=status,
                agent_name='Controller'
            )

            return success

        except Exception as e:
            await self.tracker_agent.log_activity(
                activity_type='master_plan',
                details=f'Master plan execution error: {str(e)}',
                status='error',
                agent_name='Controller'
            )
            return False
