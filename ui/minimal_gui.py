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

Additional Future Components to be Implemented:
---------------------------------------------

1. Real-time Job Processing View:
   - Live job card display
   - Current job being processed
   - Queue visualization
   - Match score display
   - Application status tracking

2. AI Decision Visualization:
   - AI confidence scores display
   - Decision tree visualization
   - Real-time strategy adjustments
   - Fallback triggers display
   - AI reasoning explanation panel

3. Multi-Platform Integration:
   - Platform selection interface
   - Platform-specific settings
   - Cross-platform job tracking
   - Integration status monitoring
   - Platform performance metrics

4. Advanced Analytics Dashboard:
   - Job market trends visualization
   - Success rate analytics
   - Skill demand graphs
   - Salary range analysis
   - Geographic opportunity mapping

5. Profile Management:
   - Resume version control
   - Cover letter template management
   - Skill matrix editor
   - Experience highlighting tools
   - Profile optimization suggestions

These components would be implemented as separate classes in the ui/components/ folder:
    components/
    ├── job_processing.py      # JobProcessingView
    ├── ai_decision.py         # AIDecisionView
    ├── platform_manager.py    # PlatformManagerView
    ├── analytics.py           # AnalyticsDashboard
    └── profile_manager.py     # ProfileManager

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
from tkinter import ttk, filedialog
import json
from pathlib import Path
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import threading
from utils.telemetry import TelemetryManager
import PyPDF2
import csv
try:
    from tkcalendar import Calendar  # Use tkcalendar instead of tkinter.Calendar
except ImportError:
    print("Warning: tkcalendar not installed. Calendar functionality will be limited.")
    Calendar = None
import os

# Constants for better maintainability
ACTIVITY_TYPES = {
    "AI_THINKING": {"color": "#9C27B0", "icon": "🤔"},
    "AI_DECISION": {"color": "#4CAF50", "icon": "✅"},
    "AI_ANALYSIS": {"color": "#FF9800", "icon": "🔍"},
    "AI_GENERATION": {"color": "#E91E63", "icon": "✨"},
    "NAVIGATION": {"color": "#2196F3", "icon": "🌐"},
    "CLICK": {"color": "#03A9F4", "icon": "👆"},
    "FORM_FILL": {"color": "#00BCD4", "icon": "📝"},
    "CAPTCHA": {"color": "#F44336", "icon": "🔒"},
    "CV_PARSE": {"color": "#795548", "icon": "📄"},
    "DATA_ANALYSIS": {"color": "#607D8B", "icon": "📊"},
    "JOB_MATCH": {"color": "#8BC34A", "icon": "🎯"},
    "AUTH": {"color": "#FFC107", "icon": "🔑"},
    "SYSTEM": {"color": "#9E9E9E", "icon": "⚙️"},
    "ERROR": {"color": "#FF5252", "icon": "❌"},
    "AGENT_HANDOFF": {"color": "#673AB7", "icon": "🔄"},
    "DELEGATION": {"color": "#3F51B5", "icon": "📤"}
}

LOG_LEVELS = {
    "INFO": {"color": "#0078D4"},
    "WARNING": {"color": "#ffc107"},
    "ERROR": {"color": "#dc3545"}
}

