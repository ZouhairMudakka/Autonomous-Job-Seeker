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
            # If controller.start_session() is async, we do:
            asyncio.run(self.controller.start_session())
            print("Session started successfully.")
        except Exception as e:
            print(f"Error starting session: {str(e)}")

    def do_stop(self, arg):
        """
        Stop the current automation session.
        """
        try:
            asyncio.run(self.controller.end_session())
            print("Session ended successfully.")
        except Exception as e:
            print(f"Error ending session: {str(e)}")

    async def do_status(self, arg):
        """
        Show current automation status from tracker_agent logs.
        Because tracker_agent log_activity is async, we wrap get_activities in an async call, too.
        """
        await self.telemetry.track_cli_command('status')
        # We'll define an inline async function to fetch logs, then run it:
        async def fetch_logs():
            # If your tracker_agent.get_activities is synchronous, just call it directly.
            # If it's async, we do: return await self.controller.tracker_agent.get_activities()
            df = self.controller.tracker_agent.get_activities()  # Suppose it's sync
            return df

        try:
            activities = asyncio.run(fetch_logs())
            if activities.empty:
                print("No activities recorded yet.")
            else:
                print("\nRecent activities:")
                # Show the last few
                print(activities.tail().to_string(index=False))
        except Exception as e:
            print(f"Error retrieving status: {str(e)}")

    def do_search(self, arg):
        """
        Example command to run a job search & apply flow.
        Usage: search "Job Title" "Location"
        e.g.: search "Software Engineer" "New York"
        """
        try:
            parts = shlex.split(arg)
            if len(parts) < 2:
                print('Usage: search "Job Title" "Location"')
                return
            job_title = parts[0]
            location = parts[1] if len(parts) > 1 else ""
        except ValueError:
            print('Failed to parse arguments. Ensure you use quotes around the title and location.')
            return

        async def run_flow():
            await self.controller.run_linkedin_flow(job_title, location)
            print(f"Searched & applied for '{job_title}' in '{location}'.")

        try:
            asyncio.run(run_flow())
        except Exception as e:
            print(f"Error running job search flow: {str(e)}")

    def do_pause(self, arg):
        """
        Pause the current automation session.
        """
        try:
            asyncio.run(self.controller.pause_session())
            print("Session paused.")
        except Exception as e:
            print(f"Error pausing session: {str(e)}")

    def do_resume(self, arg):
        """
        Resume the current automation session.
        """
        try:
            asyncio.run(self.controller.resume_session())
            print("Session resumed.")
        except Exception as e:
            print(f"Error resuming session: {str(e)}")

    def do_quit(self, arg):
        """
        Exit the application gracefully.
        """
        print("Shutting down CLI...")
        try:
            asyncio.run(self.controller.end_session())
        except Exception as e:
            print(f"Error ending session: {str(e)}")
        return True

    async def do_config(self, args):
        """Update preferences."""
        await self.telemetry.track_cli_command('config', {'args': args})
        # ... existing code ...

    def default(self, line):
        print(f"Unknown command: {line}")
        print("Type 'help' or '?' for available commands.")
