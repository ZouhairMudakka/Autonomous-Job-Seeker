"""
Platform Manager Component

This component provides a comprehensive interface for managing multiple job platforms,
including their configurations, credentials, and real-time status monitoring.

Features:
- Multi-platform support with dynamic platform switching
- Secure credential management with masked input
- Real-time status monitoring and health indicators
- Advanced configuration tabs for Performance and Integration settings
- Thread-safe updates for asynchronous platform operations
- Responsive layout with automatic widget management

Usage Example:
    root = tk.Tk()
    config = PlatformConfig(
        platform_id="linkedin",
        name="LinkedIn",
        credentials={
            "api_key": "your_api_key",
            "secret": "your_secret"
        },
        settings={
            "rate_limit": 100,
            "timeout": 30
        }
    )
    status = PlatformStatus(
        platform_id="linkedin",
        is_connected=True,
        health_status="good",
        last_sync=datetime.now(),
        error_count=0,
        performance_metrics={
            "response_time": 0.5,
            "success_rate": 0.98
        }
    )
    manager = PlatformManagerView(root)
    manager.pack(fill=tk.BOTH, expand=True)
    manager.add_platform(config)
    manager.update_platform_status(status)

Thread Safety Note:
    All UI updates should be performed on the main thread. Use the provided
    schedule_ui_update method for updates from async contexts or other threads.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from threading import Lock

# Platform-specific constants
PLATFORM_TYPES = {
    "LINKEDIN": {
        "id": "linkedin",
        "name": "LinkedIn",
        "icon": "🔗",
        "color": "#0077B5",
        "default_settings": {
            "rate_limit": 100,
            "timeout": 30,
            "auto_apply": True,
            "max_applications": 50,
            "daily_limit": 100
        }
    },
    "INDEED": {
        "id": "indeed",
        "name": "Indeed",
        "icon": "🔍",
        "color": "#2164F3",
        "default_settings": {
            "rate_limit": 60,
            "timeout": 20,
            "auto_apply": True,
            "max_applications": 30,
            "daily_limit": 50
        }
    }
}

# Platform health status colors
HEALTH_STATUS_COLORS = {
    "good": "#2ECC71",     # Green
    "warning": "#F1C40F",  # Yellow
    "error": "#E74C3C"     # Red
}

# Platform status indicators
STATUS_INDICATORS = {
    "connected": {
        "color": "#2ECC71",  # Green
        "text": "Connected"
    },
    "disconnected": {
        "color": "#E74C3C",  # Red
        "text": "Disconnected"
    },
    "connecting": {
        "color": "#F1C40F",  # Yellow
        "text": "Connecting..."
    }
}

@dataclass
class PlatformConfig:
    """Data structure for platform configuration information.
    
    Attributes:
        platform_id: Unique identifier for the platform
        name: Display name of the platform
        credentials: Dictionary of authentication credentials
        settings: Dictionary of platform-specific settings
    """
    platform_id: str
    name: str
    credentials: Dict[str, str]
    settings: Dict[str, Any]

@dataclass
class PlatformStatus:
    """Data structure for platform status information.
    
    Attributes:
        platform_id: Unique identifier for the platform
        is_connected: Whether the platform is currently connected
        health_status: Current health status (good, warning, error)
        last_sync: Timestamp of last successful synchronization
        error_count: Number of errors since last reset
        performance_metrics: Dictionary of performance-related metrics
    """
    platform_id: str
    is_connected: bool
    health_status: str
    last_sync: datetime
    error_count: int
    performance_metrics: Dict[str, float]

class PlatformManagerView(ttk.Frame):
    """A component for managing multiple job platforms and their configurations."""
    
    def __init__(self, parent, *args, **kwargs):
        """Initialize the PlatformManagerView.
        
        Args:
            parent: The parent widget
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
        """
        super().__init__(parent, *args, **kwargs)
        self._platforms: Dict[str, PlatformConfig] = {}
        self._status: Dict[str, PlatformStatus] = {}
        self._status_callbacks: List[Callable[[PlatformStatus], None]] = []
        self._update_lock = Lock()  # For thread-safe updates
        self._setup_ui()
        self._setup_bindings()

    def _setup_ui(self):
        """Initialize the UI components with improved layout and styling."""
        # Platform Selection Section
        selection_frame = ttk.LabelFrame(self, text="Platform Selection")
        selection_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Platform selection with icons
        platform_frame = ttk.Frame(selection_frame)
        platform_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.platform_var = tk.StringVar()
        self.platform_combo = ttk.Combobox(
            platform_frame,
            textvariable=self.platform_var,
            state="readonly",
            width=30
        )
        self.platform_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        # Platform icon display
        self.platform_icon = ttk.Label(
            platform_frame,
            text="⚙️",
            font=('TkDefaultFont', 12)
        )
        self.platform_icon.pack(side=tk.LEFT, padx=5)
        
        # Status Section with improved styling
        self.status_frame = ttk.LabelFrame(self, text="Platform Status")
        self.status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Connection status with icon
        self.connection_frame = ttk.Frame(self.status_frame)
        self.connection_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.status_canvas = tk.Canvas(
            self.connection_frame,
            width=16,
            height=16,
            highlightthickness=0,
            bg=self.status_frame.cget('background')
        )
        self.status_canvas.pack(side=tk.LEFT, padx=2)
        
        self.connection_label = ttk.Label(
            self.connection_frame,
            text=STATUS_INDICATORS["disconnected"]["text"]
        )
        self.connection_label.pack(side=tk.LEFT, padx=2)
        
        # Health status with color coding
        self.health_frame = ttk.Frame(self.status_frame)
        self.health_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.health_icon = ttk.Label(
            self.health_frame,
            text="💚",
            font=('TkDefaultFont', 10)
        )
        self.health_icon.pack(side=tk.LEFT, padx=2)
        
        self.health_label = ttk.Label(
            self.health_frame,
            text="Health: Good",
            foreground=HEALTH_STATUS_COLORS["good"]
        )
        self.health_label.pack(side=tk.LEFT, padx=2)
        
        # Last sync with icon
        self.sync_frame = ttk.Frame(self.status_frame)
        self.sync_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(
            self.sync_frame,
            text="🔄",
            font=('TkDefaultFont', 10)
        ).pack(side=tk.LEFT, padx=2)
        
        self.sync_label = ttk.Label(
            self.sync_frame,
            text="Last Sync: Never"
        )
        self.sync_label.pack(side=tk.LEFT, padx=2)
        
        # Error count with icon
        self.error_frame = ttk.Frame(self.status_frame)
        self.error_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.error_icon = ttk.Label(
            self.error_frame,
            text="⚠️",
            font=('TkDefaultFont', 10)
        )
        self.error_icon.pack(side=tk.LEFT, padx=2)
        
        self.error_label = ttk.Label(
            self.error_frame,
            text="Errors: 0"
        )
        self.error_label.pack(side=tk.LEFT, padx=2)
        
        # Settings Notebook with platform-specific styling
        self.settings_notebook = ttk.Notebook(self)
        self.settings_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Credentials Tab
        self.credentials_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.credentials_frame, text="Credentials")
        
        # Create scrollable frame for credentials
        self.credentials_canvas = tk.Canvas(self.credentials_frame)
        scrollbar = ttk.Scrollbar(
            self.credentials_frame,
            orient=tk.VERTICAL,
            command=self.credentials_canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.credentials_canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.credentials_canvas.configure(
                scrollregion=self.credentials_canvas.bbox("all")
            )
        )
        
        self.credentials_canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw"
        )
        self.credentials_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.credentials_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Performance Tab with metrics
        self.performance_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.performance_frame, text="Performance")
        
        # Create performance metrics display
        metrics_frame = ttk.Frame(self.performance_frame)
        metrics_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add metrics header
        ttk.Label(
            metrics_frame,
            text="Real-time Performance Metrics",
            font=('TkDefaultFont', 10, 'bold')
        ).pack(pady=(0, 10))
        
        # Create metrics display
        self.metrics_text = scrolledtext.ScrolledText(
            metrics_frame,
            height=10,
            wrap=tk.WORD,
            font=('TkDefaultFont', 9),
            state=tk.DISABLED
        )
        self.metrics_text.pack(fill=tk.BOTH, expand=True)
        
        # Integration Tab
        self.integration_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.integration_frame, text="Integration")
        
        # Create integration settings
        settings_container = ttk.LabelFrame(
            self.integration_frame,
            text="Integration Settings"
        )
        settings_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add platform-specific settings
        self.settings_frame = ttk.Frame(settings_container)
        self.settings_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Initialize platforms
        self.initialize_platforms()

    def _setup_bindings(self):
        """Set up event bindings for dynamic updates."""
        self.platform_combo.bind("<<ComboboxSelected>>", self._on_platform_selected)
        
        # Bind mouse wheel to credentials scrolling
        self.credentials_canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.credentials_canvas.yview_scroll(
                int(-1*(e.delta/120)), "units"
            )
        )

    def schedule_ui_update(self, update_func: Callable):
        """Schedule a UI update to run on the main thread.
        
        Args:
            update_func: The function to run on the main thread
        """
        self.after_idle(update_func)

    def add_platform(self, config: PlatformConfig):
        """Add or update a platform configuration.
        
        Args:
            config: The PlatformConfig instance to add/update
        """
        try:
            with self._update_lock:
                self._platforms[config.platform_id] = config
                self.schedule_ui_update(self._update_platform_list)
        except Exception as e:
            logging.error(f"Error adding platform configuration: {e}")

    def update_platform_status(self, status: PlatformStatus):
        """Update the status of a platform.
        
        Args:
            status: The PlatformStatus instance to update
        """
        try:
            with self._update_lock:
                self._status[status.platform_id] = status
                self.schedule_ui_update(
                    lambda: self._update_status_display(status.platform_id)
                )
                
                # Notify callbacks
                for callback in self._status_callbacks:
                    try:
                        callback(status)
                    except Exception as e:
                        logging.error(f"Error in status callback: {e}")
        except Exception as e:
            logging.error(f"Error updating platform status: {e}")

    def register_status_callback(self, callback: Callable[[PlatformStatus], None]):
        """Register a callback for platform status updates.
        
        Args:
            callback: Function to call when platform status changes
        """
        if callback not in self._status_callbacks:
            self._status_callbacks.append(callback)

    def _update_platform_list(self):
        """Update the platform selection dropdown."""
        platforms = list(self._platforms.values())
        self.platform_combo['values'] = [p.name for p in platforms]
        
        if platforms and not self.platform_var.get():
            self.platform_var.set(platforms[0].name)
            self._on_platform_selected(None)

    def _on_platform_selected(self, event):
        """Handle platform selection changes."""
        selected = self.platform_var.get()
        platform_id = next(
            (p.platform_id for p in self._platforms.values() if p.name == selected),
            None
        )
        
        if platform_id:
            self._update_settings_display(platform_id)
            self._update_status_display(platform_id)
            self._update_performance_display(platform_id)

    def _update_status_display(self, platform_id: str):
        """Update the status display for the selected platform.
        
        Args:
            platform_id: ID of the platform to display status for
        """
        status = self._status.get(platform_id)
        if not status:
            self._clear_status_display()
            return
        
        # Update platform icon
        self.platform_icon.config(text=self.get_platform_icon(platform_id))
        
        # Update connection status with color and icon
        self.status_canvas.delete("all")
        status_info = STATUS_INDICATORS["connected" if status.is_connected else "disconnected"]
        
        self.status_canvas.create_oval(
            2, 2, 14, 14,
            fill=status_info["color"],
            outline="#95A5A6"
        )
        
        self.connection_label.config(text=status_info["text"])
        
        # Update health status with icon
        health_icons = {
            "good": "💚",
            "warning": "💛",
            "error": "❤️"
        }
        self.health_icon.config(text=health_icons.get(status.health_status, "💔"))
        
        self.health_label.config(
            text=f"Health: {status.health_status.title()}",
            foreground=HEALTH_STATUS_COLORS[status.health_status]
        )
        
        # Update sync status
        self.sync_label.config(
            text=f"Last Sync: {status.last_sync.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Update error count with warning icon if needed
        self.error_icon.config(
            text="⚠️" if status.error_count > 0 else "✓"
        )
        
        self.error_label.config(
            text=f"Errors: {status.error_count}",
            foreground=HEALTH_STATUS_COLORS["error"] if status.error_count > 0 else "black"
        )

    def _update_settings_display(self, platform_id: str):
        """Update the settings display for the selected platform.
        
        Args:
            platform_id: ID of the platform to display settings for
        """
        config = self._platforms.get(platform_id)
        if not config:
            return
        
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        # Create credential fields
        self.credential_vars = {}  # Store variables for access
        row = 0
        
        for key, value in config.credentials.items():
            # Create label
            ttk.Label(
                self.scrollable_frame,
                text=f"{key.replace('_', ' ').title()}:"
            ).grid(row=row, column=0, padx=5, pady=2, sticky="e")
            
            # Create entry with show/hide toggle
            var = tk.StringVar(value=value)
            self.credential_vars[key] = var
            
            entry_frame = ttk.Frame(self.scrollable_frame)
            entry_frame.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
            
            entry = ttk.Entry(
                entry_frame,
                textvariable=var,
                show="*"
            )
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Add show/hide toggle button
            def toggle_show(entry=entry, show=[True]):  # Use list for mutable state
                show[0] = not show[0]
                entry.config(show="*" if show[0] else "")
            
            ttk.Button(
                entry_frame,
                text="👁",
                width=3,
                command=toggle_show
            ).pack(side=tk.RIGHT, padx=2)
            
            row += 1
        
        # Configure grid
        self.scrollable_frame.grid_columnconfigure(1, weight=1)

    def _update_performance_display(self, platform_id: str):
        """Update the performance metrics display.
        
        Args:
            platform_id: ID of the platform to display metrics for
        """
        status = self._status.get(platform_id)
        if not status:
            self.metrics_text.config(state=tk.NORMAL)
            self.metrics_text.delete('1.0', tk.END)
            self.metrics_text.insert('1.0', "No performance data available")
            self.metrics_text.config(state=tk.DISABLED)
            return
        
        self.metrics_text.config(state=tk.NORMAL)
        self.metrics_text.delete('1.0', tk.END)
        
        platform_color = self.get_platform_color(platform_id)
        platform_icon = self.get_platform_icon(platform_id)
        
        # Add header with platform info
        header = f"{platform_icon} {status.platform_id.title()} Performance Metrics\n"
        header += "=" * 40 + "\n\n"
        
        self.metrics_text.insert('1.0', header)
        
        # Add metrics with formatting
        for key, value in status.performance_metrics.items():
            metric_name = key.replace('_', ' ').title()
            if 'rate' in key.lower() or 'ratio' in key.lower():
                formatted_value = f"{value:.1%}"
            elif 'time' in key.lower():
                formatted_value = f"{value:.2f}s"
            else:
                formatted_value = f"{value:,.0f}"
            
            metric_line = f"{metric_name}: {formatted_value}\n"
            self.metrics_text.insert('end', metric_line)
        
        self.metrics_text.config(state=tk.DISABLED)

    def _clear_status_display(self):
        """Clear all status displays."""
        self.platform_icon.config(text="⚙️")
        self.status_canvas.delete("all")
        self.connection_label.config(text=STATUS_INDICATORS["disconnected"]["text"])
        self.health_icon.config(text="💔")
        self.health_label.config(text="Health: Unknown", foreground="black")
        self.sync_label.config(text="Last Sync: Never")
        self.error_icon.config(text="✓")
        self.error_label.config(text="Errors: 0", foreground="black")

    def clear(self):
        """Clear all platform data and reset the display."""
        try:
            with self._update_lock:
                self._platforms.clear()
                self._status.clear()
                self.schedule_ui_update(self._clear_all_displays)
        except Exception as e:
            logging.error(f"Error clearing platform manager: {e}")

    def _clear_all_displays(self):
        """Clear all display elements (internal)."""
        self.platform_combo.set('')
        self.platform_combo['values'] = []
        self._clear_status_display()
        
        # Clear credentials
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        # Clear performance metrics
        self.metrics_text.config(state=tk.NORMAL)
        self.metrics_text.delete('1.0', tk.END)
        self.metrics_text.config(state=tk.DISABLED)

    def initialize_platforms(self):
        """Initialize available platforms with default configurations."""
        try:
            for platform_type, config in PLATFORM_TYPES.items():
                platform_config = PlatformConfig(
                    platform_id=config["id"],
                    name=config["name"],
                    credentials={},  # Empty by default
                    settings=config["default_settings"].copy()
                )
                self.add_platform(platform_config)
                
                # Initialize status
                platform_status = PlatformStatus(
                    platform_id=config["id"],
                    is_connected=False,
                    health_status="good",
                    last_sync=datetime.now(),
                    error_count=0,
                    performance_metrics={
                        "response_time": 0.0,
                        "success_rate": 0.0,
                        "daily_applications": 0,
                        "total_applications": 0
                    }
                )
                self.update_platform_status(platform_status)
                
        except Exception as e:
            logging.error(f"Error initializing platforms: {e}")

    def get_current_platform(self) -> Optional[str]:
        """Get the currently selected platform ID."""
        selected = self.platform_var.get()
        return next(
            (p.platform_id for p in self._platforms.values() if p.name == selected),
            None
        )

    def get_platform_settings(self, platform_id: str) -> Dict[str, Any]:
        """Get settings for a specific platform."""
        try:
            platform = self._platforms.get(platform_id)
            if platform:
                return platform.settings.copy()
            return {}
        except Exception as e:
            logging.error(f"Error getting platform settings: {e}")
            return {}

    def update_platform_metrics(self, platform_id: str, metrics: Dict[str, float]):
        """Update performance metrics for a platform."""
        try:
            status = self._status.get(platform_id)
            if status:
                status.performance_metrics.update(metrics)
                self.update_platform_status(status)
        except Exception as e:
            logging.error(f"Error updating platform metrics: {e}")

    def increment_error_count(self, platform_id: str):
        """Increment the error count for a platform."""
        try:
            status = self._status.get(platform_id)
            if status:
                status.error_count += 1
                if status.error_count > 5:  # Threshold for health status
                    status.health_status = "warning"
                if status.error_count > 10:
                    status.health_status = "error"
                self.update_platform_status(status)
        except Exception as e:
            logging.error(f"Error incrementing error count: {e}")

    def reset_error_count(self, platform_id: str):
        """Reset the error count for a platform."""
        try:
            status = self._status.get(platform_id)
            if status:
                status.error_count = 0
                status.health_status = "good"
                self.update_platform_status(status)
        except Exception as e:
            logging.error(f"Error resetting error count: {e}")

    def set_platform_connection_status(self, platform_id: str, is_connected: bool):
        """Set the connection status for a platform."""
        try:
            status = self._status.get(platform_id)
            if status:
                status.is_connected = is_connected
                status.last_sync = datetime.now() if is_connected else status.last_sync
                self.update_platform_status(status)
        except Exception as e:
            logging.error(f"Error setting platform connection status: {e}")

    def get_platform_icon(self, platform_id: str) -> str:
        """Get the icon for a specific platform."""
        for platform_type in PLATFORM_TYPES.values():
            if platform_type["id"] == platform_id:
                return platform_type["icon"]
        return "⚙️"  # Default icon

    def get_platform_color(self, platform_id: str) -> str:
        """Get the brand color for a specific platform."""
        for platform_type in PLATFORM_TYPES.values():
            if platform_type["id"] == platform_id:
                return platform_type["color"]
        return "#9E9E9E"  # Default gray 