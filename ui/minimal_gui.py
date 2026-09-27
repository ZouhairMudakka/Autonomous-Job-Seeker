"""Tk controls sharing the controller's asyncio loop and main thread.

Tk events are pumped by run_app; browser coroutines never cross event loops.
"""
import asyncio
import json
import math
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

from storage.file_utils import atomic_text_writer
from ui.components.ai_decision import AIDecisionView
from ui.components.platform_manager import PlatformManagerView
from ui.components.activity_filter import ActivityFilterView


class MinimalGUI:
    def __init__(self, controller):
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("The GUI must run on the main thread")
        self.async_loop = asyncio.get_running_loop()
        self.controller = controller
        self.logs_manager = controller.logs_manager
        self.telemetry = controller.telemetry
        self.shutdown_requested = False
        self._tasks = set()
        self._automation_task = None
        self._cv_generation = 0
        self._started_at = None
        self.state = {"is_running": False, "is_paused": False, "start_time": None, "error_count": 0}
        self.settings_file = Path(controller.settings.get("system", {}).get("data_dir", "./data")) / "gui_settings.json"
        self.settings = self.load_settings()
        self.window = tk.Tk()
        self.window.title("Job Application Assistant")
        self.window.geometry("1000x750")
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.delay_var = tk.StringVar(self.window, str(self.settings.get("delay", 1.0)))
        self.auto_pause_var = tk.StringVar(self.window, str(self.settings.get("auto_pause_hours", 0)))
        self.job_title_var = tk.StringVar(self.window, self.settings.get("job_title", ""))
        self.location_var = tk.StringVar(self.window, self.settings.get("location", ""))
        self.cv_status_var = tk.StringVar(self.window, "No CV loaded")
        self.status_var = tk.StringVar(self.window, "Ready")
        self._activity_content = ""
        try:
            self.setup_ui()
        except Exception:
            self.window.destroy()
            raise

    def setup_ui(self):
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.control_tab = ttk.Frame(self.notebook)
        self.activity_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        for frame, title in ((self.control_tab, "Control"), (self.activity_tab, "Activity"), (self.settings_tab, "CV")):
            self.notebook.add(frame, text=title)
        self.setup_control_tab()
        self.setup_activity_tab()
        self.setup_settings_tab()

    def setup_control_tab(self):
        for label, variable in (("Job title", self.job_title_var), ("Location", self.location_var),
                                ("Delay (seconds)", self.delay_var), ("Auto-pause (hours, 0 disables)", self.auto_pause_var)):
            row = ttk.Frame(self.control_tab)
            row.pack(fill=tk.X, padx=12, pady=8)
            ttk.Label(row, text=label, width=30).pack(side=tk.LEFT)
            ttk.Entry(row, textvariable=variable).pack(side=tk.LEFT, fill=tk.X, expand=True)
        row = ttk.Frame(self.control_tab)
        row.pack(fill=tk.X, padx=12, pady=8)
        self.start_button = ttk.Button(row, text="Start", command=self.start_automation_command)
        self.pause_button = ttk.Button(row, text="Pause", command=self.pause_automation_command)
        self.stop_button = ttk.Button(row, text="Stop", command=self.stop_automation_command)
        for button in (self.start_button, self.pause_button, self.stop_button):
            button.pack(side=tk.LEFT, padx=5)
        ttk.Label(self.control_tab, textvariable=self.status_var).pack(anchor=tk.W, padx=12, pady=12)

    def setup_activity_tab(self):
        self.ai_decision_view = AIDecisionView(self.activity_tab)
        self.ai_decision_view.pack(fill=tk.BOTH, expand=True)
        self.activity_filter = ActivityFilterView(self.activity_tab)
        self.activity_filter.pack(fill=tk.BOTH, expand=True)
        self.platform_manager = PlatformManagerView(self.activity_tab)
        self.platform_manager.pack(fill=tk.X)

    def setup_settings_tab(self):
        row = ttk.Frame(self.settings_tab)
        row.pack(fill=tk.X, padx=12, pady=12)
        ttk.Button(row, text="Select CV", command=self.select_cv_file).pack(side=tk.LEFT)
        ttk.Button(row, text="Remove CV", command=self.remove_cv_file).pack(side=tk.LEFT, padx=8)
        ttk.Label(row, textvariable=self.cv_status_var).pack(side=tk.LEFT)
        self.cv_preview_text = scrolledtext.ScrolledText(self.settings_tab, wrap=tk.WORD, state=tk.DISABLED)
        self.cv_preview_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    async def run_app(self):
        try:
            while not self.shutdown_requested:
                self.window.update()
                self.update_status_loop()
                self.check_auto_pause()
                await asyncio.sleep(0.05)
        finally:
            self.shutdown_requested = True
            pending = [task for task in self._tasks if not task.done()]
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            try:
                await self.controller.end_session()
            finally:
                self.cleanup()

    def run_coroutine_in_background(self, coro):
        if self.shutdown_requested:
            coro.close()
            return None
        task = self.async_loop.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task):
        self._tasks.discard(task)
        if not task.cancelled():
            error = task.exception()
            if error is not None:
                self.state["error_count"] += 1
                self.log_activity(f"Operation failed: {error}", "ERROR")

    def start_automation_command(self):
        if self._automation_task is None or self._automation_task.done():
            self._automation_task = self.run_coroutine_in_background(self.start_automation())

    async def start_automation(self):
        title, location = self.job_title_var.get().strip(), self.location_var.get().strip()
        if not title or not location:
            raise ValueError("Enter a job title and location")
        settings = self._read_form_settings()
        self.controller.settings.update(job_title=title, location=location)
        self.controller.linkedin_agent.min_delay = settings["delay"]
        self.controller.linkedin_agent.max_delay = settings["delay"] * 1.5
        self.save_settings()
        self.state.update(is_running=True, is_paused=False, start_time=datetime.now())
        self._started_at = time.monotonic()
        self.log_activity("Search started")
        try:
            await self.controller.start_session()
            await self.controller.run_linkedin_flow(title, location)
            self.log_activity("Search finished; check activity records for individual application outcomes")
        finally:
            self.state.update(is_running=False, is_paused=False)

    def pause_automation_command(self):
        self.run_coroutine_in_background(self.pause_automation())

    async def pause_automation(self):
        if not self.state["is_running"]:
            return
        if self.state["is_paused"]:
            await self.controller.resume_session()
            self.state["is_paused"] = False
            self._started_at = time.monotonic()
        else:
            await self.controller.pause_session()
            self.state["is_paused"] = True

    def stop_automation_command(self):
        self.run_coroutine_in_background(self.stop_automation())

    async def stop_automation(self):
        task = self._automation_task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self.controller.end_session()
        self.state.update(is_running=False, is_paused=False)
        self.log_activity("Stopped")

    def update_status_loop(self):
        running, paused = self.state["is_running"], self.state["is_paused"]
        self.status_var.set("Paused" if paused else "Running" if running else "Ready")
        self.start_button.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.pause_button.configure(state=tk.NORMAL if running else tk.DISABLED, text="Resume" if paused else "Pause")
        self.stop_button.configure(state=tk.NORMAL if running else tk.DISABLED)

    def check_auto_pause(self):
        try:
            hours = float(self.auto_pause_var.get())
        except ValueError:
            return
        if (math.isfinite(hours) and hours > 0 and self.state["is_running"]
                and not self.state["is_paused"] and self._started_at is not None
                and time.monotonic() - self._started_at >= hours * 3600):
            self._started_at = None
            self.pause_automation_command()

    def _read_form_settings(self):
        delay, hours = float(self.delay_var.get()), float(self.auto_pause_var.get())
        if not all(math.isfinite(value) and value >= 0 for value in (delay, hours)):
            raise ValueError("Delay and auto-pause must be finite, non-negative numbers")
        return {"delay": delay, "auto_pause_hours": hours,
                "job_title": self.job_title_var.get(), "location": self.location_var.get()}

    def save_settings(self):
        settings = self._read_form_settings()
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        with atomic_text_writer(self.settings_file) as stream:
            json.dump(settings, stream)
        self.settings = settings

    def load_settings(self):
        try:
            data = json.loads(self.settings_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def select_cv_file(self):
        selected = filedialog.askopenfilename(parent=self.window, filetypes=[("CV documents", "*.pdf *.docx *.txt")])
        if selected:
            self._cv_generation += 1
            self.run_coroutine_in_background(self.parse_cv_content(Path(selected), self._cv_generation))

    async def parse_cv_content(self, file_path, generation=None):
        if generation is None:
            self._cv_generation += 1
            generation = self._cv_generation
        path = Path(file_path)
        if not path.is_file() or path.suffix.lower() not in {".pdf", ".docx", ".txt"}:
            raise ValueError("Select a PDF, DOCX or text file")
        if not 0 < path.stat().st_size <= 5 * 1024 * 1024:
            raise ValueError("CV files must be non-empty and at most 5 MB")
        data = await self.controller.cv_parser.parse_cv(path)
        if generation != self._cv_generation or self.shutdown_requested:
            return
        if hasattr(data, "model_dump"):
            data = data.model_dump(mode="json")
        if not isinstance(data, dict):
            raise ValueError("CV parser returned invalid data")
        self.controller.settings.update(cv_path=str(path), parsed_cv_data=data)
        self.cv_status_var.set(path.name)
        self.cv_preview_text.configure(state=tk.NORMAL)
        self.cv_preview_text.delete("1.0", tk.END)
        self.cv_preview_text.insert(tk.END, str(data.get("raw_text", data.get("text", "CV parsed")))[:10000])
        self.cv_preview_text.configure(state=tk.DISABLED)
        self.log_activity("CV loaded")

    def remove_cv_file(self):
        self._cv_generation += 1
        self.controller.settings.pop("cv_path", None)
        self.controller.settings.pop("parsed_cv_data", None)
        self.cv_status_var.set("No CV loaded")
        self.cv_preview_text.configure(state=tk.NORMAL)
        self.cv_preview_text.delete("1.0", tk.END)
        self.cv_preview_text.configure(state=tk.DISABLED)

    def log_activity(self, message, activity_type="SYSTEM"):
        if self.shutdown_requested:
            return
        self._activity_content += f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{activity_type}] {message}\n"
        self._activity_content = self._activity_content[-100000:]
        self.activity_filter.add_activity(message, activity_type)

    def verify_components(self):
        return {"event_loop": {"running": self.async_loop.is_running()}, "window": bool(self.window.winfo_exists())}

    def on_closing(self):
        try:
            self.save_settings()
        except (OSError, ValueError) as exc:
            self.log_activity(f"Settings were not saved: {exc}", "ERROR")
        self.shutdown_requested = True

    def stop(self):
        self.on_closing()

    def cleanup(self):
        try:
            self.window.destroy()
        except tk.TclError:
            pass