class MinimalGUI:
    def __init__(self, controller):
        """Initialize the GUI with a reference to the automation controller."""
        self.controller = controller
        
        # Initialize telemetry with error handling
        self.telemetry = None
        try:
            self.telemetry = TelemetryManager(controller.settings)
        except Exception as e:
            print(f"Warning: Failed to initialize telemetry: {e}")

        # Add background event loop setup
        self.loop = None
        self.background_thread = None
        try:
            self.loop = asyncio.new_event_loop()
            self.background_thread = threading.Thread(
                target=self._run_event_loop,
                daemon=True
            )
            self.background_thread.start()
        except Exception as e:
            print(f"Error setting up event loop: {e}")
            raise

        # Initialize states
        self.is_running = False
        self.is_paused = False
        self.start_time: Optional[datetime] = None
        self.last_error_time = None
        self.error_count = 0

        # Setup main window
        self.window = tk.Tk()
        self.window.title("LinkedIn Automation Control (MVP)")
        self.window.geometry("500x600")
        self.window.resizable(True, True)
        
        # Add window close handler
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Note: we add a comment disclaiming pressing buttons too quickly:
        self.press_note = (
            "NOTE: Please avoid pressing multiple actions too quickly. "
            "We're using a basic async approach and can't handle rapid-fire commands gracefully."
        )

        # Extension file for status
        self.extension_status_file = Path("ui/extension/status.json")

        # Initialize settings
        self.settings_file = Path("ui/settings.json")
        self.settings = self.load_settings()

        # Setup tab-based UI
        self.setup_ui()

        # Start periodic update loop
        self.update_status_loop()

    def _run_event_loop(self):
        """Run the event loop with error handling and recovery."""
        while True:
            try:
                asyncio.set_event_loop(self.loop)
                self.loop.run_forever()
            except Exception as e:
                self.log_error(f"Event loop error: {e}")
                # Only attempt recovery if we're still running
                if self.is_running:
                    self.log_to_console("Attempting to recover event loop...", level="WARNING")
                    try:
                        # Create new event loop
                        self.loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(self.loop)
                        continue
                    except Exception as recovery_error:
                        self.log_error(f"Failed to recover event loop: {recovery_error}")
                break
            except KeyboardInterrupt:
                break

    async def _track_telemetry(self, event_type: str, data: dict = None):
        """Safely track telemetry events."""
        if self.telemetry:
            try:
                await self.telemetry.track_event(
                    event_type=event_type,
                    data=data or {},
                    success=True
                )
            except Exception as e:
                print(f"Warning: Failed to track telemetry: {e}")

    def on_closing(self):
        """Handle window closing event."""
        if self.is_running:
            self.run_coroutine_in_background(self.stop_automation())
        self.stop()

    def setup_ui(self):
        """Create and arrange GUI elements in a tabbed layout (Console + Settings)."""
        # Configure custom styles
        style = ttk.Style()
        style.configure(
            "Custom.TButton",
            padding=10,
            font=("Arial", 10),
            background="#0078D4",
            foreground="white"
        )
        style.configure(
            "Success.TButton",
            padding=10,
            font=("Arial", 10, "bold"),
            background="#28a745",
            foreground="white"
        )
        style.configure(
            "Warning.TButton",
            padding=10,
            font=("Arial", 10),
            background="#ffc107",
            foreground="black"
        )
        style.configure(
            "Danger.TButton",
            padding=10,
            font=("Arial", 10),
            background="#dc3545",
            foreground="white"
        )
        style.configure(
            "Custom.TLabelframe",
            padding=15,
            background="#f8f9fa"
        )
        style.configure(
            "Custom.TLabel",
            font=("Arial", 10),
            padding=5
        )
        style.configure(
            "Title.TLabel",
            font=("Arial", 16, "bold"),
            padding=10,
            foreground="#0078D4"
        )
        style.configure(
            "Subtitle.TLabel",
            font=("Arial", 12),
            padding=8,
            foreground="#666666"
        )
        
        # Configure window
        self.window.configure(bg="#f0f2f5")

        # Create a Notebook for tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ---------- CONSOLE TAB ----------
        self.console_tab = ttk.Frame(self.notebook, padding="20")
        self.console_tab.configure(style="Custom.TFrame")
        self.notebook.add(self.console_tab, text="Console")

        # Title in console tab with new style
        console_title = ttk.Label(
            self.console_tab, 
            text="Automation Controls & Console",
            style="Title.TLabel"
        )
        console_title.pack(pady=10)

        # Status label with enhanced style
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(
            self.console_tab,
            textvariable=self.status_var,
            style="Subtitle.TLabel"
        )
        self.status_label.pack(pady=5)

        # Runtime display with custom style
        self.runtime_var = tk.StringVar(value="Runtime: 00:00:00")
        self.runtime_label = ttk.Label(
            self.console_tab,
            textvariable=self.runtime_var,
            style="Custom.TLabel"
        )
        self.runtime_label.pack(pady=5)

        # Control buttons frame for better organization
        control_frame = ttk.Frame(self.console_tab)
        control_frame.pack(fill=tk.X, pady=15)

        # Start button with success style
        self.start_button = ttk.Button(
            control_frame,
            text="🤖 Start AI Job Search",
            command=self.start_automation_command,
            style="Success.TButton"
        )
        self.start_button.pack(pady=5, fill=tk.X)

        # Pause button with warning style
        self.pause_button = ttk.Button(
            control_frame,
            text="⏸ Pause AI Agents",
            command=self.pause_automation_command,
            state=tk.DISABLED,
            style="Warning.TButton"
        )
        self.pause_button.pack(pady=5, fill=tk.X)

        # Stop button with danger style
        self.stop_button = ttk.Button(
            control_frame,
            text="⏹ Stop Job Search",
            command=self.stop_automation_command,
            state=tk.DISABLED,
            style="Danger.TButton"
        )
        self.stop_button.pack(pady=5, fill=tk.X)

        # Console frame with enhanced styling
        console_frame = ttk.LabelFrame(
            self.console_tab,
            text="Console Log",
            padding="15",
            style="Custom.TLabelframe"
        )
        console_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # AI Activity Monitor section
        activity_frame = ttk.LabelFrame(
            console_frame,
            text="Automation Activity Monitor",
            padding="10",
            style="Custom.TLabelframe"
        )
        activity_frame.pack(fill=tk.X, pady=(0, 10))

        # Filter controls
        filter_frame = ttk.Frame(activity_frame)
        filter_frame.pack(fill=tk.X, pady=5)

        # Filter by type
        ttk.Label(
            filter_frame,
            text="Type:",
            style="Custom.TLabel"
        ).pack(side=tk.LEFT, padx=5)

        self.filter_var = tk.StringVar(value="ALL")
        filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_var,
            values=["ALL", "AI Core", "Navigation", "Data", "System", "Agents", "Errors Only", "Success Only"],
            width=12,
            state="readonly"
        )
        filter_combo.pack(side=tk.LEFT, padx=5)
        filter_combo.bind('<<ComboboxSelected>>', self.apply_activity_filter)

        # Filter by agent
        ttk.Label(
            filter_frame,
            text="Agent:",
            style="Custom.TLabel"
        ).pack(side=tk.LEFT, padx=5)

        self.agent_filter_var = tk.StringVar(value="ALL")
        agent_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.agent_filter_var,
            values=["ALL", "NavigatorAgent", "CVParserAgent", "FormFillerAgent", "MatcherAgent", "AuthAgent"],
            width=12,
            state="readonly"
        )
        agent_combo.pack(side=tk.LEFT, padx=5)
        agent_combo.bind('<<ComboboxSelected>>', self.apply_activity_filter)

        # Time range filter
        time_frame = ttk.Frame(activity_frame)
        time_frame.pack(fill=tk.X, pady=2)

        ttk.Label(
            time_frame,
            text="Time:",
            style="Custom.TLabel"
        ).pack(side=tk.LEFT, padx=5)

        self.time_filter_var = tk.StringVar(value="ALL")
        time_combo = ttk.Combobox(
            time_frame,
            textvariable=self.time_filter_var,
            values=["ALL", "Last 5 min", "Last 15 min", "Last hour", "Today", "Custom Range"],
            width=12,
            state="readonly"
        )
        time_combo.pack(side=tk.LEFT, padx=5)
        time_combo.bind('<<ComboboxSelected>>', self.on_time_filter_change)

        # Custom date range frame
        self.date_range_frame = ttk.Frame(activity_frame)
        
        # From date
        ttk.Label(
            self.date_range_frame,
            text="From:",
            style="Custom.TLabel"
        ).pack(side=tk.LEFT, padx=5)
        
        self.from_date_var = tk.StringVar()
        self.from_date_entry = ttk.Entry(
            self.date_range_frame,
            textvariable=self.from_date_var,
            width=16
        )
        self.from_date_entry.pack(side=tk.LEFT, padx=2)
        
        # To date
        ttk.Label(
            self.date_range_frame,
            text="To:",
            style="Custom.TLabel"
        ).pack(side=tk.LEFT, padx=5)
        
        self.to_date_var = tk.StringVar()
        self.to_date_entry = ttk.Entry(
            self.date_range_frame,
            textvariable=self.to_date_var,
            width=16
        )
        self.to_date_entry.pack(side=tk.LEFT, padx=2)
        
        # Apply range button
        ttk.Button(
            self.date_range_frame,
            text="Apply Range",
            command=self.apply_date_range,
            style="Custom.TButton"
        ).pack(side=tk.LEFT, padx=5)

        # Add calendar popup for date selection
        def show_calendar(self, entry_var):
            """Show calendar popup for date selection."""
            try:
                top = tk.Toplevel(self.window)
                top.title("Select Date")
                
                def set_date():
                    date = cal.selection_get()
                    entry_var.set(date.strftime("%Y-%m-%d %H:%M"))
                    top.destroy()
                
                cal = Calendar(
                    top,
                    selectmode='day',
                    year=datetime.now().year,
                    month=datetime.now().month,
                    day=datetime.now().day
                )
                cal.pack(padx=10, pady=10)
                
                ttk.Button(
                    top,
                    text="Select",
                    command=set_date
                ).pack(pady=5)
                
            except Exception as e:
                self.log_error(f"Error showing calendar: {str(e)}")

        def on_time_filter_change(self, event=None):
            """Handle time filter changes."""
            try:
                if self.time_filter_var.get() == "Custom Range":
                    # Show custom range inputs
                    self.date_range_frame.pack(fill=tk.X, pady=2)
                    # Set default date range (last 24 hours)
                    now = datetime.now()
                    self.to_date_var.set(now.strftime("%Y-%m-%d %H:%M"))
                    self.from_date_var.set(
                        (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
                    )
                else:
                    # Hide custom range inputs
                    self.date_range_frame.pack_forget()
                
                # Apply the filter
                self.apply_activity_filter()
                
            except Exception as e:
                self.log_error(f"Error changing time filter: {str(e)}")

        def apply_date_range(self):
            """Apply custom date range filter."""
            try:
                # Validate date formats
                try:
                    from_date = datetime.strptime(self.from_date_var.get(), "%Y-%m-%d %H:%M")
                    to_date = datetime.strptime(self.to_date_var.get(), "%Y-%m-%d %H:%M")
                except ValueError:
                    self.log_to_console(
                        "Invalid date format. Use YYYY-MM-DD HH:MM",
                        level="ERROR"
                    )
                    return
                
                # Validate date range
                if from_date > to_date:
                    self.log_to_console(
                        "Start date must be before end date",
                        level="ERROR"
                    )
                    return
                
                # Apply the filter
                self.apply_activity_filter()
                
            except Exception as e:
                self.log_error(f"Error applying date range: {str(e)}")

        # Add methods to the class
        MinimalGUI.show_calendar = show_calendar
        MinimalGUI.on_time_filter_change = on_time_filter_change
        MinimalGUI.apply_date_range = apply_date_range

        # Bind calendar popup to date entry fields
        self.from_date_entry.bind('<Double-Button-1>', lambda e: self.show_calendar(self.from_date_var))
        self.to_date_entry.bind('<Double-Button-1>', lambda e: self.show_calendar(self.to_date_var))

        # Search box with label
        ttk.Label(
            time_frame,
            text="Search:",
            style="Custom.TLabel"
        ).pack(side=tk.LEFT, padx=5)

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(
            time_frame,
            textvariable=self.search_var,
            width=15
        )
        search_entry.pack(side=tk.LEFT, padx=5)
        self.search_var.trace_add("write", lambda *args: self.apply_activity_filter())

        # Clear filters button
        ttk.Button(
            time_frame,
            text="Clear Filters",
            command=self.clear_activity_filters,
            style="Custom.TButton",
            width=12
        ).pack(side=tk.RIGHT, padx=5)

        # Activity status with custom style
        self.current_activity_var = tk.StringVar(value="System Ready...")
        current_activity_label = ttk.Label(
            activity_frame,
            textvariable=self.current_activity_var,
            style="Custom.TLabel",
            font=("Arial", 10, "bold")
        )
        current_activity_label.pack(fill=tk.X, pady=5)

        # Activity list with custom styling
        self.activity_text = tk.Text(
            activity_frame,
            height=6,  # Increased height for better visibility
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#f8f9fa",
            relief=tk.FLAT,
            padx=10,
            pady=5
        )
        self.activity_text.pack(fill=tk.BOTH, expand=True)

        # Add custom tags for different activity types
        # AI Core Activities
        self.activity_text.tag_configure("AI_THINKING", foreground="#9C27B0")    # Purple for thinking
        self.activity_text.tag_configure("AI_DECISION", foreground="#4CAF50")    # Green for decisions
        self.activity_text.tag_configure("AI_ANALYSIS", foreground="#FF9800")    # Orange for analysis
        self.activity_text.tag_configure("AI_GENERATION", foreground="#E91E63")  # Pink for text generation

        # Navigation & Interaction
        self.activity_text.tag_configure("NAVIGATION", foreground="#2196F3")     # Blue for navigation
        self.activity_text.tag_configure("CLICK", foreground="#03A9F4")          # Light blue for clicks
        self.activity_text.tag_configure("FORM_FILL", foreground="#00BCD4")      # Cyan for form filling
        self.activity_text.tag_configure("CAPTCHA", foreground="#F44336")        # Red for captcha events

        # Data Processing
        self.activity_text.tag_configure("CV_PARSE", foreground="#795548")       # Brown for CV parsing
        self.activity_text.tag_configure("DATA_ANALYSIS", foreground="#607D8B")  # Blue grey for data analysis
        self.activity_text.tag_configure("JOB_MATCH", foreground="#8BC34A")      # Light green for job matching

        # System & Auth
        self.activity_text.tag_configure("AUTH", foreground="#FFC107")           # Amber for authentication
        self.activity_text.tag_configure("SYSTEM", foreground="#9E9E9E")         # Grey for system events
        self.activity_text.tag_configure("ERROR", foreground="#FF5252")          # Red for errors
        self.activity_text.tag_configure("TIMESTAMP", foreground="#666666")      # Dark grey for timestamps

        # Agent Coordination
        self.activity_text.tag_configure("AGENT_HANDOFF", foreground="#673AB7")  # Deep purple for agent handoffs
        self.activity_text.tag_configure("DELEGATION", foreground="#3F51B5")     # Indigo for delegations

        # Enhanced console text widget
        self.console_text = tk.Text(
            console_frame,
            height=10,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#f8f9fa",
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.console_text.pack(fill=tk.BOTH, expand=True)

        # Add custom tags for log levels with colors
        self.console_text.tag_configure("INFO", foreground="#0078D4")
        self.console_text.tag_configure("WARNING", foreground="#ffc107")
        self.console_text.tag_configure("ERROR", foreground="#dc3545")

        # Add the activity tracking methods
        def update_ai_activity(self, activity_type: str, message: str, agent_name: str = None):
            """Update the activity monitor with the latest activity."""
            try:
                timestamp = datetime.now().strftime("%H:%M:%S")
                agent_prefix = f"[{agent_name}] " if agent_name else ""
                
                # Store the new activity in the full content
                if not hasattr(self, '_activity_content'):
                    self._activity_content = ""
                
                new_line = f"[{timestamp}] {agent_prefix}{message}\n"
                self._activity_content += new_line
                
                # Update current activity
                self.current_activity_var.set(f"Current: {agent_prefix}{message}")
                
                # Add to activity history with appropriate tag
                self.activity_text.config(state=tk.NORMAL)
                self.activity_text.insert(tk.END, f"[{timestamp}] ", "TIMESTAMP")
                self.activity_text.insert(tk.END, f"{agent_prefix}{message}\n", activity_type)
                self.activity_text.see(tk.END)
                self.activity_text.config(state=tk.DISABLED)
                
                # Keep only last 200 lines
                lines = self._activity_content.splitlines()
                if len(lines) > 200:
                    self._activity_content = "\n".join(lines[-200:]) + "\n"
                    
            except Exception as e:
                self.log_error(f"Error updating activity: {str(e)}")

        # Core AI Activities
        async def on_ai_thinking(self, message: str, agent_name: str = None):
            """Called when AI is thinking/processing."""
            self.update_ai_activity("AI_THINKING", f"🤔 {message}", agent_name)

        async def on_ai_decision(self, message: str, agent_name: str = None):
            """Called when AI makes a decision."""
            self.update_ai_activity("AI_DECISION", f"✅ {message}", agent_name)

        async def on_ai_analysis(self, message: str, agent_name: str = None):
            """Called when AI is analyzing something."""
            self.update_ai_activity("AI_ANALYSIS", f"🔍 {message}", agent_name)

        async def on_ai_generation(self, message: str, agent_name: str = None):
            """Called when AI is generating text/content."""
            self.update_ai_activity("AI_GENERATION", f"✨ {message}", agent_name)

        # Navigation & Interaction
        async def on_navigation(self, message: str, agent_name: str = None):
            """Called when navigating to a new page."""
            self.update_ai_activity("NAVIGATION", f"🌐 {message}", agent_name)

        async def on_click(self, message: str, agent_name: str = None):
            """Called when clicking elements."""
            self.update_ai_activity("CLICK", f"👆 {message}", agent_name)

        async def on_form_fill(self, message: str, agent_name: str = None):
            """Called when filling forms."""
            self.update_ai_activity("FORM_FILL", f"📝 {message}", agent_name)

        async def on_captcha(self, message: str, agent_name: str = None):
            """Called during captcha handling."""
            self.update_ai_activity("CAPTCHA", f"🔒 {message}", agent_name)

        # Data Processing
        async def on_cv_parse(self, message: str, agent_name: str = None):
            """Called during CV parsing."""
            self.update_ai_activity("CV_PARSE", f"📄 {message}", agent_name)

        async def on_data_analysis(self, message: str, agent_name: str = None):
            """Called during data analysis."""
            self.update_ai_activity("DATA_ANALYSIS", f"📊 {message}", agent_name)

        async def on_job_match(self, message: str, agent_name: str = None):
            """Called during job matching."""
            self.update_ai_activity("JOB_MATCH", f"🎯 {message}", agent_name)

        # System & Auth
        async def on_auth(self, message: str, agent_name: str = None):
            """Called during authentication events."""
            self.update_ai_activity("AUTH", f"🔑 {message}", agent_name)

        async def on_system(self, message: str, agent_name: str = None):
            """Called for system events."""
            self.update_ai_activity("SYSTEM", f"⚙️ {message}", agent_name)

        # Agent Coordination
        async def on_agent_handoff(self, message: str, from_agent: str, to_agent: str):
            """Called when one agent hands off to another."""
            self.update_ai_activity("AGENT_HANDOFF", f"🔄 {message}", f"{from_agent}➜{to_agent}")

        async def on_delegation(self, message: str, from_agent: str, to_agent: str):
            """Called when tasks are delegated between agents."""
            self.update_ai_activity("DELEGATION", f"📤 {message}", f"{from_agent}➜{to_agent}")

        # Add all methods to the class
        MinimalGUI.update_ai_activity = update_ai_activity
        MinimalGUI.on_ai_thinking = on_ai_thinking
        MinimalGUI.on_ai_decision = on_ai_decision
        MinimalGUI.on_ai_analysis = on_ai_analysis
        MinimalGUI.on_ai_generation = on_ai_generation
        MinimalGUI.on_navigation = on_navigation
        MinimalGUI.on_click = on_click
        MinimalGUI.on_form_fill = on_form_fill
        MinimalGUI.on_captcha = on_captcha
        MinimalGUI.on_cv_parse = on_cv_parse
        MinimalGUI.on_data_analysis = on_data_analysis
        MinimalGUI.on_job_match = on_job_match
        MinimalGUI.on_auth = on_auth
        MinimalGUI.on_system = on_system
        MinimalGUI.on_agent_handoff = on_agent_handoff
        MinimalGUI.on_delegation = on_delegation

        # ---------- SETTINGS / OPTIONS TAB ----------
        self.settings_tab = ttk.Frame(self.notebook, padding="20")
        self.settings_tab.configure(style="Custom.TFrame")
        self.notebook.add(self.settings_tab, text="Settings")

        # ---------- STATISTICS TAB ----------
        self.stats_tab = ttk.Frame(self.notebook, padding="20")
        self.stats_tab.configure(style="Custom.TFrame")
        self.notebook.add(self.stats_tab, text="Statistics")

        # Statistics title
        stats_title = ttk.Label(
            self.stats_tab,
            text="Automation Statistics",
            style="Title.TLabel"
        )
        stats_title.pack(pady=10)

        # Create main stats container
        stats_container = ttk.Frame(self.stats_tab)
        stats_container.pack(fill=tk.BOTH, expand=True, padx=10)

        # Job Statistics section
        job_stats_frame = ttk.LabelFrame(
            stats_container,
            text="Job Application Statistics",
            padding="15",
            style="Custom.TLabelframe"
        )
        job_stats_frame.pack(fill=tk.X, pady=10)

        # Create grid for job statistics
        self.jobs_viewed_var = tk.StringVar(value="0")
        self.jobs_matched_var = tk.StringVar(value="0")
        self.jobs_applied_var = tk.StringVar(value="0")
        self.jobs_failed_var = tk.StringVar(value="0")

        stats_grid = [
            ("Jobs Viewed", self.jobs_viewed_var, "🔍"),
            ("Jobs Matched", self.jobs_matched_var, "✅"),
            ("Applications Submitted", self.jobs_applied_var, "📤"),
            ("Failed Attempts", self.jobs_failed_var, "❌")
        ]

        for i, (label, var, icon) in enumerate(stats_grid):
            row = i // 2
            col = i % 2
            
            stat_frame = ttk.Frame(job_stats_frame)
            stat_frame.grid(row=row, column=col, padx=10, pady=5, sticky="ew")
            
            ttk.Label(
                stat_frame,
                text=f"{icon} {label}:",
                style="Custom.TLabel"
            ).pack(side=tk.LEFT)
            
            ttk.Label(
                stat_frame,
                textvariable=var,
                font=("Arial", 12, "bold"),
                foreground="#0078D4"
            ).pack(side=tk.LEFT, padx=5)

        # Configure grid columns
        job_stats_frame.columnconfigure(0, weight=1)
        job_stats_frame.columnconfigure(1, weight=1)

        # Success Rate section
        success_frame = ttk.LabelFrame(
            stats_container,
            text="Success Metrics",
            padding="15",
            style="Custom.TLabelframe"
        )
        success_frame.pack(fill=tk.X, pady=10)

        # Success rate progress bar
        self.success_rate_var = tk.StringVar(value="0%")
        success_label = ttk.Label(
            success_frame,
            text="Success Rate:",
            style="Custom.TLabel"
        )
        success_label.pack(side=tk.LEFT, padx=5)

        self.success_progress = ttk.Progressbar(
            success_frame,
            length=200,
            mode='determinate',
            value=0
        )
        self.success_progress.pack(side=tk.LEFT, padx=5)

        success_value = ttk.Label(
            success_frame,
            textvariable=self.success_rate_var,
            font=("Arial", 10, "bold")
        )
        success_value.pack(side=tk.LEFT, padx=5)

        # Session Statistics section
        session_stats_frame = ttk.LabelFrame(
            stats_container,
            text="Session Information",
            padding="15",
            style="Custom.TLabelframe"
        )
        session_stats_frame.pack(fill=tk.X, pady=10)

        # Session statistics variables
        self.total_runtime_var = tk.StringVar(value="Total Runtime: 00:00:00")
        self.avg_time_per_app_var = tk.StringVar(value="Avg. Time per Application: 00:00")
        self.last_activity_var = tk.StringVar(value="Last Activity: None")
        self.success_rate_today_var = tk.StringVar(value="Today's Success Rate: 0%")
        self.total_jobs_today_var = tk.StringVar(value="Jobs Today: 0")
        self.avg_match_score_var = tk.StringVar(value="Avg. Match Score: 0%")

        session_stats = [
            (self.total_runtime_var, "⏱"),
            (self.avg_time_per_app_var, "⌛"),
            (self.last_activity_var, "📝"),
            (self.success_rate_today_var, "📈"),
            (self.total_jobs_today_var, "📊"),
            (self.avg_match_score_var, "🎯")
        ]

        for var, icon in session_stats:
            stat_label = ttk.Label(
                session_stats_frame,
                textvariable=var,
                style="Custom.TLabel"
            )
            stat_label.pack(fill=tk.X, padx=5, pady=2)
            stat_label.configure(text=f"{icon} {var.get()}")

        # Add export and refresh buttons frame
        button_frame = ttk.Frame(stats_container)
        button_frame.pack(fill=tk.X, pady=15)

        # Export button
        export_button = ttk.Button(
            button_frame,
            text="📊 Export Statistics",
            command=self.export_statistics,
            style="Custom.TButton"
        )
        export_button.pack(side=tk.LEFT, padx=5)

        # Refresh button
        refresh_button = ttk.Button(
            button_frame,
            text="🔄 Refresh Statistics",
            command=self.refresh_statistics,
            style="Custom.TButton"
        )
        refresh_button.pack(side=tk.LEFT, padx=5)

        # Add detailed stats section
        detailed_stats_frame = ttk.LabelFrame(
            stats_container,
            text="Detailed Statistics",
            padding="15",
            style="Custom.TLabelframe"
        )
        detailed_stats_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Create scrolled text widget for detailed stats
        self.detailed_stats_text = tk.Text(
            detailed_stats_frame,
            height=8,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#f8f9fa",
            relief=tk.FLAT
        )
        self.detailed_stats_text.pack(fill=tk.BOTH, expand=True)

        # Settings title with new style
        settings_title = ttk.Label(
            self.settings_tab,
            text="Automation Settings",
            style="Title.TLabel"
        )
        settings_title.pack(pady=10)

        # Create main settings container
        settings_container = ttk.Frame(self.settings_tab)
        settings_container.pack(fill=tk.BOTH, expand=True, padx=10)

        # Job Search Delay setting with enhanced style
        delay_frame = ttk.LabelFrame(
            settings_container,
            text="Job Search Delay",
            padding="15",
            style="Custom.TLabelframe"
        )
        delay_frame.pack(fill=tk.X, pady=10)

        delay_container = ttk.Frame(delay_frame)
        delay_container.pack(fill=tk.X, padx=5)

        self.delay_var = tk.StringVar(value="2")
        delay_spinbox = ttk.Spinbox(
            delay_container,
            from_=1,
            to=10,
            textvariable=self.delay_var,
            width=5,
            font=("Arial", 10)
        )
        delay_spinbox.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(
            delay_container,
            text="seconds between job searches",
            style="Custom.TLabel"
        ).pack(side=tk.LEFT, padx=5)

        # Auto-Pause setting with enhanced style
        pause_frame = ttk.LabelFrame(
            settings_container,
            text="Auto-Pause After Hours",
            padding="15",
            style="Custom.TLabelframe"
        )
        pause_frame.pack(fill=tk.X, pady=10)

        pause_container = ttk.Frame(pause_frame)
        pause_container.pack(fill=tk.X, padx=5)

        self.auto_pause_var = tk.StringVar(value="4")
        pause_spinbox = ttk.Spinbox(
            pause_container,
            from_=1,
            to=24,
            textvariable=self.auto_pause_var,
            width=5,
            font=("Arial", 10)
        )
        pause_spinbox.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(
            pause_container,
            text="hours of continuous running",
            style="Custom.TLabel"
        ).pack(side=tk.LEFT, padx=5)

        # Save button with custom style
        self.save_settings_button = ttk.Button(
            settings_container,
            text="💾 Save Settings",
            command=self.save_settings,
            style="Custom.TButton"
        )
        self.save_settings_button.pack(pady=15)

        # Separator with padding
        ttk.Separator(settings_container, orient='horizontal').pack(fill='x', pady=20)

        # CV Upload section with enhanced styling
        cv_frame = ttk.LabelFrame(
            settings_container,
            text="CV/Resume Upload",
            padding="15",
            style="Custom.TLabelframe"
        )
        cv_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # CV status with custom style
        self.cv_status_var = tk.StringVar(value="No CV uploaded")
        cv_status_label = ttk.Label(
            cv_frame,
            textvariable=self.cv_status_var,
            style="Custom.TLabel",
            wraplength=350
        )
        cv_status_label.pack(fill=tk.X, pady=5)

        # Button frame for upload and remove
        cv_button_frame = ttk.Frame(cv_frame)
        cv_button_frame.pack(fill=tk.X, pady=10)

        # CV upload button with custom style
        self.cv_upload_button = ttk.Button(
            cv_button_frame,
            text="📄 Select CV File",
            command=self.select_cv_file,
            style="Custom.TButton"
        )
        self.cv_upload_button.pack(side=tk.LEFT, padx=5)

        # CV remove button with danger style
        self.cv_remove_button = ttk.Button(
            cv_button_frame,
            text="🗑 Remove CV",
            command=self.remove_cv_file,
            state=tk.DISABLED,
            style="Danger.TButton"
        )
        self.cv_remove_button.pack(side=tk.LEFT, padx=5)

        # CV preview area with enhanced styling
        preview_frame = ttk.LabelFrame(
            cv_frame,
            text="Preview",
            padding="10",
            style="Custom.TLabelframe"
        )
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        preview_container = ttk.Frame(preview_frame)
        preview_container.pack(fill=tk.BOTH, expand=True)

        self.cv_preview_text = tk.Text(
            preview_container,
            height=8,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#f8f9fa",
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.cv_preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar with custom style
        preview_scrollbar = ttk.Scrollbar(
            preview_container,
            orient=tk.VERTICAL,
            command=self.cv_preview_text.yview
        )
        preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.cv_preview_text.config(yscrollcommand=preview_scrollbar.set)

        # Format info with custom style
        cv_info = ttk.Label(
            cv_frame,
            text="Supported formats: PDF, DOCX, TXT\nMax file size: 5MB",
            style="Custom.TLabel",
            foreground="#666666"
        )
        cv_info.pack(pady=5)

        # ---------- CHAT TAB ----------
        self.chat_tab = ttk.Frame(self.notebook, padding="20")
        self.chat_tab.configure(style="Custom.TFrame")
        self.notebook.add(self.chat_tab, text="💬 Chat")

        # Create main chat container with weight configuration
        chat_container = ttk.Frame(self.chat_tab)
        chat_container.pack(fill=tk.BOTH, expand=True)
        chat_container.grid_columnconfigure(0, weight=1)
        chat_container.grid_rowconfigure(1, weight=1)

        # Header frame with AI model info
        header_frame = ttk.Frame(chat_container)
        header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        header_frame.grid_columnconfigure(1, weight=1)

        # AI Assistant icon and title
        ttk.Label(
            header_frame,
            text="🤖",
            font=("Arial", 16)
        ).grid(row=0, column=0, padx=(0, 5))

        ttk.Label(
            header_frame,
            text="AI Assistant",
            style="Title.TLabel"
        ).grid(row=0, column=1, sticky="w")

        # AI Model info
        self.model_info_var = tk.StringVar(value="Model: Loading...")
        ttk.Label(
            header_frame,
            textvariable=self.model_info_var,
            style="Subtitle.TLabel"
        ).grid(row=1, column=1, sticky="w")

        # Chat history frame with dynamic resizing
        chat_history_frame = ttk.Frame(chat_container)
        chat_history_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        chat_history_frame.grid_columnconfigure(0, weight=1)
        chat_history_frame.grid_rowconfigure(0, weight=1)

        # Chat history text widget with improved styling
        self.chat_history = tk.Text(
            chat_history_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=10,
            spacing3=5,  # Add spacing between messages
            cursor="arrow"
        )
        self.chat_history.grid(row=0, column=0, sticky="nsew")

        # Scrollbar with modern styling
        chat_scrollbar = ttk.Scrollbar(
            chat_history_frame,
            orient=tk.VERTICAL,
            command=self.chat_history.yview
        )
        chat_scrollbar.grid(row=0, column=1, sticky="ns")
        self.chat_history.config(yscrollcommand=chat_scrollbar.set)

        # Input frame with modern design
        input_frame = ttk.Frame(chat_container)
        input_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        input_frame.grid_columnconfigure(0, weight=1)

        # Modern input field
        self.chat_input = ttk.Entry(
            input_frame,
            font=("Segoe UI", 10),
            style="Chat.TEntry"
        )
        self.chat_input.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.chat_input.bind("<Return>", self.send_message)

        # Send button with icon
        send_button = ttk.Button(
            input_frame,
            text="Send ➤",
            command=lambda: self.send_message(None),
            style="Chat.TButton"
        )
        send_button.grid(row=0, column=1)

        # Configure chat message tags with modern styling
        self.chat_history.tag_configure(
            "user",
            foreground="#0078D4",
            font=("Segoe UI", 10, "bold"),
            spacing1=10,
            spacing3=5
        )
        self.chat_history.tag_configure(
            "assistant",
            foreground="#444444",
            font=("Segoe UI", 10),
            spacing1=5,
            spacing3=10,
            lmargin1=20
        )
        self.chat_history.tag_configure(
            "timestamp",
            foreground="#666666",
            font=("Segoe UI", 8),
            spacing1=2
        )
        self.chat_history.tag_configure(
            "error",
            foreground="#dc3545",
            font=("Segoe UI", 10, "italic")
        )
        self.chat_history.config(state=tk.DISABLED)

        # Add chat-specific styles
        style.configure(
            "Chat.TEntry",
            padding=10,
            relief=tk.FLAT,
            borderwidth=1
        )
        style.configure(
            "Chat.TButton",
            padding=10,
            font=("Segoe UI", 10),
            background="#0078D4",
            foreground="white"
        )

    async def start_automation(self):
        """Start the automation process."""
        await self._track_telemetry("click", {"action": "Start Automation"})
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
        await self._track_telemetry("click", {"action": "Pause"})
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
        await self._track_telemetry("click", {"action": "Stop"})
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

    def log_to_console(self, message: str, level: str = "INFO"):
        """Append a line to the mini console area with timestamp and log level."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_colors = {
            "INFO": "black",
            "WARNING": "orange",
            "ERROR": "red"
        }
        
        try:
            self.console_text.tag_configure(level, foreground=level_colors.get(level, "black"))
            self.console_text.insert(tk.END, f"[{timestamp}] {level}: {message}\n", level)
            self.console_text.see(tk.END)  # auto-scroll to bottom
            
            # Update extension status if it's an error
            if level == "ERROR":
                self._update_extension_status()
        except Exception as e:
            print(f"Failed to log to console: {e}")
            print(f"Original message: [{timestamp}] {level}: {message}")

    def log_error(self, message: str):
        """Log errors in console and in status.json with rate limiting."""
        # Rate limit error logging
        now = datetime.now()
        if (self.last_error_time and 
            (now - self.last_error_time).total_seconds() < 5 and 
            self.error_count > 10):
            # Too many errors too quickly, suppress
            return
            
        self.last_error_time = now
        self.error_count += 1
        
        # Log to console
        self.log_to_console(message, level="ERROR")
        
        # Update error log file
        try:
            # Read existing data
            data = {}
            if self.extension_status_file.exists():
                with open(self.extension_status_file, 'r') as f:
                    data = json.load(f)

            # Update errors list
            if "errors" not in data:
                data["errors"] = []
            
            # Add error with timestamp
            error_entry = {
                "timestamp": datetime.now().isoformat(),
                "message": message
            }
            data["errors"].append(error_entry)
            
            # Keep only last 100 errors
            data["errors"] = data["errors"][-100:]

            # Ensure directory exists
            self.extension_status_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write updated data
            with open(self.extension_status_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"Failed to write error to status file: {e}")
            self.log_to_console(
                f"Failed to write error to status file: {e}", 
                level="WARNING"
            )

    def _update_extension_status(self):
        """Update status.json for browser extension or debug usage with error handling."""
        try:
            # Get current status
            status = {
                "is_running": self.is_running,
                "is_paused": self.is_paused,
                "status": self.status_var.get(),
                "runtime": self.runtime_var.get(),
                "last_update": datetime.now().isoformat(),
                "errors": [],
                "metrics": {
                    "error_count": self.error_count,
                    "total_runtime": self._get_total_runtime()
                }
            }

            # Read existing data
            current_data = {}
            if self.extension_status_file.exists():
                try:
                    with open(self.extension_status_file, 'r') as f:
                        current_data = json.load(f)
                except json.JSONDecodeError:
                    self.log_to_console("Warning: Status file corrupted, creating new", level="WARNING")
                except Exception as e:
                    self.log_to_console(f"Warning: Could not read status file: {e}", level="WARNING")

            # Preserve existing errors and merge new status
            if "errors" in current_data:
                status["errors"] = current_data["errors"]

            # Update with new status
            current_data.update(status)

            # Ensure directory exists
            self.extension_status_file.parent.mkdir(parents=True, exist_ok=True)

            # Write updated status
            with open(self.extension_status_file, 'w') as f:
                json.dump(current_data, f, indent=2)

        except Exception as e:
            self.log_to_console(f"Error writing extension status: {str(e)}", level="WARNING")

    def _get_total_runtime(self) -> float:
        """Calculate total runtime in seconds."""
        if not self.start_time:
            return 0.0
        
        if self.is_paused:
            return (self.pause_time - self.start_time).total_seconds()
        
        return (datetime.now() - self.start_time).total_seconds()

    def update_status_loop(self):
        """Update runtime, status, and statistics if running, every second."""
        try:
            if not hasattr(self, 'last_status_update'):
                self.last_status_update = datetime.now()

            current_time = datetime.now()
            
            # Check for auto-pause condition
            self.check_auto_pause()
            
            # Validate running state
            if self.is_running and self.start_time:
                if not self.is_paused:
                    runtime = current_time - self.start_time
                    hours, remainder = divmod(runtime.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    self.runtime_var.set(f"Runtime: {hours:02d}:{minutes:02d}:{seconds:02d}")
                    
                    # Update status file and refresh statistics every 5 seconds
                    if (current_time - self.last_status_update).total_seconds() >= 5:
                        self._update_extension_status()
                        self.refresh_statistics()
                        self.last_status_update = current_time
                        
                    # Track long-running sessions
                    if runtime.seconds > 0 and runtime.seconds % 3600 == 0:  # Every hour
                        self.run_coroutine_in_background(
                            self._track_telemetry("session_milestone", {
                                "runtime_hours": hours,
                                "is_paused": self.is_paused,
                                "total_runtime": self._get_total_runtime(),
                                "jobs_applied": self.get_statistics().get('jobs_applied', 0)
                            })
                        )

        except Exception as e:
            self.log_error(f"Error in status update: {str(e)}")
            # Attempt to reset status if there's an error
            try:
                self.runtime_var.set("Runtime: 00:00:00")
                self.last_status_update = current_time
            except Exception:
                pass  # Ignore secondary errors in recovery

        # Schedule next update with error check
        if not self.window.winfo_exists():
            return  # Stop updates if window is destroyed
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

    async def on_button_click(self, button_name):
        await self._track_telemetry("click", {"action": button_name})
        # ... existing code ...

    async def on_start_button_click(self):
        await self._track_telemetry("click", {"action": "start_button"})
        # ... existing code ...

    async def on_stop_button_click(self):
        await self._track_telemetry("click", {"action": "stop_button"})
        # ... existing code ...

    async def on_settings_change(self, setting_name, new_value):
        await self._track_telemetry("settings_change", {"setting": setting_name, "new_value": new_value})
        # ... existing code ...

    def save_settings(self):
        """Save current settings to file and update controller."""
        try:
            settings = {
                "job_search_delay": float(self.delay_var.get()),
                "auto_pause_hours": float(self.auto_pause_var.get()),
                "last_updated": datetime.now().isoformat()
            }
            
            # Ensure directory exists
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save to file
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            
            # Update controller settings
            self.controller.settings.update(settings)
            
            # Track settings change
            self.run_coroutine_in_background(
                self._track_telemetry("settings_updated", settings)
            )
            
            self.log_to_console("Settings saved successfully", level="INFO")
            
        except Exception as e:
            self.log_error(f"Failed to save settings: {str(e)}")

    def load_settings(self) -> dict:
        """Load settings from file or return defaults."""
        defaults = {
            "job_search_delay": 2.0,
            "auto_pause_hours": 4.0
        }
        
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    saved = json.load(f)
                defaults.update(saved)
                
                # Update UI if it exists
                if hasattr(self, 'delay_var'):
                    self.delay_var.set(str(defaults['job_search_delay']))
                if hasattr(self, 'auto_pause_var'):
                    self.auto_pause_var.set(str(defaults['auto_pause_hours']))
                    
        except Exception as e:
            self.log_to_console(f"Warning: Could not load settings: {e}", level="WARNING")
            
        return defaults

    def check_auto_pause(self):
        """Check if we should auto-pause based on runtime."""
        if self.is_running and not self.is_paused and self.start_time:
            runtime_hours = (datetime.now() - self.start_time).total_seconds() / 3600
            auto_pause_hours = float(self.auto_pause_var.get())
            
            if runtime_hours >= auto_pause_hours:
                self.log_to_console(
                    f"Auto-pausing after {auto_pause_hours} hours of runtime",
                    level="WARNING"
                )
                self.run_coroutine_in_background(self.pause_automation())

    def select_cv_file(self):
        """Handle CV file selection, validation, preview and parsing."""
        try:
            file_path = filedialog.askopenfilename(
                title="Select your CV/Resume",
                filetypes=[
                    ("PDF files", "*.pdf"),
                    ("Word documents", "*.docx"),
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ]
            )
            
            if not file_path:
                return  # User cancelled
                
            # Convert to Path object
            cv_path = Path(file_path)
            
            # Validate file
            if not self.validate_cv_file(cv_path):
                return
                
            # Store the CV path in the controller's settings
            self.controller.settings['cv_file_path'] = str(cv_path)
            
            # Update status and UI
            self.cv_status_var.set(f"CV loaded: {cv_path.name}")
            self.cv_remove_button.config(state=tk.NORMAL)
            self.log_to_console(f"CV file selected: {cv_path.name}", level="INFO")
            
            # Preview the CV content
            self.preview_cv_content(cv_path)
            
            # Automatically parse the CV
            self.run_coroutine_in_background(self.parse_cv_content(cv_path))
            
            # Track the event
            self.run_coroutine_in_background(
                self._track_telemetry("cv_uploaded", {
                    "filename": cv_path.name,
                    "format": cv_path.suffix.lower(),
                    "size_kb": round(cv_path.stat().st_size / 1024, 2)
                })
            )
            
            # Save settings to persist the CV path
            self.save_settings()
            
        except Exception as e:
            self.log_error(f"Error selecting CV file: {str(e)}")
            self.cv_status_var.set("Error loading CV file")

    def preview_cv_content(self, file_path: Path):
        """Show a preview of the CV content."""
        try:
            # Clear existing preview
            self.cv_preview_text.config(state=tk.NORMAL)
            self.cv_preview_text.delete(1.0, tk.END)
            
            # Read and display first 1000 characters
            preview_text = ""
            if file_path.suffix.lower() == '.pdf':
                # Use PyPDF2 for PDF preview
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    preview_text = reader.pages[0].extract_text()[:1000]
            else:
                # For other formats, read directly
                with open(file_path, 'r', encoding='utf-8') as f:
                    preview_text = f.read(1000)
            
            # Add preview text with ellipsis if truncated
            self.cv_preview_text.insert(tk.END, preview_text)
            if len(preview_text) == 1000:
                self.cv_preview_text.insert(tk.END, "...\n(Preview truncated)")
                
            self.cv_preview_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.log_error(f"Error previewing CV: {str(e)}")
            self.cv_preview_text.insert(tk.END, "Error loading preview")
            self.cv_preview_text.config(state=tk.DISABLED)

    async def parse_cv_content(self, file_path: Path):
        """Parse the CV content using CVParserAgent."""
        try:
            # Get CVParserAgent instance from controller
            if not hasattr(self.controller, 'cv_parser'):
                self.log_to_console("CV Parser not initialized", level="ERROR")
                return
                
            # Parse the CV
            self.log_to_console("Parsing CV content...", level="INFO")
            cv_data = await self.controller.cv_parser.parse_cv(file_path)
            
            if cv_data:
                self.log_to_console("CV parsed successfully", level="INFO")
                # Store parsed data in controller's settings
                self.controller.settings['parsed_cv_data'] = cv_data.dict()
                self.save_settings()
            else:
                self.log_to_console("No data extracted from CV", level="WARNING")
                
        except Exception as e:
            self.log_error(f"Error parsing CV: {str(e)}")

    def validate_cv_file(self, file_path: Path) -> bool:
        """Validate the selected CV file with enhanced checks."""
        try:
            # Check if file exists
            if not file_path.exists():
                self.log_to_console("Selected file does not exist", level="ERROR")
                return False
                
            # Check file size (5MB limit)
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if file_path.stat().st_size > max_size:
                self.log_to_console(
                    "File too large. Maximum size is 5MB",
                    level="ERROR"
                )
                return False
                
            # Check file format
            valid_formats = {'.pdf', '.docx', '.txt'}
            if file_path.suffix.lower() not in valid_formats:
                self.log_to_console(
                    f"Unsupported file format. Please use: {', '.join(valid_formats)}",
                    level="ERROR"
                )
                return False
                
            # Additional validation checks
            if file_path.stat().st_size == 0:
                self.log_to_console("File is empty", level="ERROR")
                return False
                
            # Check if file is readable
            try:
                file_path.open('rb').close()
            except Exception:
                self.log_to_console("File is not readable", level="ERROR")
                return False
                
            # For PDF files, check if it's a valid PDF
            if file_path.suffix.lower() == '.pdf':
                try:
                    with open(file_path, 'rb') as f:
                        PyPDF2.PdfReader(f)
                except Exception:
                    self.log_to_console("Invalid PDF file", level="ERROR")
                    return False
                    
            return True
            
        except Exception as e:
            self.log_error(f"Error validating CV file: {str(e)}")
            return False

    def remove_cv_file(self):
        """Handle CV file removal."""
        try:
            # Remove the CV file from the controller's settings
            self.controller.settings.pop('cv_file_path', None)
            
            # Update status
            self.cv_status_var.set("No CV uploaded")
            self.log_to_console("CV file removed", level="INFO")
            
            # Track the event
            self.run_coroutine_in_background(
                self._track_telemetry("cv_removed")
            )
            
            # Save settings to persist the change
            self.save_settings()
            
        except Exception as e:
            self.log_error(f"Error removing CV file: {str(e)}")
            self.cv_status_var.set("Error removing CV file")

    def apply_activity_filter(self, event=None):
        """Apply activity filter based on selected type, agent, time range and search term."""
        try:
            filter_type = self.filter_var.get()
            agent_filter = self.agent_filter_var.get()
            time_filter = self.time_filter_var.get()
            search_term = self.search_var.get().lower()
            
            # Store all content
            if not hasattr(self, '_activity_content'):
                self._activity_content = self.activity_text.get(1.0, tk.END)
            
            # Clear current content
            self.activity_text.config(state=tk.NORMAL)
            self.activity_text.delete(1.0, tk.END)
            
            # Get filter tags based on type
            filter_tags = {
                "ALL": ["AI_THINKING", "AI_DECISION", "AI_ANALYSIS", "AI_GENERATION",
                       "NAVIGATION", "CLICK", "FORM_FILL", "CAPTCHA",
                       "CV_PARSE", "DATA_ANALYSIS", "JOB_MATCH",
                       "AUTH", "SYSTEM", "ERROR",
                       "AGENT_HANDOFF", "DELEGATION"],
                "AI Core": ["AI_THINKING", "AI_DECISION", "AI_ANALYSIS", "AI_GENERATION"],
                "Navigation": ["NAVIGATION", "CLICK", "FORM_FILL", "CAPTCHA"],
                "Data": ["CV_PARSE", "DATA_ANALYSIS", "JOB_MATCH"],
                "System": ["AUTH", "SYSTEM", "ERROR"],
                "Agents": ["AGENT_HANDOFF", "DELEGATION"],
                "Errors Only": ["ERROR"],
                "Success Only": ["AI_DECISION", "JOB_MATCH"]
            }
            
            # Get relevant tags for the selected filter
            active_tags = filter_tags.get(filter_type, filter_tags["ALL"])
            
            # Calculate time threshold or range
            time_threshold = None
            date_range = None
            now = datetime.now()
            
            if time_filter != "ALL":
                if time_filter == "Last 5 min":
                    time_threshold = now - timedelta(minutes=5)
                elif time_filter == "Last 15 min":
                    time_threshold = now - timedelta(minutes=15)
                elif time_filter == "Last hour":
                    time_threshold = now - timedelta(hours=1)
                elif time_filter == "Today":
                    time_threshold = now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif time_filter == "Custom Range":
                    try:
                        from_date = datetime.strptime(self.from_date_var.get(), "%Y-%m-%d %H:%M")
                        to_date = datetime.strptime(self.to_date_var.get(), "%Y-%m-%d %H:%M")
                        date_range = (from_date, to_date)
                    except ValueError:
                        self.log_to_console("Invalid date format in range", level="WARNING")
            
            # Split content into lines and filter
            lines = self._activity_content.splitlines()
            filtered_lines = []
            
            for line in lines:
                # Skip empty lines
                if not line.strip():
                    continue
                    
                # Check timestamp if time filter is active
                if time_threshold or date_range:
                    try:
                        timestamp_str = line[1:9]  # Extract HH:MM:SS
                        date_str = now.strftime("%Y-%m-%d ")  # Use current date
                        timestamp = datetime.strptime(date_str + timestamp_str, "%Y-%m-%d %H:%M:%S")
                        
                        if date_range:
                            if not (date_range[0] <= timestamp <= date_range[1]):
                                continue
                        elif time_threshold and timestamp < time_threshold:
                            continue
                    except:
                        pass  # Skip time filtering if timestamp parsing fails
                
                # Check if line matches search term
                if search_term and search_term not in line.lower():
                    continue
                    
                # Check if line matches selected agent
                if agent_filter != "ALL":
                    if f"[{agent_filter}]" not in line:
                        continue
                    
                # Check if line matches selected type
                if filter_type != "ALL":
                    matches_type = False
                    for tag in active_tags:
                        if any(indicator in line for indicator in self._get_tag_indicators(tag)):
                            matches_type = True
                            break
                    if not matches_type:
                        continue
                        
                filtered_lines.append(line)
            
            # Reinsert filtered content with tags
            for line in filtered_lines:
                self._insert_line_with_tags(line)
                
            self.activity_text.config(state=tk.DISABLED)
            
            # Update filter status
            filter_count = len(filtered_lines)
            total_count = len([l for l in lines if l.strip()])
            self.log_to_console(
                f"Showing {filter_count} of {total_count} events",
                level="INFO"
            )
            
        except Exception as e:
            self.log_error(f"Error applying activity filter: {str(e)}")

    def _get_tag_indicators(self, tag: str) -> list:
        """Get text indicators for a specific tag."""
        if tag in ACTIVITY_TYPES:
            return [ACTIVITY_TYPES[tag]["icon"]]
        return []

    def _insert_line_with_tags(self, line: str):
        """Insert a line with appropriate tags based on content."""
        # First insert timestamp if present
        if line.startswith("["):
            timestamp_end = line.find("]") + 1
            if timestamp_end > 0:
                self.activity_text.insert(tk.END, line[:timestamp_end], "TIMESTAMP")
                line = line[timestamp_end:]
        
        # Check content against all tag indicators and insert with appropriate tag
        for tag in ["AI_THINKING", "AI_DECISION", "AI_ANALYSIS", "AI_GENERATION",
                   "NAVIGATION", "CLICK", "FORM_FILL", "CAPTCHA",
                   "CV_PARSE", "DATA_ANALYSIS", "JOB_MATCH",
                   "AUTH", "SYSTEM", "ERROR",
                   "AGENT_HANDOFF", "DELEGATION"]:
            indicators = self._get_tag_indicators(tag)
            for indicator in indicators:
                if indicator in line:
                    self.activity_text.insert(tk.END, line + "\n", tag)
                    return
        
        # If no specific tag found, insert without tag
        self.activity_text.insert(tk.END, line + "\n")

    def clear_activity_filters(self):
        """Clear all activity filters."""
        try:
            self.filter_var.set("ALL")
            self.agent_filter_var.set("ALL")
            self.time_filter_var.set("ALL")
            self.search_var.set("")
            
            # Restore original content if stored
            if hasattr(self, '_activity_content'):
                self.activity_text.config(state=tk.NORMAL)
                self.activity_text.delete(1.0, tk.END)
                
                # Reinsert all content with proper tags
                lines = self._activity_content.splitlines()
                for line in lines:
                    if line.strip():  # Skip empty lines
                        self._insert_line_with_tags(line)
                    
                self.activity_text.config(state=tk.DISABLED)
                
                # Update status
                total_count = len([l for l in lines if l.strip()])
                self.log_to_console(f"Showing all {total_count} events", level="INFO")
                
        except Exception as e:
            self.log_error(f"Error clearing activity filters: {str(e)}")

    def refresh_statistics(self):
        """Refresh statistics and update the UI."""
        try:
            # Get statistics from controller
            stats = self.controller.get_statistics()
            
            # Update job statistics
            self.jobs_viewed_var.set(str(stats.get('jobs_viewed', 0)))
            self.jobs_matched_var.set(str(stats.get('jobs_matched', 0)))
            self.jobs_applied_var.set(str(stats.get('jobs_applied', 0)))
            self.jobs_failed_var.set(str(stats.get('jobs_failed', 0)))
            
            # Calculate and update success rate
            total_attempts = stats.get('jobs_applied', 0) + stats.get('jobs_failed', 0)
            if total_attempts > 0:
                success_rate = (stats.get('jobs_applied', 0) / total_attempts) * 100
                self.success_rate_var.set(f"{success_rate:.1f}%")
                self.success_progress['value'] = success_rate
            else:
                self.success_rate_var.set("0%")
                self.success_progress['value'] = 0
            
            # Update session information
            if self.start_time:
                total_runtime = datetime.now() - self.start_time
                hours = total_runtime.seconds // 3600
                minutes = (total_runtime.seconds % 3600) // 60
                seconds = total_runtime.seconds % 60
                self.total_runtime_var.set(
                    f"⏱ Total Runtime: {hours:02d}:{minutes:02d}:{seconds:02d}"
                )
                
                # Calculate average time per application
                if stats.get('jobs_applied', 0) > 0:
                    avg_time = total_runtime.seconds / stats.get('jobs_applied', 1)
                    avg_minutes = int(avg_time // 60)
                    avg_seconds = int(avg_time % 60)
                    self.avg_time_per_app_var.set(
                        f"⌛ Avg. Time per Application: {avg_minutes:02d}:{avg_seconds:02d}"
                    )
            
            # Update last activity
            if hasattr(self, 'current_activity_var'):
                self.last_activity_var.set(
                    f"📝 Last Activity: {self.current_activity_var.get().replace('Current: ', '')}"
                )
            
            # Track refresh event
            self.run_coroutine_in_background(
                self._track_telemetry("stats_refreshed", {
                    "jobs_viewed": stats.get('jobs_viewed', 0),
                    "jobs_applied": stats.get('jobs_applied', 0),
                    "success_rate": float(self.success_rate_var.get().replace('%', ''))
                })
            )
            
        except Exception as e:
            self.log_error(f"Error refreshing statistics: {str(e)}")

    def update_statistics(self, event_type: str, data: dict = None):
        """Update statistics based on events."""
        try:
            if not hasattr(self, '_statistics'):
                self._statistics = {
                    'jobs_viewed': 0,
                    'jobs_matched': 0,
                    'jobs_applied': 0,
                    'jobs_failed': 0
                }
            
            # Update relevant statistics based on event type
            if event_type == "job_viewed":
                self._statistics['jobs_viewed'] += 1
            elif event_type == "job_matched":
                self._statistics['jobs_matched'] += 1
            elif event_type == "job_applied":
                self._statistics['jobs_applied'] += 1
            elif event_type == "job_failed":
                self._statistics['jobs_failed'] += 1
            
            # Refresh the statistics display
            self.refresh_statistics()
            
        except Exception as e:
            self.log_error(f"Error updating statistics: {str(e)}")

    def get_statistics(self) -> dict:
        """Get current statistics."""
        if not hasattr(self, '_statistics'):
            self._statistics = {
                'jobs_viewed': 0,
                'jobs_matched': 0,
                'jobs_applied': 0,
                'jobs_failed': 0
            }
        return self._statistics.copy()

    def export_statistics(self):
        """Export statistics to a CSV file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile=f"job_search_stats_{timestamp}.csv"
            )
            
            if not filename:
                return  # User cancelled
                
            stats = self.get_detailed_statistics()
            
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Metric", "Value"])  # Header
                
                # Write basic stats
                writer.writerow(["Jobs Viewed", stats['jobs_viewed']])
                writer.writerow(["Jobs Matched", stats['jobs_matched']])
                writer.writerow(["Applications Submitted", stats['jobs_applied']])
                writer.writerow(["Failed Attempts", stats['jobs_failed']])
                writer.writerow(["Success Rate", f"{stats['success_rate']}%"])
                writer.writerow(["Average Match Score", f"{stats['avg_match_score']}%"])
                
                # Write today's stats
                writer.writerow(["Jobs Today", stats['jobs_today']])
                writer.writerow(["Success Rate Today", f"{stats['success_rate_today']}%"])
                
                # Write timing stats
                writer.writerow(["Total Runtime", stats['total_runtime']])
                writer.writerow(["Average Time per Application", stats['avg_time_per_app']])
                
                # Write detailed stats
                writer.writerow([])  # Empty row for separation
                writer.writerow(["Detailed Statistics"])
                for category, value in stats['detailed_stats'].items():
                    writer.writerow([category, value])
            
            self.log_to_console(f"Statistics exported to {filename}", level="INFO")
            
        except Exception as e:
            self.log_error(f"Error exporting statistics: {str(e)}")

    def get_detailed_statistics(self) -> dict:
        """Get detailed statistics including daily and overall metrics."""
        try:
            stats = self.get_statistics()
            now = datetime.now()
            
            # Calculate daily stats
            if not hasattr(self, '_daily_stats'):
                self._daily_stats = {
                    'date': now.date(),
                    'jobs_viewed': 0,
                    'jobs_applied': 0,
                    'jobs_failed': 0
                }
            
            # Reset daily stats if it's a new day
            if self._daily_stats['date'] != now.date():
                self._daily_stats = {
                    'date': now.date(),
                    'jobs_viewed': 0,
                    'jobs_applied': 0,
                    'jobs_failed': 0
                }
            
            # Calculate success rates
            total_attempts = stats['jobs_applied'] + stats['jobs_failed']
            success_rate = (stats['jobs_applied'] / total_attempts * 100) if total_attempts > 0 else 0
            
            daily_attempts = self._daily_stats['jobs_applied'] + self._daily_stats['jobs_failed']
            daily_success_rate = (self._daily_stats['jobs_applied'] / daily_attempts * 100) if daily_attempts > 0 else 0
            
            # Get runtime information
            total_runtime = "00:00:00"
            avg_time_per_app = "00:00"
            if self.start_time:
                runtime = datetime.now() - self.start_time
                hours = runtime.seconds // 3600
                minutes = (runtime.seconds % 3600) // 60
                seconds = runtime.seconds % 60
                total_runtime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                
                if stats['jobs_applied'] > 0:
                    avg_seconds = runtime.seconds / stats['jobs_applied']
                    avg_minutes = int(avg_seconds // 60)
                    avg_seconds = int(avg_seconds % 60)
                    avg_time_per_app = f"{avg_minutes:02d}:{avg_seconds:02d}"
            
            return {
                'jobs_viewed': stats['jobs_viewed'],
                'jobs_matched': stats['jobs_matched'],
                'jobs_applied': stats['jobs_applied'],
                'jobs_failed': stats['jobs_failed'],
                'success_rate': round(success_rate, 1),
                'avg_match_score': round(stats.get('avg_match_score', 0), 1),
                'jobs_today': self._daily_stats['jobs_viewed'],
                'success_rate_today': round(daily_success_rate, 1),
                'total_runtime': total_runtime,
                'avg_time_per_app': avg_time_per_app,
                'detailed_stats': {
                    'Successful Applications Today': self._daily_stats['jobs_applied'],
                    'Failed Applications Today': self._daily_stats['jobs_failed'],
                    'Average Processing Time': avg_time_per_app,
                    'Session Start Time': self.start_time.strftime('%H:%M:%S') if self.start_time else 'Not Started',
                    'Total Pauses': getattr(self, 'pause_count', 0),
                    'Last Error': getattr(self, 'last_error_time', 'None'),
                    'Error Count': self.error_count
                }
            }
            
        except Exception as e:
            self.log_error(f"Error getting detailed statistics: {str(e)}")
            return {}

    def verify_components(self) -> dict:
        """Verify all GUI components are working properly."""
        status = {
            "components": {},
            "errors": []
        }
        
        try:
            # Verify main window
            status["components"]["main_window"] = {
                "exists": bool(self.window),
                "title": self.window.title(),
                "geometry": self.window.geometry()
            }
            
            # Verify tabs
            status["components"]["tabs"] = {
                "console_tab": bool(self.console_tab),
                "settings_tab": bool(self.settings_tab),
                "stats_tab": bool(self.stats_tab)
            }
            
            # Verify control buttons
            status["components"]["controls"] = {
                "start_button": {
                    "exists": bool(self.start_button),
                    "state": self.start_button.cget("state")
                },
                "pause_button": {
                    "exists": bool(self.pause_button),
                    "state": self.pause_button.cget("state")
                },
                "stop_button": {
                    "exists": bool(self.stop_button),
                    "state": self.stop_button.cget("state")
                }
            }
            
            # Verify activity monitor
            status["components"]["activity_monitor"] = {
                "text_widget": bool(self.activity_text),
                "filter_controls": {
                    "type_filter": bool(self.filter_var),
                    "agent_filter": bool(self.agent_filter_var),
                    "time_filter": bool(self.time_filter_var),
                    "search": bool(self.search_var)
                }
            }
            
            # Verify statistics
            status["components"]["statistics"] = {
                "jobs_viewed": bool(self.jobs_viewed_var),
                "jobs_matched": bool(self.jobs_matched_var),
                "jobs_applied": bool(self.jobs_applied_var),
                "jobs_failed": bool(self.jobs_failed_var),
                "success_rate": bool(self.success_rate_var),
                "progress_bar": bool(self.success_progress)
            }
            
            # Verify CV upload
            status["components"]["cv_upload"] = {
                "status_var": bool(self.cv_status_var),
                "upload_button": bool(self.cv_upload_button),
                "remove_button": bool(self.cv_remove_button),
                "preview": bool(self.cv_preview_text)
            }
            
            # Verify settings
            status["components"]["settings"] = {
                "delay_var": bool(self.delay_var),
                "auto_pause_var": bool(self.auto_pause_var),
                "save_button": bool(self.save_settings_button)
            }
            
            # Verify calendar functionality
            status["components"]["calendar"] = {
                "available": bool(Calendar),
                "date_range_frame": bool(self.date_range_frame),
                "from_date": bool(self.from_date_var),
                "to_date": bool(self.to_date_var)
            }
            
            # Test event handlers
            status["event_handlers"] = {
                "start_automation": bool(self.start_automation_command),
                "pause_automation": bool(self.pause_automation_command),
                "stop_automation": bool(self.stop_automation_command),
                "save_settings": bool(self.save_settings),
                "export_statistics": bool(self.export_statistics),
                "apply_filters": bool(self.apply_activity_filter)
            }
            
            # Test file operations
            status["file_operations"] = {
                "settings_file": self.settings_file.exists(),
                "status_file": self.extension_status_file.exists(),
                "settings_writable": os.access(self.settings_file.parent, os.W_OK),
                "status_writable": os.access(self.extension_status_file.parent, os.W_OK)
            }
            
            # Verify telemetry
            status["telemetry"] = {
                "initialized": bool(self.telemetry),
                "event_loop": bool(self.loop and self.loop.is_running())
            }
            
            # Log verification results
            self.log_to_console("Component verification completed", level="INFO")
            if not all(all(v.values()) for v in status["components"].values()):
                self.log_to_console("Some components failed verification", level="WARNING")
                
        except Exception as e:
            error_msg = f"Error during component verification: {str(e)}"
            status["errors"].append(error_msg)
            self.log_error(error_msg)
            
        return status

    def run_component_test(self):
        """Run a test of all major components."""
        try:
            # Test activity logging
            self.log_to_console("Testing activity logging...", level="INFO")
            for activity_type, config in ACTIVITY_TYPES.items():
                self.update_ai_activity(
                    activity_type,
                    f"Test {activity_type} with {config['icon']}",
                    "TestAgent"
                )
            
            # Test statistics
            self.log_to_console("Testing statistics...", level="INFO")
            test_stats = {
                'jobs_viewed': 10,
                'jobs_matched': 7,
                'jobs_applied': 5,
                'jobs_failed': 2
            }
            self._statistics = test_stats
            self.refresh_statistics()
            
            # Test filters
            self.log_to_console("Testing filters...", level="INFO")
            self.filter_var.set("AI Core")
            self.apply_activity_filter()
            self.filter_var.set("ALL")
            
            # Test date range
            self.log_to_console("Testing date range...", level="INFO")
            now = datetime.now()
            self.from_date_var.set((now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"))
            self.to_date_var.set(now.strftime("%Y-%m-%d %H:%M"))
            self.apply_date_range()
            
            # Verify all components
            status = self.verify_components()
            
            # Log results
            self.log_to_console("Component test completed", level="INFO")
            if status["errors"]:
                for error in status["errors"]:
                    self.log_to_console(error, level="ERROR")
            
            return status
            
        except Exception as e:
            self.log_error(f"Error during component test: {str(e)}")
            return {"error": str(e)}

    def send_message(self, event=None):
        """Handle sending a chat message."""
        try:
            message = self.chat_input.get().strip()
            if not message:
                return

            # Clear input
            self.chat_input.delete(0, tk.END)

            # Add message to chat history
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            self.chat_history.config(state=tk.NORMAL)
            self.chat_history.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_history.insert(tk.END, "You: ", "user")
            self.chat_history.insert(tk.END, f"{message}\n", "user")
            self.chat_history.see(tk.END)
            self.chat_history.config(state=tk.DISABLED)

            # Process message asynchronously
            self.run_coroutine_in_background(self.process_message(message))

        except Exception as e:
            self.log_error(f"Error sending message: {str(e)}")

    async def process_message(self, message: str):
        """Process a chat message and generate a response."""
        try:
            # Add loading indicator
            self.chat_history.config(state=tk.NORMAL)
            self.chat_history.insert(tk.END, "AI Assistant is thinking...\n", "assistant")
            self.chat_history.see(tk.END)
            self.chat_history.config(state=tk.DISABLED)

            # Get response from AI module through controller
            response = await self.controller.process_chat_message(message)

            # Update model info if available
            if hasattr(self.controller, 'ai_module'):
                model_info = self.controller.ai_module.get_model_info()
                self.model_info_var.set(f"Model: {model_info}")

            # Remove loading indicator and add response
            self.chat_history.config(state=tk.NORMAL)
            self.chat_history.delete("end-2c linestart", tk.END)  # Remove loading message
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.chat_history.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_history.insert(tk.END, "🤖 AI: ", "assistant")
            self.chat_history.insert(tk.END, f"{response}\n", "assistant")
            self.chat_history.see(tk.END)
            self.chat_history.config(state=tk.DISABLED)

            # Track chat interaction
            await self._track_telemetry("chat_interaction", {
                "message_length": len(message),
                "response_length": len(response),
                "model": getattr(self.controller.ai_module, 'model_name', 'unknown')
            })

        except Exception as e:
            self.log_error(f"Error processing message: {str(e)}")
            self.chat_history.config(state=tk.NORMAL)
            self.chat_history.delete("end-2c linestart", tk.END)
            self.chat_history.insert(tk.END, "❌ Error: Failed to process message\n", "error")
            self.chat_history.see(tk.END)
            self.chat_history.config(state=tk.DISABLED)

# Additional comment about possibly splitting the code into a ui/components/ folder
# if the GUI grows with multiple custom widgets or advanced config tabs.
