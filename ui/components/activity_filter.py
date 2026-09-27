"""
Activity Filter Component

This component provides a comprehensive interface for filtering activity logs,
including type filtering, agent filtering, time-based filtering, and search functionality.

Features:
- Multiple filter types (Navigation, Data, System, Agents, etc.)
- Agent-specific filtering
- Time-based filtering with custom ranges
- Search functionality
- Real-time filter updates
- Tag-based activity highlighting
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
import logging
from storage.privacy import redact_text

# Constants for activity types and their styling
ACTIVITY_TYPES = {
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

FILTER_TYPES = {
    'Navigation': {'NAVIGATION', 'CLICK'},
    'Data': {'FORM_FILL', 'CV_PARSE', 'DATA_ANALYSIS', 'JOB_MATCH'},
    'System': {'SYSTEM', 'AUTH', 'CAPTCHA'},
    'Agents': {'AGENT_HANDOFF', 'DELEGATION'},
    'Errors Only': {'ERROR'},
}

class ActivityFilterView(ttk.Frame):
    """A component for filtering and displaying activity logs."""

    def __init__(self, parent, *args, **kwargs):
        """Initialize the activity filter view.

        Args:
            parent: The parent widget
            *args: Additional positional arguments for ttk.Frame
            **kwargs: Additional keyword arguments for ttk.Frame
        """
        super().__init__(parent, *args, **kwargs)
        self._activity_content = ""
        self._setup_ui()
        self._setup_tags()

    def _setup_ui(self):
        """Initialize the UI components."""
        # Create filter controls frame
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        # Type filter
        ttk.Label(filter_frame, text="Type:").pack(side=tk.LEFT, padx=2)
        self.filter_var = tk.StringVar(value="ALL")
        type_filter = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_var,
            values=["ALL", "Navigation", "Data", "System", "Agents", "Errors Only", "Success Only"],
            state="readonly",
            width=15
        )
        type_filter.pack(side=tk.LEFT, padx=5)

        # Agent filter
        ttk.Label(filter_frame, text="Agent:").pack(side=tk.LEFT, padx=2)
        self.agent_filter_var = tk.StringVar(value="ALL")
        agent_filter = ttk.Combobox(
            filter_frame,
            textvariable=self.agent_filter_var,
            values=["ALL", "Browser", "CV", "Job", "Auth"],
            state="readonly",
            width=15
        )
        agent_filter.pack(side=tk.LEFT, padx=5)

        # Time filter
        ttk.Label(filter_frame, text="Time:").pack(side=tk.LEFT, padx=2)
        self.time_filter_var = tk.StringVar(value="ALL")
        time_filter = ttk.Combobox(
            filter_frame,
            textvariable=self.time_filter_var,
            values=["ALL", "Last 5 min", "Last 15 min", "Last hour", "Today", "Custom Range"],
            state="readonly",
            width=15
        )
        time_filter.pack(side=tk.LEFT, padx=5)

        # Search
        ttk.Label(filter_frame, text="Search:").pack(side=tk.LEFT, padx=2)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        range_frame = ttk.Frame(self)
        range_frame.pack(fill=tk.X, padx=5)
        self.from_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d 00:00'))
        self.to_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d %H:%M'))
        for label, variable in (('Range from', self.from_date_var), ('to', self.to_date_var)):
            ttk.Label(range_frame, text=label).pack(side=tk.LEFT)
            entry = ttk.Entry(range_frame, textvariable=variable, width=18)
            entry.pack(side=tk.LEFT, padx=5)
            entry.bind('<KeyRelease>', self._apply_filter)

        # Create activity text widget
        self.activity_text = scrolledtext.ScrolledText(self, wrap=tk.WORD, height=20)
        self.activity_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Bind filter changes
        type_filter.bind('<<ComboboxSelected>>', self._apply_filter)
        agent_filter.bind('<<ComboboxSelected>>', self._apply_filter)
        time_filter.bind('<<ComboboxSelected>>', self._apply_filter)
        search_entry.bind('<KeyRelease>', self._apply_filter)

    def _setup_tags(self):
        """Configure text tags for activity types."""
        # Configure timestamp tag
        self.activity_text.tag_configure("timestamp", foreground="#666666")

        # Configure tags for each activity type
        for activity_type, info in ACTIVITY_TYPES.items():
            self.activity_text.tag_configure(
                activity_type,
                foreground=info["color"],
                font=('TkDefaultFont', 10, 'bold')
            )

    def _apply_filter(self, event=None):
        """Apply activity filter based on selected type, agent, time range and search term."""
        try:
            filter_type = self.filter_var.get()
            agent_filter = self.agent_filter_var.get()
            time_filter = self.time_filter_var.get()
            search_term = self.search_var.get().lower()

            # Clear current content
            self.activity_text.config(state=tk.NORMAL)
            self.activity_text.delete(1.0, tk.END)

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
                        if from_date > to_date:
                            raise ValueError('Invalid date range')
                        date_range = (from_date, to_date)
                    except ValueError:
                        logging.error("Invalid date format in range")
                        self.activity_text.config(state=tk.DISABLED)
                        return

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
                        timestamp_str = line[1:line.index(']')]
                        if len(timestamp_str) == 8:  # Legacy entries recorded only a time.
                            timestamp_str = now.strftime('%Y-%m-%d ') + timestamp_str
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                        if date_range:
                            if not (date_range[0] <= timestamp <= date_range[1]):
                                continue
                        elif time_threshold and timestamp < time_threshold:
                            continue
                    except (ValueError, IndexError):
                        continue

                # Check if line matches search term
                if search_term and search_term not in line.lower():
                    continue

                # Check if line matches selected agent
                if agent_filter != "ALL":
                    if f"[{agent_filter}]" not in line:
                        continue

                allowed = FILTER_TYPES.get(filter_type)
                if allowed and not any(f'[{kind}]' in line or ACTIVITY_TYPES[kind]['icon'] in line for kind in allowed):
                    continue
                if filter_type == 'Success Only' and not any(marker in line.lower() for marker in ('[success]', 'success', '✅')):
                    continue

                # Add line to filtered content
                filtered_lines.append(line)

            # Reinsert filtered content with tags
            for line in filtered_lines:
                self._insert_line_with_tags(line)

            self.activity_text.config(state=tk.DISABLED)

        except Exception as e:
            logging.error(f"Error applying activity filter: {str(e)}")
            self.activity_text.config(state=tk.DISABLED)

    def _insert_line_with_tags(self, line: str):
        """Insert a line with appropriate tags based on content."""
        try:
            # First insert timestamp if present
            if line.startswith("["):
                timestamp_end = line.find("]") + 1
                if timestamp_end > 0:
                    self.activity_text.insert(tk.END, line[:timestamp_end], "timestamp")
                    line = line[timestamp_end:]

            # Check content against all activity types
            for activity_type, info in ACTIVITY_TYPES.items():
                if any(indicator in line for indicator in [info["icon"], f"[{activity_type}]"]):
                    self.activity_text.insert(tk.END, line + "\n", activity_type)
                    return

            # If no specific tag found, insert without tag
            self.activity_text.insert(tk.END, line + "\n")

        except Exception as e:
            logging.error(f"Error inserting line with tags: {str(e)}")

    def add_activity(self, message: str, activity_type: str = "SYSTEM"):
        """Add a new activity entry with timestamp and formatting."""
        try:
            timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
            formatted_message = f"{timestamp} [{activity_type}] {redact_text(message)}\n"

            # Store activity content
            self._activity_content += formatted_message

            # Update display
            self.activity_text.config(state=tk.NORMAL)
            self._insert_line_with_tags(formatted_message.strip())
            self.activity_text.see(tk.END)
            self.activity_text.config(state=tk.DISABLED)

            # Reapply current filter
            self._apply_filter()

        except Exception as e:
            logging.error(f"Error adding activity: {str(e)}")

    def clear(self):
        """Clear all activity content."""
        self._activity_content = ""
        self.activity_text.config(state=tk.NORMAL)
        self.activity_text.delete(1.0, tk.END)
        self.activity_text.config(state=tk.DISABLED)
