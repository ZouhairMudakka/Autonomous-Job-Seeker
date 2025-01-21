"""
Minimal GUI Implementation for LinkedIn Automation Tool (Updated MVP)

This module provides a simple desktop GUI interface that:
1. Controls automation (start/stop/pause/resume)
2. Displays basic status (including a mini console for short updates/errors)
3. Writes to an extension status file (status.json) if desired
4. Uses tkinter for a lightweight interface with tab-based layout (console + settings)

Future Enhancements:
- More robust concurrency (using async_tkinter_loop or a separate thread if needed)
- Advanced job search config panel
- Detailed logs or a scrollable console
- Potential 'ui/components/' folder if the GUI grows significantly
- Switch between modes (auto / CLI / GUI) on the fly (for now, user restarts app)

Important MVP Notes:
-------------------
1) We do not handle extensive concurrency. We rely on the user not to spam 
   the Pause/Resume/Stop buttons too quickly. (We add a note about this in the UI.)
2) We do not track 'jobs viewed' or 'applications' in real time in this MVP. 
   We only handle success/fail confirmations or session state changes.
3) We log errors in the console traceback and also store them in status.json (optional).
4) If you want to do real-time concurrency tasks, 
   you might need a bridging library or threads.

"""

import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
import asyncio
from datetime import datetime
from typing import Optional
import threading

