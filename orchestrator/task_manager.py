"""
Task Management Module (Async Version)

This module handles the queuing and execution of automation tasks,
providing a concurrency-friendly approach via asyncio.

Replaces the old thread-based design with async/await logic.
"""

import asyncio
import time
from constants import TimingConstants, Messages
from datetime import datetime, timedelta
from typing import Any, Coroutine

class Task:
    def __init__(self, coroutine: Coroutine, task_id: str = None):
        self.coroutine = coroutine
        self.task_id = task_id or datetime.now().isoformat()
        self.created_at = datetime.now()
        self.completed_at = None
        self.status = 'pending'
        self.result = None
        self.error = None

class TaskManager:
    def __init__(self, controller):
        """
        Args:
            controller: Reference to the main controller (for logging, tracker access, etc.)
        """
        self.controller = controller
        self.tasks = {}
        self.active_tasks = set()
        self.max_concurrent = 3
        self.queue_check_interval = TimingConstants.QUEUE_CHECK_INTERVAL
        self.task_timeout = TimingConstants.TASK_TIMEOUT

    async def create_task(self, coroutine: Coroutine, task_id: str = None) -> Task:
        """Create a new task."""
        task = Task(coroutine, task_id)
        self.tasks[task.task_id] = task
        
        await self.controller.tracker_agent.log_activity(
            activity_type='task',
            details=Messages.TASK_CREATED.format(task.task_id),
            status='created',
            agent_name='TaskManager'
        )
        
        return task

    async def run_task(self, task: Task) -> Any:
        """Run a task with timeout and error handling."""
        try:
            if len(self.active_tasks) >= self.max_concurrent:
                await self._wait_for_slot()

            self.active_tasks.add(task.task_id)
            task.status = 'running'

            # Run with timeout
            result = await asyncio.wait_for(
                task.coroutine,
                timeout=self.task_timeout
            )

            task.status = 'completed'
            task.completed_at = datetime.now()
            task.result = result
            
            await self.controller.tracker_agent.log_activity(
                activity_type='task',
                details=Messages.TASK_COMPLETED.format(task.task_id),
                status='success',
                agent_name='TaskManager'
            )

            return result

        except asyncio.TimeoutError:
            task.status = 'timeout'
            task.error = 'Task timed out'
            raise

        except Exception as e:
            task.status = 'failed'
            task.error = str(e)
            
            await self.controller.tracker_agent.log_activity(
                activity_type='task',
                details=Messages.TASK_FAILED.format(f"{task.task_id}: {str(e)}"),
                status='error',
                agent_name='TaskManager'
            )
            
            raise

        finally:
            self.active_tasks.discard(task.task_id)

    async def _wait_for_slot(self):
        """Wait for a task slot to become available."""
        while len(self.active_tasks) >= self.max_concurrent:
            await asyncio.sleep(self.queue_check_interval)

    def get_task(self, task_id: str) -> Task:
        """Get task by ID."""
        return self.tasks.get(task_id)

    def get_active_tasks(self) -> list[Task]:
        """Get list of currently active tasks."""
        return [
            self.tasks[task_id] 
            for task_id in self.active_tasks
        ]

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        task = self.tasks.get(task_id)
        if task and task.status == 'running':
            task.status = 'cancelled'
            self.active_tasks.discard(task_id)
            return True
        return False

    async def add_task(self, task_type, params):
        """
        Add a new task to the queue.
        'task_type' (str) e.g. "job_search", "captcha", etc.
        'params' (dict) any parameters needed for that task.
        """
        task_info = {
            'type': task_type,
            'params': params,
            'added_time': time.time()
        }
        await self.task_queue.put(task_info)

    async def start_processing(self):
        """Begin processing tasks in the queue (in the background)."""
        if self.is_running:
            return  # already running

        self.is_running = True
        self.processor_task = asyncio.create_task(self._process_tasks())
        await self.controller.tracker_agent.log_activity(
            activity_type='task_manager',
            details='Task processing started',
            status='info',
            agent_name='TaskManager'
        )

    async def stop_processing(self):
        """Stop processing tasks gracefully."""
        if not self.is_running:
            return  # not running

        self.is_running = False
        if self.processor_task:
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass
            self.processor_task = None

        await self.controller.tracker_agent.log_activity(
            activity_type='task_manager',
            details='Task processing stopped',
            status='info',
            agent_name='TaskManager'
        )

    async def _process_tasks(self):
        """Continuously checks the queue for new tasks and processes them."""
        try:
            while self.is_running:
                if not self.task_queue.empty():
                    task = await self.task_queue.get()
                    try:
                        await self._execute_task(task)
                    except Exception as e:
                        await self.controller.tracker_agent.log_activity(
                            activity_type='task_error',
                            details=Messages.TASK_FAILED.format(str(e)),
                            status='error',
                            agent_name='TaskManager'
                        )
                else:
                    # Use constant for queue check interval
                    await asyncio.sleep(TimingConstants.QUEUE_CHECK_INTERVAL)
        except asyncio.CancelledError:
            # This means stop_processing() was called, so we do a graceful exit
            pass

    async def _execute_task(self, task):
        """Execute a single task based on task_type."""
        task_type = task['type']
        params = task['params']

        try:
            if task_type == 'job_search':
                job_title = params.get('job_title')
                location = params.get('location')
                await self.controller.run_linkedin_flow(job_title, location)
                
            elif task_type == 'captcha':
                await self.controller.credentials_agent.handle_captcha()
                
            elif task_type == 'state_restoration':
                # Handle state restoration with verification
                success = await self.controller._restore_session_state()
                if not success:
                    raise Exception("State restoration failed")
                
                # Verify restoration with AI Navigator
                verify_success, confidence = await self.controller.ai_navigator.execute_master_plan([
                    "verify_action",
                    "double_verify_action"
                ])
                if not verify_success:
                    raise Exception(f"State restoration verification failed (confidence: {confidence})")
                
            elif task_type == 'recovery':
                # Handle recovery tasks
                success, confidence = await self.controller.ai_navigator.execute_master_plan([
                    "recovery_check",
                    "verify_action"
                ])
                if not success:
                    raise Exception(f"Recovery failed (confidence: {confidence})")
                
            elif task_type == 'verification':
                # Handle standalone verification tasks
                verify_params = params.get('verify_params', {})
                success, confidence = await self.controller.ai_navigator.execute_master_plan([
                    "verify_action",
                    *(["double_verify_action"] if verify_params.get('double_verify') else [])
                ])
                if not success:
                    raise Exception(f"Verification failed (confidence: {confidence})")
            
            else:
                # Unknown or future tasks
                print(f"[TaskManager] Unknown task type: {task_type}")
                return

            await self.controller.tracker_agent.log_activity(
                activity_type='task_execute',
                details=f"Executed task {task_type} with params={params}",
                status='success',
                agent_name='TaskManager'
            )

        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            print(f"[TaskManager] {error_msg}")
            
            await self.controller.tracker_agent.log_activity(
                activity_type='task_execute',
                details=error_msg,
                status='error',
                agent_name='TaskManager'
            )
            
            # Re-raise to let caller handle
            raise
