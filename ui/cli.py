"""
Command Line Interface Module (MVP, async wrapping)

Uses the built-in `cmd` module for synchronous input parsing,
but wraps asynchronous controller calls with `asyncio.run(...)`.

Required Modules:
- cmd: For command-line interface base
- sys: For system-level operations
- asyncio: To run async calls in each command
- datetime: For optional timestamp display

TODO (AI Integration):
- Add AI-specific commands and flags
- Add confidence score display in status
- Add learning pipeline statistics command
- Setup AI debugging commands
- Add AI/systematic mode toggle
"""
"""
Command Line Interface (MVP)

NOTE (Post-MVP): 
-----------------
For now, we're using the built-in `cmd` module with `asyncio.run(...)` calls 
in each command. This approach is sufficient for a small set of commands 
(start/stop/session info). After the MVP stage, we plan to switch to a more 
robust async CLI framework (e.g., Typer), which will allow a continuous 
event loop without calling `asyncio.run` repeatedly, and provide cleaner 
argument parsing, subcommands, and advanced features.
"""

import cmd
import sys
import asyncio
from datetime import datetime
import shlex
from utils.telemetry import TelemetryManager

class CLI(cmd.Cmd):
    intro = 'Welcome to the LinkedIn Automation MVP. Type help or ? to list commands.\n'
    prompt = '(linkedin) '

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.telemetry = TelemetryManager(controller.settings)
        self.logs_manager = controller.logs_manager

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    async def do_start(self, arg):
        """
        Start a new automation session.
        For an MVP, we wrap the async controller.start_session() call using asyncio.run.
        """
        await self.telemetry.track_cli_command("start", {"args": arg})
        try:
            await self.logs_manager.info("Starting new automation session...")
            await self.controller.start_session()
            await self.logs_manager.info("Session started successfully.")
        except Exception as e:
            await self.logs_manager.error(f"Error starting session: {str(e)}")
            raise

    async def do_stop(self, arg):
        """
        Stop the current automation session.
        """
        try:
            await self.logs_manager.info("Stopping current automation session...")
            await self.controller.end_session()
            await self.logs_manager.info("Session ended successfully.")
        except Exception as e:
            await self.logs_manager.error(f"Error ending session: {str(e)}")
            raise

    async def do_status(self, arg):
        """
        Show current automation status from tracker_agent logs.
        Because tracker_agent log_activity is async, we wrap get_activities in an async call, too.
        """
        await self.telemetry.track_cli_command('status')
        await self.logs_manager.info("Fetching current automation status...")
        
        try:
            activities = self.controller.tracker_agent.get_activities()
            if activities.empty:
                await self.logs_manager.info("No activities recorded yet.")
            else:
                await self.logs_manager.info("\nRecent activities:")
                # We still use print for the actual dataframe display since it's tabular data
                print(activities.tail().to_string(index=False))
        except Exception as e:
            await self.logs_manager.error(f"Error retrieving status: {str(e)}")
            raise

    async def do_search(self, arg):
        """
        Example command to run a job search & apply flow.
        Usage: search "Job Title" "Location"
        e.g.: search "Software Engineer" "New York"
        """
        try:
            parts = shlex.split(arg)
            if len(parts) < 2:
                await self.logs_manager.warning('Usage: search "Job Title" "Location"')
                return
            job_title = parts[0]
            location = parts[1] if len(parts) > 1 else ""
            
            await self.logs_manager.info(f"Starting job search for '{job_title}' in '{location}'...")
            await self.controller.run_linkedin_flow(job_title, location)
            await self.logs_manager.info(f"Completed search & apply flow for '{job_title}' in '{location}'.")
            
        except ValueError:
            await self.logs_manager.error('Failed to parse arguments. Ensure you use quotes around the title and location.')
        except Exception as e:
            await self.logs_manager.error(f"Error running job search flow: {str(e)}")
            raise

    async def do_pause(self, arg):
        """
        Pause the current automation session.
        """
        try:
            await self.logs_manager.info("Pausing current session...")
            await self.controller.pause_session()
            await self.logs_manager.info("Session paused successfully.")
        except Exception as e:
            await self.logs_manager.error(f"Error pausing session: {str(e)}")
            raise

    async def do_resume(self, arg):
        """
        Resume the current automation session.
        """
        try:
            await self.logs_manager.info("Resuming session...")
            await self.controller.resume_session()
            await self.logs_manager.info("Session resumed successfully.")
        except Exception as e:
            await self.logs_manager.error(f"Error resuming session: {str(e)}")
            raise

    async def do_quit(self, arg):
        """
        Exit the application gracefully.
        """
        await self.logs_manager.info("Shutting down CLI...")
        try:
            await self.controller.end_session()
            await self.logs_manager.info("Session ended, goodbye!")
            return True
        except Exception as e:
            await self.logs_manager.error(f"Error during shutdown: {str(e)}")
            raise

    async def do_config(self, args):
        """Update preferences."""
        await self.telemetry.track_cli_command('config', {'args': args})
        await self.logs_manager.info(f"Updating configuration with args: {args}")
        # ... existing code ...

    async def default(self, line):
        await self.logs_manager.warning(f"Unknown command: {line}")
        await self.logs_manager.info("Type 'help' or '?' for available commands.")