class MinimalGUI:
    def __init__(self, controller):
        """Initialize the GUI with a reference to the automation controller."""
        self.controller = controller

        # Add background event loop setup
        self.loop = asyncio.new_event_loop()
        self.background_thread = threading.Thread(
            target=self.loop.run_forever, 
            daemon=True
        )
        self.background_thread.start()

        # Initialize states
        self.is_running = False
        self.is_paused = False
        self.start_time: Optional[datetime] = None

        # Setup main window
        self.window = tk.Tk()
        self.window.title("LinkedIn Automation Control (MVP)")
        # A vertical size that can be adjusted
        self.window.geometry("500x600")
        self.window.resizable(True, True)

        # Note: we add a comment disclaiming pressing buttons too quickly:
        self.press_note = (
            "NOTE: Please avoid pressing multiple actions too quickly. "
            "We're using a basic async approach and can't handle rapid-fire commands gracefully."
        )

        # Extension file for status
        self.extension_status_file = Path("ui/extension/status.json")

        # Setup tab-based UI
        self.setup_ui()

        # Start periodic update loop
        self.update_status_loop()

    def setup_ui(self):
        """Create and arrange GUI elements in a tabbed layout (Console + Settings)."""

        # Create a Notebook for tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # ---------- CONSOLE TAB ----------
        self.console_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.console_tab, text="Console")

        # Title in console tab
        console_title = ttk.Label(
            self.console_tab, 
            text="Automation Controls & Console",
            font=("Arial", 14, "bold")
        )
        console_title.pack(pady=5)

        # Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(
            self.console_tab,
            textvariable=self.status_var,
            font=("Arial", 12, "bold"),
            foreground="green"
        )
        self.status_label.pack(pady=5)

        # Runtime display
        self.runtime_var = tk.StringVar(value="Runtime: 00:00:00")
        self.runtime_label = ttk.Label(
            self.console_tab,
            textvariable=self.runtime_var
        )
        self.runtime_label.pack(pady=5)

        # Add note about not pressing buttons too quickly
        note_label = ttk.Label(
            self.console_tab,
            text=self.press_note,
            wraplength=400,
            foreground="blue"
        )
        note_label.pack(pady=5)

        # Control buttons
        self.start_button = ttk.Button(
            self.console_tab,
            text="Start Automation",
            command=self.start_automation_command
        )
        self.start_button.pack(pady=5, fill=tk.X)

        self.pause_button = ttk.Button(
            self.console_tab,
            text="Pause",
            command=self.pause_automation_command,
            state=tk.DISABLED
        )
        self.pause_button.pack(pady=5, fill=tk.X)

        self.stop_button = ttk.Button(
            self.console_tab,
            text="Stop",
            command=self.stop_automation_command,
            state=tk.DISABLED
        )
        self.stop_button.pack(pady=5, fill=tk.X)

        # A mini console for short logs or errors
        console_frame = ttk.LabelFrame(self.console_tab, text="Console Log", padding="5")
        console_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.console_text = tk.Text(console_frame, height=10, wrap=tk.WORD)
        self.console_text.pack(fill=tk.BOTH, expand=True)

        # ---------- SETTINGS / OPTIONS TAB ----------
        self.settings_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.settings_tab, text="Settings / More Options")

        # Placeholders for future expansions
        settings_label = ttk.Label(
            self.settings_tab,
            text="(Future) Configuration panel. For now, no settings to change."
        )
        settings_label.pack()

        # Possibly add more advanced fields here for job title, location, concurrency, etc.

    async def start_automation(self):
        """Start the automation process."""
        self.log_to_console("Start button pressed. Attempting to start session.")
        self.is_running = True
        self.is_paused = False
        self.start_time = datetime.now()

        self.status_var.set("Running")
        self.status_label.config(foreground="green")

        self.start_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL)

        try:
            await self.controller.start_session()
            self.log_to_console("Session started successfully.")
        except Exception as e:
            self.log_error(f"Error starting session: {str(e)}")

        self._update_extension_status()

    async def pause_automation(self):
        """Pause/Resume the automation."""
        self.log_to_console("Pause/Resume button pressed.")
        self.is_paused = not self.is_paused
        status = "Paused" if self.is_paused else "Running"
        button_text = "Resume" if self.is_paused else "Pause"

        self.status_var.set(status)
        self.status_label.config(foreground="orange" if self.is_paused else "green")
        self.pause_button.config(text=button_text)

        try:
            if self.is_paused:
                # We assume controller has 'pause_session'
                await self.controller.pause_session()
                self.log_to_console("Session paused.")
            else:
                # We assume controller has 'resume_session'
                await self.controller.resume_session()
                self.log_to_console("Session resumed.")
        except Exception as e:
            self.log_error(f"Error pausing/resuming: {str(e)}")

        self._update_extension_status()

    async def stop_automation(self):
        """Stop the automation process."""
        self.log_to_console("Stop button pressed. Stopping session.")
        self.is_running = False
        self.is_paused = False
        self.start_time = None

        self.status_var.set("Stopped")
        self.status_label.config(foreground="red")
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED, text="Pause")
        self.stop_button.config(state=tk.DISABLED)

        try:
            await self.controller.end_session()
            self.log_to_console("Session ended.")
        except Exception as e:
            self.log_error(f"Error ending session: {str(e)}")

        self._update_extension_status()

    def log_to_console(self, message: str):
        """Append a line to the mini console area."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.console_text.see(tk.END)  # auto-scroll to bottom

    def log_error(self, message: str):
        """Log errors in console and in status.json."""
        self.log_to_console(message)
        # Also write error in status.json
        try:
            if self.extension_status_file:
                with open(self.extension_status_file, 'r') as f:
                    data = json.load(f)
        except:
            data = {}  # If file doesn't exist or read fails

        if "errors" not in data:
            data["errors"] = []
        data["errors"].append(message)

        self.extension_status_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.extension_status_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _update_extension_status(self):
        """Update status.json for browser extension or debug usage."""
        try:
            status = {
                "is_running": self.is_running,
                "is_paused": self.is_paused,
                "status": self.status_var.get(),
                "runtime": self.runtime_var.get(),
                "errors": []
            }

            # If file already has errors, keep them
            current_data = {}
            if self.extension_status_file.exists():
                with open(self.extension_status_file, 'r') as f:
                    current_data = json.load(f)
            current_data.update(status)
            self.extension_status_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.extension_status_file, 'w') as f:
                json.dump(current_data, f, indent=2)
        except Exception as e:
            # If something fails in writing the status, we log it in console
            self.log_to_console(f"Error writing extension status: {str(e)}")

    def update_status_loop(self):
        """Update runtime if running, every second."""
        if self.is_running and self.start_time and not self.is_paused:
            runtime = datetime.now() - self.start_time
            hours, remainder = divmod(runtime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.runtime_var.set(f"Runtime: {hours:02d}:{minutes:02d}:{seconds:02d}")

        # Schedule next update
        self.window.after(1000, self.update_status_loop)

    def start(self):
        """Start the GUI event loop (legacy method name)."""
        self.run_app()

    def run_app(self):
        """Start the GUI event loop (new preferred method name)."""
        self.window.mainloop()

    def stop(self):
        """
        Clean shutdown of GUI.
        If the user closes the window or picks a different mode, we might do final cleanup.
        """
        if self.is_running:
            self.run_coroutine_in_background(self.stop_automation())
        self.loop.call_soon_threadsafe(self.loop.stop)  # stop the loop
        self.window.destroy()
        self.background_thread.join()

    def run_coroutine_in_background(self, coro):
        """Schedule an async coroutine to run on the background event loop."""
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    # Add new command methods
    def start_automation_command(self):
        """GUI button callback that schedules start_automation in the background."""
        self.run_coroutine_in_background(self.start_automation())

    def pause_automation_command(self):
        """GUI button callback that schedules pause_automation in the background."""
        self.run_coroutine_in_background(self.pause_automation())

    def stop_automation_command(self):
        """GUI button callback that schedules stop_automation in the background."""
        self.run_coroutine_in_background(self.stop_automation())

# Additional comment about possibly splitting the code into a ui/components/ folder
# if the GUI grows with multiple custom widgets or advanced config tabs.
