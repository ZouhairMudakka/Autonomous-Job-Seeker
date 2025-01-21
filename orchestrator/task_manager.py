"""
Task Management Module (Async Version)

This module handles the queuing and execution of automation tasks,
providing a concurrency-friendly approach via asyncio.

Replaces the old thread-based design with async/await logic.
"""

import asyncio
import time
from constants import TimingConstants, Messages

class TaskManager:
    def __init__(self, controller):
        """
        Args:
            controller: Reference to the main controller (for logging, tracker access, etc.)
        """
        self.controller = controller
        self.task_queue = asyncio.Queue()
        self.is_running = False
        self.processor_task = None
        self.tasks = []  # Store active tasks
        
        # Use constants for delays
        self.poll_interval = TimingConstants.POLL_INTERVAL
        self.action_delay = TimingConstants.ACTION_DELAY

    async def create_task(self, coro):
        """Creates a new async task from a coroutine."""
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        
        # Use task ID for logging with constant message
        task_id = id(task)
        await self.controller.tracker_agent.log_activity(
            activity_type='task_created',
            details=Messages.TASK_CREATED.format(task_id),
            status='info',
            agent_name='TaskManager'
        )
        return task

    async def run_task(self, task):
        """Runs a task and handles logging."""
        try:
            result = await task
            await self.controller.tracker_agent.log_activity(
                activity_type='task_completed',
                details=Messages.TASK_COMPLETED.format(id(task)),
                status='success',
                agent_name='TaskManager'
            )
            return result
        except Exception as e:
            await self.controller.tracker_agent.log_activity(
                activity_type='task_failed',
                details=Messages.TASK_FAILED.format(str(e)),
                status='error',
                agent_name='TaskManager'
            )
            raise

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

        if task_type == 'job_search':
            job_title = params.get('job_title')
            location = params.get('location')
            await self.controller.run_linkedin_flow(job_title, location)
        elif task_type == 'captcha':
            await self.controller.credentials_agent.handle_captcha()
        else:
            # Unknown or future tasks
            pass

        await self.controller.tracker_agent.log_activity(
            activity_type='task_execute',
            details=f"Executed task {task_type} with params={params}",
            status='success',
            agent_name='TaskManager'
        )
