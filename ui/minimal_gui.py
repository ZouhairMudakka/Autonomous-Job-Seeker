"""
Minimal GUI Implementation for LinkedIn Automation Tool (Updated MVP)

This module provides a simple desktop GUI interface that:
1. Controls automation (start/stop/pause/resume)
2. Displays basic status (including a mini console for short updates/errors)
3. Writes to an extension status file (status.json) if desired
4. Uses tkinter for a lightweight interface with tab-based layout (console + settings)

REFACTORING NOTES:
-----------------
The following code will be moved to separate modules:

1. Async Event Loop Management -> async_manager/event_loop_manager.py:
   - _run_async_loop()
   - run_coroutine_in_background()
   - Related async setup/cleanup code

2. Performance Monitoring -> utils/performance_monitor.py:
   - PerformanceMonitor class
   - monitor_performance() function

3. Settings Management -> utils/settings_manager.py:
   - save_settings()
   - load_settings()
   - Related settings persistence code

4. CV File Handling -> utils/file_manager.py:
   - select_cv_file()
   - validate_cv_file()
   - preview_cv_content()
   - remove_cv_file()
   - Related CV file operations

5. Activity Filtering -> ui/components/activity_filter.py (future):
   - apply_activity_filter()
   - _insert_line_with_tags()
   - Related filtering logic

6. Job Processing View -> ui/components/job_processing.py (future):
   - Job card display
   - Queue visualization
   - Match score display

7. Analytics Dashboard -> ui/components/analytics.py (future):
   - Performance metrics
   - Success rate tracking
   - Trend visualization

The MinimalGUI class will be refactored to:
1. Focus on pure UI code and layout
2. Use dependency injection for services
3. Implement clean event handling
4. Remove duplicate code
5. Improve error handling

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

3. Profile Management:
   - Resume version control
   - Cover letter template management
   - Skill matrix editor
   - Experience highlighting tools
   - Profile optimization suggestions

These components would be implemented as separate classes in the ui/components/ folder:
    components/
    ├── job_processing.py      # JobProcessingView
    ├── ai_decision.py         # AIDecisionView
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
from tkinter import ttk, filedialog, scrolledtext
import json
from pathlib import Path
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import threading
from utils.telemetry import TelemetryManager
import PyPDF2
import csv
import sys
from ui.components.ai_decision import AIDecisionView, AIDecision
from ui.components.platform_manager import PlatformManagerView, PlatformConfig, PlatformStatus
from ui.components.activity_filter import ActivityFilterView, ACTIVITY_TYPES
try:
    from tkcalendar import Calendar
except ImportError:
    temp_logger = LogsManager({'system': {'data_dir': './data', 'log_level': 'INFO'}})
    asyncio.run(temp_logger.initialize())
    asyncio.run(temp_logger.warning("tkcalendar not installed. Calendar functionality will be limited."))
    Calendar = None
import os
from storage.logs_manager import LogsManager
import psutil
import time

# Constants for better maintainability
LOG_LEVELS = {
    "INFO": {"color": "#0078D4"},
    "WARNING": {"color": "#ffc107"},
    "ERROR": {"color": "#dc3545"}
}

class PerformanceMonitor:
    """Context manager for monitoring performance of operations."""
    def __init__(self, gui, operation: str):
        self.gui = gui
        self.operation = operation
        self.start_time = None
        self.start_memory = None
        
    async def __aenter__(self):
        """Start monitoring."""
        self.start_time = time.time()
        try:
            process = psutil.Process()
            self.start_memory = process.memory_info().rss
        except Exception:
            self.start_memory = None
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """End monitoring and log results."""
        try:
            end_time = time.time()
            duration = end_time - self.start_time
            
            performance_data = {
                "operation": self.operation,
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "duration": duration,
                "success": exc_type is None
            }
            
            # Add memory metrics if available
            if self.start_memory is not None:
                try:
                    process = psutil.Process()
                    end_memory = process.memory_info().rss
                    memory_delta = end_memory - self.start_memory
                    performance_data.update({
                        "memory_before": self.start_memory,
                        "memory_after": end_memory,
                        "memory_delta": memory_delta
                    })
                except Exception as e:
                    await self.gui.logs_manager.warning(f"Failed to get memory metrics: {e}")
            
            # Add error information if operation failed
            if exc_type is not None:
                performance_data.update({
                    "error_type": exc_type.__name__,
                    "error_message": str(exc_val)
                })
            
            # Log performance data
            await self.gui.logs_manager.info(
                f"Performance data: {json.dumps(performance_data, default=str)}"
            )
            
            # Track slow operations
            if duration > 1.0:  # More than 1 second
                await self.gui.logs_manager.warning(
                    f"Slow operation detected: {self.operation} took {duration:.2f} seconds"
                )
                
                # Track in telemetry
                await self.gui._track_telemetry("slow_operation", performance_data)
            
            # Track memory spikes
            if self.start_memory is not None and memory_delta > 50 * 1024 * 1024:  # 50MB
                await self.gui.logs_manager.warning(
                    f"High memory usage in operation: {self.operation} "
                    f"delta={memory_delta / 1024 / 1024:.1f}MB"
                )
                
                # Track in telemetry
                await self.gui._track_telemetry("high_memory_usage", performance_data)
            
        except Exception as e:
            await self.gui.logs_manager.error(
                f"Failed to log performance data: {str(e)}",
                context={
                    "operation": self.operation,
                    "duration": time.time() - self.start_time
                }
            )

async def monitor_performance(self, operation: str):
    """Get a performance monitoring context manager."""
    return PerformanceMonitor(self, operation)

class MinimalGUI:
    def __init__(self, controller):
        """Initialize MinimalGUI with controller reference."""
        try:
            print("[DEBUG] ========================================")
            print("[DEBUG] MinimalGUI.__init__ Pre-initialization Checks:")
            print("[DEBUG] 1. Environment Information:")
            print(f"[DEBUG] - Python version: {sys.version}")
            print(f"[DEBUG] - Python executable: {sys.executable}")
            print(f"[DEBUG] - Platform: {sys.platform}")
            print(f"[DEBUG] - Tkinter version: {tk.TkVersion}")
            print(f"[DEBUG] - Current working directory: {os.getcwd()}")
            print(f"[DEBUG] - Process ID: {os.getpid()}")
            
            print("\n[DEBUG] 2. Thread Information:")
            print(f"[DEBUG] - Current thread: {threading.current_thread().name}")
            print(f"[DEBUG] - Is main thread: {threading.current_thread() is threading.main_thread()}")
            print(f"[DEBUG] - Active thread count: {threading.active_count()}")
            
            print("\n[DEBUG] 3. Memory Usage:")
            process = psutil.Process(os.getpid())
            print(f"[DEBUG] - Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            
            print("\n[DEBUG] 4. Event Loop State:")
            try:
                current_loop = asyncio.get_event_loop()
                print(f"[DEBUG] - Current event loop: {current_loop}")
                print(f"[DEBUG] - Loop policy: {asyncio.get_event_loop_policy().__class__.__name__}")
                print(f"[DEBUG] - Loop is closed: {current_loop.is_closed()}")
                print(f"[DEBUG] - Loop is running: {current_loop.is_running()}")
            except Exception as e:
                print(f"[DEBUG] - Event loop check failed: {str(e)}")
            
            print("\n[DEBUG] 5. Controller Verification:")
            print(f"[DEBUG] - Controller type: {type(controller).__name__}")
            print(f"[DEBUG] - Has logs_manager: {hasattr(controller, 'logs_manager')}")
            print(f"[DEBUG] - Has telemetry: {hasattr(controller, 'telemetry')}")
            print("[DEBUG] ========================================")
            
            # Now proceed with actual initialization
            print("[DEBUG] Starting MinimalGUI initialization sequence...")
            
            # Store controller reference
            print("[DEBUG] Step 1: Storing controller reference...")
            self.controller = controller
            self.logs_manager = controller.logs_manager
            self.telemetry = controller.telemetry
            print("[DEBUG] Step 1: Complete - Controller references stored")
            
            # Create async event loop and thread
            print("[DEBUG] Step 2: Creating async event loop and thread...")
            self.async_loop = asyncio.new_event_loop()
            self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
            self.async_thread.start()
            print("[DEBUG] Step 2: Complete - Async infrastructure created")
            print(f"[DEBUG] - Async thread started: {self.async_thread.is_alive()}")
            print(f"[DEBUG] - Async loop running: {self.async_loop.is_running()}")
            
            # Now we can use logs_manager since async loop is ready
            future = asyncio.run_coroutine_threadsafe(
                self.logs_manager.info(">>> Async thread started successfully"),
                self.async_loop
            )
            future.result(timeout=5.0)
            print("[DEBUG] Step 2: Async logging test successful")
            
            # Initialize state
            print("[DEBUG] Step 3: Initializing state...")
            self.state = {
                "is_running": False,
                "is_paused": False,
                "start_time": None,
                "error_count": 0
            }
            print("[DEBUG] Step 3: Complete - State initialized")
            
            # Initialize required variables before window creation
            self.settings_file = Path("./data/gui_settings.json")
            self.delay_var = tk.StringVar(value="1.0")
            self.auto_pause_var = tk.BooleanVar(value=False)
            self.cv_status_var = tk.StringVar(value="No CV loaded")
            self.cv_preview_text = None  # Will be created in setup_ui
            
            # Initialize components
            self.ai_decision_view = None  # Will be created in setup_ui
            self.platform_manager = None  # Will be created in setup_ui
            self._activity_content = ""  # Store activity content
            
            # Create main window with enhanced visibility handling
            print("[DEBUG] Step 4: Creating main window...")
            try:
                self.window = tk.Tk()
                print("[DEBUG] Step 4a: tk.Tk() instance created successfully")
                print(f"[DEBUG] - Window exists: {self.window.winfo_exists()}")
                print(f"[DEBUG] - Window ID: {self.window.winfo_id()}")
                
                # Set window title and protocol
                self.window.title("LinkedIn Job Application Assistant")
                self.window.geometry("1200x800")
                self.window.protocol("WM_DELETE_WINDOW", self.on_closing)  # Bind close event
                print("[DEBUG] Step 4c: Window title and protocol set")
                
                # Set window icon if available
                try:
                    icon_path = Path("./assets/icon.ico")
                    if icon_path.exists():
                        self.window.iconbitmap(icon_path)
                except Exception as e:
                    print(f"[DEBUG] Could not set window icon: {e}")
                
                # Verify window creation
                if not self.window.winfo_exists():
                    raise RuntimeError("Window creation failed - winfo_exists() returned False")
                print("[DEBUG] Step 4b: Window exists check passed")
                
                # Get and verify screen dimensions
                screen_width = self.window.winfo_screenwidth()
                screen_height = self.window.winfo_screenheight()
                if screen_width <= 0 or screen_height <= 0:
                    raise RuntimeError(f"Invalid screen dimensions: {screen_width}x{screen_height}")
                print(f"[DEBUG] Step 4d: Valid screen dimensions detected: {screen_width}x{screen_height}")
                
                # Calculate and verify window position
                window_width = 800
                window_height = 600
                x_position = (screen_width - window_width) // 2
                y_position = (screen_height - window_height) // 2
                if x_position < 0 or y_position < 0:
                    raise RuntimeError(f"Invalid window position calculated: {x_position}, {y_position}")
                print(f"[DEBUG] Step 4e: Valid window position calculated: {x_position}, {y_position}")
                
                # Set window geometry
                self.window.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
                print("[DEBUG] Step 4f: Window geometry set")
                
                # Force window to be visible
                self.window.lift()
                self.window.attributes('-topmost', True)
                self.window.update()
                print("[DEBUG] Step 4g: Window lifted and updated")
                
                # Verify window is mapped
                if not self.window.winfo_ismapped():
                    print("[DEBUG] WARNING: Window is not mapped to screen")
                else:
                    print("[DEBUG] Step 4h: Window is mapped to screen")
                
                # Verify window has focus
                if not self.window.focus_get():
                    print("[DEBUG] WARNING: Window does not have focus")
                self.window.focus_force()
                print("[DEBUG] Step 4i: Focus forced")
                
                # Remove topmost flag
                self.window.attributes('-topmost', False)
                print("[DEBUG] Step 4j: Topmost flag removed")
                
                # Final window verification
                window_geometry = self.window.geometry()
                print(f"[DEBUG] Step 4k: Final window geometry: {window_geometry}")
            except Exception as e:
                print(f"[DEBUG] ERROR: Window creation failed: {str(e)}")
                raise
            
            print("[DEBUG] Step 4: Complete - Window created and configured")
            
            # Verify window visibility
            print("[DEBUG] Step 5: Verifying window visibility...")
            if not self.window.winfo_viewable():
                print("[DEBUG] WARNING: Window might not be visible!")
                print("[DEBUG] Window state:", self.window.state())
                print("[DEBUG] Window attributes:", self.window.attributes())
                print("[DEBUG] Window geometry:", self.window.geometry())
                print("[DEBUG] Window is mapped:", self.window.winfo_ismapped())
                print("[DEBUG] Window has focus:", bool(self.window.focus_get()))
                
                future = asyncio.run_coroutine_threadsafe(
                    self.logs_manager.warning("Window might not be visible - manual check required"),
                    self.async_loop
                )
                future.result(timeout=5.0)
            print("[DEBUG] Step 5: Complete - Window visibility verified")
            
            # Load settings
            print("[DEBUG] Step 6: Loading settings...")
            self.settings = self.load_settings()
            future = asyncio.run_coroutine_threadsafe(
                self.logs_manager.info(">>> Settings loaded successfully"),
                self.async_loop
            )
            future.result(timeout=5.0)
            print("[DEBUG] Step 6: Complete - Settings loaded")
            
            # Setup UI components
            print("[DEBUG] Step 7: Setting up UI components...")
            self.setup_ui()
            future = asyncio.run_coroutine_threadsafe(
                self.logs_manager.info(">>> UI components initialized"),
                self.async_loop
            )
            future.result(timeout=5.0)
            print("[DEBUG] Step 7: Complete - UI components set up")

            # Initialize platform manager with default settings
            print("[DEBUG] Step 8: Initializing platform manager...")
            if hasattr(self, 'platform_manager'):
                # Create default LinkedIn platform config
                linkedin_config = PlatformConfig(
                    platform_id="linkedin",
                    name="LinkedIn",
                    credentials={},  # Empty by default
                    settings={
                        "rate_limit": 100,
                        "timeout": 30,
                        "auto_apply": True,
                        "max_applications": 50,
                        "daily_limit": 100
                    }
                )
                self.platform_manager.add_platform(linkedin_config)
            
                # Initialize platform status
                linkedin_status = PlatformStatus(
                    platform_id="linkedin",
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
                self.platform_manager.update_platform_status(linkedin_status)
            
                future = asyncio.run_coroutine_threadsafe(
                    self.logs_manager.info(">>> Platform manager initialized with default settings"),
                    self.async_loop
                )
                future.result(timeout=5.0)
            print("[DEBUG] Step 8: Complete - Platform manager initialized")
            
            # Start status updates
            print("[DEBUG] Step 9: Starting status update loop...")
            self.update_status_loop()
            future = asyncio.run_coroutine_threadsafe(
                self.logs_manager.info(">>> Status update loop started"),
                self.async_loop
            )
            future.result(timeout=5.0)
            print("[DEBUG] Step 9: Complete - Status updates started")
            
            # Final window visibility check and focus
            print("[DEBUG] Step 10: Final window visibility check...")
            self.window.lift()
            self.window.focus_force()
            print("[DEBUG] Step 10: Complete - Final visibility check done")
            
            print("[DEBUG] ========================================")
            print("[DEBUG] MinimalGUI.__init__ has finished building the UI")
            print("[DEBUG] Window should now be visible on screen")
            print("[DEBUG] If not visible, check:")
            print(">>>  - Behind other windows (Alt+Tab)")
            print(">>>  - Other monitors")
            print(">>>  - Taskbar for minimized window")
            print("[DEBUG] ========================================")
                
        except Exception as e:
            print("[DEBUG] ========================================")
            print(f"[DEBUG] ERROR in MinimalGUI.__init__: {str(e)}")
            print("[DEBUG] ========================================")
            if hasattr(self, 'logs_manager') and hasattr(self, 'async_loop'):
                    future = asyncio.run_coroutine_threadsafe(
                        self.logs_manager.error(f">>> MinimalGUI initialization failed: {str(e)}"),
                        self.async_loop
                )
                    future.result(timeout=5.0)
            raise

    def run_app(self):
        """Start the GUI application."""
        try:
            print("[DEBUG] ========================================")
            print("[DEBUG] run_app() is starting...")
            print("[DEBUG] Current thread:", threading.current_thread().name)
            print("[DEBUG] Is main thread:", threading.current_thread() is threading.main_thread())
            print("[DEBUG] Window exists:", self.window.winfo_exists())
            print("[DEBUG] Window is mapped:", self.window.winfo_ismapped())
            print("[DEBUG] Window is viewable:", self.window.winfo_viewable())
            print("[DEBUG] Window geometry:", self.window.geometry())
            print("[DEBUG] Window state:", self.window.state())
            print("[DEBUG] ========================================")
            
            # Verify components before starting
            print("[DEBUG] Step 1: Verifying components...")
            status = self.verify_components()
            print("[DEBUG] Component status:", status)
            
            if status.get("event_loop", {}).get("running"):
                future = asyncio.run_coroutine_threadsafe(
                    self.logs_manager.info(">>> Event loop verification successful"),
                    self.async_loop
                )
                future.result(timeout=5.0)
                print("[DEBUG] Step 1: Complete - Event loop verified")
            else:
                print("[DEBUG] Step 1: WARNING - Event loop not running!")
                future = asyncio.run_coroutine_threadsafe(
                    self.logs_manager.warning(">>> Event loop not running or not properly initialized"),
                    self.async_loop
                )
                future.result(timeout=5.0)
            
            print("[DEBUG] Step 2: About to enter mainloop()...")
            print("[DEBUG] Window should be visible now")
            print("[DEBUG] Current window state:")
            print(f"  - Exists: {self.window.winfo_exists()}")
            print(f"  - Is mapped: {self.window.winfo_ismapped()}")
            print(f"  - Is viewable: {self.window.winfo_viewable()}")
            print(f"  - Geometry: {self.window.geometry()}")
            print(f"  - State: {self.window.state()}")
            print("[DEBUG] If not visible, check:")
            print(">>>  - Behind other windows (Alt+Tab)")
            print(">>>  - Other monitors")
            print(">>>  - Taskbar for minimized window")
            print("[DEBUG] The next message should only appear after you close the window")
            print("[DEBUG] ========================================")
            
            # Start mainloop - THIS SHOULD BLOCK
            self.window.mainloop()
            
            print("[DEBUG] ========================================")
            print("[DEBUG] mainloop() has returned - window was closed")
            print("[DEBUG] Final window state:")
            print(f"  - Exists: {self.window.winfo_exists()}")
            print(f"  - Is mapped: {self.window.winfo_ismapped() if self.window.winfo_exists() else 'N/A'}")
            print(f"  - Is viewable: {self.window.winfo_viewable() if self.window.winfo_exists() else 'N/A'}")
            print("[DEBUG] Starting cleanup process...")
            print("[DEBUG] ========================================")
            
            # Log completion if possible
            if hasattr(self, 'logs_manager') and hasattr(self, 'async_loop') and not self.async_loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(
                    self.logs_manager.info(">>> GUI mainloop ended normally"),
                    self.async_loop
                )
                future.result(timeout=5.0)
            
        except KeyboardInterrupt:
            print("[DEBUG] ========================================")
            print("[DEBUG] KeyboardInterrupt received in mainloop")
            print("[DEBUG] Current thread:", threading.current_thread().name)
            print("[DEBUG] ========================================")
            self.shutdown_requested = True
            self.stop()
            
        except Exception as e:
            print("[DEBUG] ========================================")
            print(f"[DEBUG] ERROR in run_app: {str(e)}")
            print("[DEBUG] Current thread:", threading.current_thread().name)
            print("[DEBUG] ========================================")
            if hasattr(self, 'logs_manager') and hasattr(self, 'async_loop') and not self.async_loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(
                    self.logs_manager.error(f">>> Error in GUI mainloop: {str(e)}"),
                    self.async_loop
                )
                future.result(timeout=5.0)
            raise
            
        finally:
            print("[DEBUG] ========================================")
            print("[DEBUG] run_app() is in finally block")
            print("[DEBUG] Calling cleanup()...")
            print("[DEBUG] Current thread:", threading.current_thread().name)
            print("[DEBUG] ========================================")
            self.cleanup()

    def stop(self):
        """Clean shutdown of GUI with proper error handling."""
        try:
            self.shutdown_requested = True
            
            # Stop automation if running
            if self.state["is_running"]:
                if self.async_loop and not self.async_loop.is_closed():
                    future = asyncio.run_coroutine_threadsafe(
                        self.stop_automation(),
                        self.async_loop
                    )
                    future.result(timeout=5.0)

            # Stop the async event loop
            if self.async_loop and not self.async_loop.is_closed():
                self.async_loop.call_soon_threadsafe(self.async_loop.stop)
            
            # Destroy the Tkinter window
            if self.window and self.window.winfo_exists():
                self.window.destroy()
            
            # Wait for the async thread to finish
            if self.async_thread and self.async_thread.is_alive():
                self.async_thread.join(timeout=5.0)
                
            # Log successful shutdown
            if self.async_loop and not self.async_loop.is_closed():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.logs_manager.info("GUI shutdown completed successfully"),
                        self.async_loop
                    )
                    future.result(timeout=5.0)
                except Exception:
                    pass  # If we can't log, we're probably already shut down
            
        except Exception as e:
            # Try to log the error, but don't raise since we're shutting down
            if self.async_loop and not self.async_loop.is_closed():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.logs_manager.error(f"Error during GUI shutdown: {str(e)}"),
                        self.async_loop
                    )
                    future.result(timeout=5.0)
                except Exception:
                    pass  # If we can't log, we're probably already shut down

    def _run_async_loop(self):
        """Run the async event loop in a separate thread."""
        try:
            # TODO: Move to logs_manager
            # print("[MinimalGUI] Starting async event loop thread")
            asyncio.set_event_loop(self.async_loop)
            self.async_loop.run_forever()
            # print("[MinimalGUI] Async event loop thread ended")
        except Exception as e:
            # Keep this print as it's critical error feedback
            print(f"[MinimalGUI] Error in async event loop thread: {str(e)}")
            if hasattr(self, 'logs_manager'):
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.logs_manager.error(f"Error in async event loop thread: {str(e)}"),
                        self.async_loop
                    )
                    future.result(timeout=5.0)
                except Exception:
                    pass  # If we can't log, we're probably already shut down
            raise

    def cleanup(self):
        """Clean up resources before shutdown."""
        try:
            # Stop the async loop
            if hasattr(self, 'async_loop') and self.async_loop and not self.async_loop.is_closed():
                if hasattr(self, 'logs_manager'):
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            self.logs_manager.info("Stopping async event loop..."),
                            self.async_loop
                        )
                        future.result(timeout=5.0)
                    except Exception:
                        pass  # If we can't log, we're probably already shut down
                
                self.async_loop.call_soon_threadsafe(self.async_loop.stop)
                
                if hasattr(self, 'async_thread') and self.async_thread:
                    self.async_thread.join(timeout=5.0)
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            self.logs_manager.info("Async thread joined"),
                            self.async_loop
                        )
                        future.result(timeout=5.0)
                    except Exception:
                        pass  # If we can't log, we're probably already shut down
                    
                self.async_loop.close()
            
            # Clean up window
            if hasattr(self, 'window') and self.window:
                try:
                    self.window.quit()
                    if hasattr(self, 'logs_manager') and hasattr(self, 'async_loop') and not self.async_loop.is_closed():
                        try:
                            future = asyncio.run_coroutine_threadsafe(
                                self.logs_manager.info("Window closed successfully"),
                                self.async_loop
                            )
                            future.result(timeout=5.0)
                        except Exception:
                            pass  # If we can't log, we're probably already shut down
                except Exception as e:
                    if hasattr(self, 'logs_manager') and hasattr(self, 'async_loop') and not self.async_loop.is_closed():
                        try:
                            future = asyncio.run_coroutine_threadsafe(
                                self.logs_manager.error(f"Error closing window: {str(e)}"),
                                self.async_loop
                            )
                            future.result(timeout=5.0)
                        except Exception:
                            pass  # If we can't log, we're probably already shut down
            
        except Exception as e:
            # Keep this print as it's critical error feedback
            print(f"[MinimalGUI] Error during cleanup: {str(e)}")
            if hasattr(self, 'logs_manager') and hasattr(self, 'async_loop') and not self.async_loop.is_closed():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.logs_manager.error(f"Error during cleanup: {str(e)}"),
                        self.async_loop
                    )
                    future.result(timeout=5.0)
                except Exception:
                    pass  # Suppress errors during cleanup logging

    def verify_components(self):
        """Verify that all components are properly initialized and running."""
        try:
            status = {
                "event_loop": {
                    "exists": hasattr(self, 'async_loop'),
                    "running": bool(self.async_loop and not self.async_loop.is_closed() if hasattr(self, 'async_loop') else False)
                },
                "thread": {
                    "exists": hasattr(self, 'async_thread'),
                    "alive": bool(self.async_thread and self.async_thread.is_alive() if hasattr(self, 'async_thread') else False)
                },
                "window": {
                    "exists": hasattr(self, 'window'),
                    "valid": bool(self.window and self.window.winfo_exists() if hasattr(self, 'window') else False)
                },
                "logs_manager": bool(hasattr(self, 'logs_manager')),
                "telemetry": bool(hasattr(self, 'telemetry'))
            }
            
            # Log verification results
            if hasattr(self, 'logs_manager') and hasattr(self, 'async_loop') and not self.async_loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(
                    self.logs_manager.info(f"Component verification results: {status}"),
                    self.async_loop
                )
                future.result(timeout=5.0)
            
            return status

        except Exception as e:
            print(f"[MinimalGUI] Error verifying components: {str(e)}")
            if hasattr(self, 'logs_manager') and hasattr(self, 'async_loop') and not self.async_loop.is_closed():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.logs_manager.error(f"Error verifying components: {str(e)}"),
                        self.async_loop
                    )
                    future.result(timeout=5.0)
                except Exception:
                    pass
            return {
                "error": str(e),
                "event_loop": False,
                "thread": False,
                "window": False,
                "logs_manager": False,
                "telemetry": False
            }

    def run_coroutine_in_background(self, coro):
        """Schedule an async coroutine to run on the background event loop."""
        if self.async_loop and not self.async_loop.is_closed():
            return asyncio.run_coroutine_threadsafe(coro, self.async_loop)
        return None

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
        """Save current settings to file."""
        try:
            settings = {
                "delay": self.delay_var.get(),
                "auto_pause": self.auto_pause_var.get(),
                "window_geometry": self.window.geometry()
            }
            
            # Ensure directory exists
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
                
            print(f"[DEBUG] Settings saved to {self.settings_file}")
            
        except Exception as e:
            print(f"[DEBUG] Error saving settings: {str(e)}")

    def load_settings(self):
        """Load settings from file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                print(f"[DEBUG] Settings loaded from {self.settings_file}")
                return settings
            return {}
        except Exception as e:
            print(f"[DEBUG] Error loading settings: {str(e)}")
            return {}

    def check_auto_pause(self):
        """Check if we should auto-pause based on runtime."""
        if self.state["is_running"] and not self.state["is_paused"] and self.state["start_time"]:
            runtime_hours = (datetime.now() - self.state["start_time"]).total_seconds() / 3600
            auto_pause_hours = float(self.auto_pause_var.get())
            
            if runtime_hours >= auto_pause_hours:
                self.run_coroutine_in_background(
                    self.logs_manager.warning(f"Auto-pausing after {auto_pause_hours} hours of runtime")
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
            self.run_coroutine_in_background(
                self.logs_manager.info(f"CV file selected: {cv_path.name}")
            )
            
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
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error selecting CV file: {str(e)}")
            )
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
            self.run_coroutine_in_background(
                self.logs_manager.info(f"CV preview generated for {file_path.name}")
            )

        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error previewing CV: {str(e)}")
            )
            self.cv_preview_text.insert(tk.END, "Error loading preview")
            self.cv_preview_text.config(state=tk.DISABLED)

    async def parse_cv_content(self, file_path: Path):
        """Parse the CV content using CVParserAgent."""
        try:
            # Get CVParserAgent instance from controller
            if not hasattr(self.controller, 'cv_parser'):
                await self.logs_manager.error("CV Parser not initialized")
                return
            
            # Parse the CV
            await self.logs_manager.info("Parsing CV content...")
            cv_data = await self.controller.cv_parser.parse_cv(file_path)
            
            if cv_data:
                await self.logs_manager.info("CV parsed successfully")
                # Store parsed data in controller's settings
                self.controller.settings['parsed_cv_data'] = cv_data.dict()
                self.save_settings()
            else:
                await self.logs_manager.warning("No data extracted from CV")
        except Exception as e:
            await self.logs_manager.error(f"Error parsing CV: {str(e)}")
            raise

    def validate_cv_file(self, file_path: Path) -> bool:
        """Validate the selected CV file with enhanced checks."""
        try:
            # Check if file exists
            if not file_path.exists():
                self.run_coroutine_in_background(
                    self.logs_manager.error("Selected file does not exist")
                )
                return False
                
            # Check file size (5MB limit)
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if file_path.stat().st_size > max_size:
                self.run_coroutine_in_background(
                    self.logs_manager.error("File too large. Maximum size is 5MB")
                )
                return False
                
            # Check file format
            valid_formats = {'.pdf', '.docx', '.txt'}
            if file_path.suffix.lower() not in valid_formats:
                self.run_coroutine_in_background(
                    self.logs_manager.error(f"Unsupported file format. Please use: {', '.join(valid_formats)}")
                )
                return False
                
            # Additional validation checks
            if file_path.stat().st_size == 0:
                self.run_coroutine_in_background(
                    self.logs_manager.error("File is empty")
                )
                return False
                
            # Check if file is readable
            try:
                file_path.open('rb').close()
            except Exception:
                self.run_coroutine_in_background(
                    self.logs_manager.error("File is not readable")
                )
                return False
                
            # For PDF files, check if it's a valid PDF
            if file_path.suffix.lower() == '.pdf':
                try:
                    with open(file_path, 'rb') as f:
                        PyPDF2.PdfReader(f)
                except Exception:
                    self.run_coroutine_in_background(
                        self.logs_manager.error("Invalid PDF file")
                    )
                    return False
                    
            return True
            
        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error validating CV file: {str(e)}")
            )
            return False

    def remove_cv_file(self):
        """Handle CV file removal."""
        try:
            # Remove the CV file from the controller's settings
            self.controller.settings.pop('cv_file_path', None)
            
            # Update status
            self.cv_status_var.set("No CV uploaded")
            self.run_coroutine_in_background(
                self.logs_manager.info("CV file removed")
            )
            
            # Track the event
            self.run_coroutine_in_background(
                self._track_telemetry("cv_removed")
            )
            
            # Save settings to persist the change
            self.save_settings()
        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error removing CV file: {str(e)}")
            )
            self.cv_status_var.set("Error removing CV file")

    def setup_ui(self):
        """Set up the GUI components."""
        try:
            # Create main notebook for tabs
            self.notebook = ttk.Notebook(self.window)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create tabs
            self.control_tab = ttk.Frame(self.notebook)
            self.activity_tab = ttk.Frame(self.notebook)
            self.settings_tab = ttk.Frame(self.notebook)
            
            self.notebook.add(self.control_tab, text="Control")
            self.notebook.add(self.activity_tab, text="Activity")
            self.notebook.add(self.settings_tab, text="Settings")
            
            # Setup Control Tab
            self.setup_control_tab()
            
            # Setup Activity Tab
            self.setup_activity_tab()
            
            # Setup Settings Tab
            self.setup_settings_tab()

        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error setting up UI: {str(e)}")
            )

    def setup_activity_tab(self):
        """Set up the activity tab with AI decision view and activity log."""
        try:
            # Create left frame for AI decision view
            left_frame = ttk.Frame(self.activity_tab)
            left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create AI decision view
            self.ai_decision_view = AIDecisionView(left_frame)
            self.ai_decision_view.pack(fill=tk.BOTH, expand=True)
            
            # Create right frame for activity log
            right_frame = ttk.Frame(self.activity_tab)
            right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create activity filter view
            self.activity_filter = ActivityFilterView(right_frame)
            self.activity_filter.pack(fill=tk.BOTH, expand=True)
            
            # Create platform manager view
            self.platform_manager = PlatformManagerView(self.activity_tab)
            self.platform_manager.pack(fill=tk.X, padx=5, pady=5)

        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error setting up activity tab: {str(e)}")
            )

    def setup_control_tab(self):
        """Set up the control tab with automation controls."""
        # Create control frame
        control_frame = ttk.LabelFrame(self.control_tab, text="Automation Controls")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create buttons frame
        buttons_frame = ttk.Frame(control_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create control buttons
        self.start_button = ttk.Button(
            buttons_frame,
            text="Start",
            command=self.start_automation_command
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.pause_button = ttk.Button(
            buttons_frame,
            text="Pause",
            command=self.pause_automation_command,
            state=tk.DISABLED
        )
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            buttons_frame,
            text="Stop",
            command=self.stop_automation_command,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Create delay control
        delay_frame = ttk.Frame(control_frame)
        delay_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(delay_frame, text="Delay (seconds):").pack(side=tk.LEFT)
        delay_entry = ttk.Entry(
            delay_frame,
            textvariable=self.delay_var,
            width=10
        )
        delay_entry.pack(side=tk.LEFT, padx=5)
        
        # Create auto-pause control
        auto_pause_frame = ttk.Frame(control_frame)
        auto_pause_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(auto_pause_frame, text="Auto-pause after (hours):").pack(side=tk.LEFT)
        auto_pause_entry = ttk.Entry(
            auto_pause_frame,
            textvariable=self.auto_pause_var,
            width=10
        )
        auto_pause_entry.pack(side=tk.LEFT, padx=5)

    def setup_settings_tab(self):
        """Set up the settings tab."""
        # Create CV section
        cv_frame = ttk.LabelFrame(self.settings_tab, text="CV Management")
        cv_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create CV buttons frame
        cv_buttons_frame = ttk.Frame(cv_frame)
        cv_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Add CV selection button
        select_cv_button = ttk.Button(
            cv_buttons_frame,
            text="Select CV",
            command=self.select_cv_file
        )
        select_cv_button.pack(side=tk.LEFT, padx=5)
        
        # Add CV status label
        cv_status_label = ttk.Label(
            cv_buttons_frame,
            textvariable=self.cv_status_var
        )
        cv_status_label.pack(side=tk.LEFT, padx=5)
        
        # Create CV preview
        preview_frame = ttk.LabelFrame(cv_frame, text="CV Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.cv_preview_text = scrolledtext.ScrolledText(
            preview_frame,
            wrap=tk.WORD,
            width=50,
            height=10
        )
        self.cv_preview_text.pack(fill=tk.BOTH, expand=True)
        self.cv_preview_text.config(state=tk.DISABLED)

    def on_closing(self):
        """Handle window close event."""
        try:
            print("[DEBUG] on_closing called - starting cleanup")
            
            # Save current settings
            self.save_settings()
            
            # Stop any running operations
            if hasattr(self, 'stop'):
                self.stop()
            
            # Clean up async resources
            if hasattr(self, 'async_loop') and not self.async_loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(
                    self.logs_manager.info(">>> GUI closing - cleanup initiated"),
                    self.async_loop
                )
                future.result(timeout=5.0)
            
            # Destroy the window
            if hasattr(self, 'window') and self.window.winfo_exists():
                self.window.destroy()
            
            print("[DEBUG] on_closing completed successfully")
            
        except Exception as e:
            print(f"[DEBUG] Error in on_closing: {str(e)}")
            # Still try to destroy the window even if other cleanup fails
            if hasattr(self, 'window') and self.window.winfo_exists():
                self.window.destroy()

    def stop(self):
        """Stop all running operations."""
        try:
            print("[DEBUG] stop called - halting operations")
            self.state["is_running"] = False
            self.state["is_paused"] = False
            
            if hasattr(self, 'async_loop') and not self.async_loop.is_closed():
                    future = asyncio.run_coroutine_threadsafe(
                    self.logs_manager.info(">>> Operations stopped by user"),
                        self.async_loop
                    )
                    future.result(timeout=5.0)
            
            print("[DEBUG] stop completed successfully")
            
        except Exception as e:
            print(f"[DEBUG] Error in stop: {str(e)}")

    def save_settings(self):
        """Save current settings to file."""
        try:
            settings = {
                "delay": self.delay_var.get(),
                "auto_pause": self.auto_pause_var.get(),
                "window_geometry": self.window.geometry()
            }
            
            # Ensure directory exists
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
                
            print(f"[DEBUG] Settings saved to {self.settings_file}")
            
        except Exception as e:
            print(f"[DEBUG] Error saving settings: {str(e)}")

    def load_settings(self):
        """Load settings from file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                print(f"[DEBUG] Settings loaded from {self.settings_file}")
                return settings
            return {}
        except Exception as e:
            print(f"[DEBUG] Error loading settings: {str(e)}")
            return {}

    def check_auto_pause(self):
        """Check if we should auto-pause based on runtime."""
        if self.state["is_running"] and not self.state["is_paused"] and self.state["start_time"]:
            runtime_hours = (datetime.now() - self.state["start_time"]).total_seconds() / 3600
            auto_pause_hours = float(self.auto_pause_var.get())
            
            if runtime_hours >= auto_pause_hours:
                self.run_coroutine_in_background(
                    self.logs_manager.warning(f"Auto-pausing after {auto_pause_hours} hours of runtime")
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
            self.run_coroutine_in_background(
                self.logs_manager.info(f"CV file selected: {cv_path.name}")
            )
            
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
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error selecting CV file: {str(e)}")
            )
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
            self.run_coroutine_in_background(
                self.logs_manager.info(f"CV preview generated for {file_path.name}")
            )

        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error previewing CV: {str(e)}")
            )
            self.cv_preview_text.insert(tk.END, "Error loading preview")
            self.cv_preview_text.config(state=tk.DISABLED)

    async def parse_cv_content(self, file_path: Path):
        """Parse the CV content using CVParserAgent."""
        try:
            # Get CVParserAgent instance from controller
            if not hasattr(self.controller, 'cv_parser'):
                await self.logs_manager.error("CV Parser not initialized")
                return
            
            # Parse the CV
            await self.logs_manager.info("Parsing CV content...")
            cv_data = await self.controller.cv_parser.parse_cv(file_path)
            
            if cv_data:
                await self.logs_manager.info("CV parsed successfully")
                # Store parsed data in controller's settings
                self.controller.settings['parsed_cv_data'] = cv_data.dict()
                self.save_settings()
            else:
                await self.logs_manager.warning("No data extracted from CV")
        except Exception as e:
            await self.logs_manager.error(f"Error parsing CV: {str(e)}")
            raise

    def validate_cv_file(self, file_path: Path) -> bool:
        """Validate the selected CV file with enhanced checks."""
        try:
            # Check if file exists
            if not file_path.exists():
                self.run_coroutine_in_background(
                    self.logs_manager.error("Selected file does not exist")
                )
                return False
                
            # Check file size (5MB limit)
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if file_path.stat().st_size > max_size:
                self.run_coroutine_in_background(
                    self.logs_manager.error("File too large. Maximum size is 5MB")
                )
                return False
                
            # Check file format
            valid_formats = {'.pdf', '.docx', '.txt'}
            if file_path.suffix.lower() not in valid_formats:
                self.run_coroutine_in_background(
                    self.logs_manager.error(f"Unsupported file format. Please use: {', '.join(valid_formats)}")
                )
                return False
                
            # Additional validation checks
            if file_path.stat().st_size == 0:
                self.run_coroutine_in_background(
                    self.logs_manager.error("File is empty")
                )
                return False
                
            # Check if file is readable
            try:
                file_path.open('rb').close()
            except Exception:
                self.run_coroutine_in_background(
                    self.logs_manager.error("File is not readable")
                )
                return False
                
            # For PDF files, check if it's a valid PDF
            if file_path.suffix.lower() == '.pdf':
                try:
                    with open(file_path, 'rb') as f:
                        PyPDF2.PdfReader(f)
                except Exception:
                    self.run_coroutine_in_background(
                        self.logs_manager.error("Invalid PDF file")
                    )
                    return False
                    
            return True
            
        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error validating CV file: {str(e)}")
            )
            return False

    def remove_cv_file(self):
        """Handle CV file removal."""
        try:
            # Remove the CV file from the controller's settings
            self.controller.settings.pop('cv_file_path', None)
            
            # Update status
            self.cv_status_var.set("No CV uploaded")
            self.run_coroutine_in_background(
                self.logs_manager.info("CV file removed")
            )
            
            # Track the event
            self.run_coroutine_in_background(
                self._track_telemetry("cv_removed")
            )
            
            # Save settings to persist the change
            self.save_settings()
        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error removing CV file: {str(e)}")
            )
            self.cv_status_var.set("Error removing CV file")

    def setup_ui(self):
        """Set up the GUI components."""
        try:
            # Create main notebook for tabs
            self.notebook = ttk.Notebook(self.window)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create tabs
            self.control_tab = ttk.Frame(self.notebook)
            self.activity_tab = ttk.Frame(self.notebook)
            self.settings_tab = ttk.Frame(self.notebook)
            
            self.notebook.add(self.control_tab, text="Control")
            self.notebook.add(self.activity_tab, text="Activity")
            self.notebook.add(self.settings_tab, text="Settings")
            
            # Setup Control Tab
            self.setup_control_tab()
            
            # Setup Activity Tab
            self.setup_activity_tab()
            
            # Setup Settings Tab
            self.setup_settings_tab()

        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error setting up UI: {str(e)}")
            )

    def setup_activity_tab(self):
        """Set up the activity tab with AI decision view and activity log."""
        try:
            # Create left frame for AI decision view
            left_frame = ttk.Frame(self.activity_tab)
            left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create AI decision view
            self.ai_decision_view = AIDecisionView(left_frame)
            self.ai_decision_view.pack(fill=tk.BOTH, expand=True)
            
            # Create right frame for activity log
            right_frame = ttk.Frame(self.activity_tab)
            right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create activity filter view
            self.activity_filter = ActivityFilterView(right_frame)
            self.activity_filter.pack(fill=tk.BOTH, expand=True)
            
            # Create platform manager view
            self.platform_manager = PlatformManagerView(self.activity_tab)
            self.platform_manager.pack(fill=tk.X, padx=5, pady=5)

        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error setting up activity tab: {str(e)}")
            )

    def setup_control_tab(self):
        """Set up the control tab with automation controls."""
        # Create control frame
        control_frame = ttk.LabelFrame(self.control_tab, text="Automation Controls")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create buttons frame
        buttons_frame = ttk.Frame(control_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create control buttons
        self.start_button = ttk.Button(
            buttons_frame,
            text="Start",
            command=self.start_automation_command
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.pause_button = ttk.Button(
            buttons_frame,
            text="Pause",
            command=self.pause_automation_command,
            state=tk.DISABLED
        )
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            buttons_frame,
            text="Stop",
            command=self.stop_automation_command,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Create delay control
        delay_frame = ttk.Frame(control_frame)
        delay_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(delay_frame, text="Delay (seconds):").pack(side=tk.LEFT)
        delay_entry = ttk.Entry(
            delay_frame,
            textvariable=self.delay_var,
            width=10
        )
        delay_entry.pack(side=tk.LEFT, padx=5)
        
        # Create auto-pause control
        auto_pause_frame = ttk.Frame(control_frame)
        auto_pause_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(auto_pause_frame, text="Auto-pause after (hours):").pack(side=tk.LEFT)
        auto_pause_entry = ttk.Entry(
            auto_pause_frame,
            textvariable=self.auto_pause_var,
            width=10
        )
        auto_pause_entry.pack(side=tk.LEFT, padx=5)

    def setup_settings_tab(self):
        """Set up the settings tab."""
        # Create CV section
        cv_frame = ttk.LabelFrame(self.settings_tab, text="CV Management")
        cv_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create CV buttons frame
        cv_buttons_frame = ttk.Frame(cv_frame)
        cv_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Add CV selection button
        select_cv_button = ttk.Button(
            cv_buttons_frame,
            text="Select CV",
            command=self.select_cv_file
        )
        select_cv_button.pack(side=tk.LEFT, padx=5)
        
        # Add CV status label
        cv_status_label = ttk.Label(
            cv_buttons_frame,
            textvariable=self.cv_status_var
        )
        cv_status_label.pack(side=tk.LEFT, padx=5)
        
        # Create CV preview
        preview_frame = ttk.LabelFrame(cv_frame, text="CV Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.cv_preview_text = scrolledtext.ScrolledText(
            preview_frame,
            wrap=tk.WORD,
            width=50,
            height=10
        )
        self.cv_preview_text.pack(fill=tk.BOTH, expand=True)
        self.cv_preview_text.config(state=tk.DISABLED)

    def on_closing(self):
        """Handle window close event."""
        try:
            print("[DEBUG] on_closing called - starting cleanup")
            
            # Save current settings
            self.save_settings()
            
            # Stop any running operations
            if hasattr(self, 'stop'):
                self.stop()
            
            # Clean up async resources
            if hasattr(self, 'async_loop') and not self.async_loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(
                    self.logs_manager.info(">>> GUI closing - cleanup initiated"),
                    self.async_loop
                )
                future.result(timeout=5.0)
            
            # Destroy the window
            if hasattr(self, 'window') and self.window.winfo_exists():
                self.window.destroy()
            
            print("[DEBUG] on_closing completed successfully")
            
        except Exception as e:
            print(f"[DEBUG] Error in on_closing: {str(e)}")
            # Still try to destroy the window even if other cleanup fails
            if hasattr(self, 'window') and self.window.winfo_exists():
                self.window.destroy()
    def stop(self):
        """Stop all running operations."""
        try:
            print("[DEBUG] stop called - halting operations")
            self.state["is_running"] = False
            self.state["is_paused"] = False
            
            if hasattr(self, 'async_loop') and not self.async_loop.is_closed():
                    future = asyncio.run_coroutine_threadsafe(
                    self.logs_manager.info(">>> Operations stopped by user"),
                        self.async_loop
                    )
                    future.result(timeout=5.0)
            
            print("[DEBUG] stop completed successfully")
            
        except Exception as e:
            print(f"[DEBUG] Error in stop: {str(e)}")

    def save_settings(self):
        """Save current settings to file."""
        try:
            settings = {
                "delay": self.delay_var.get(),
                "auto_pause": self.auto_pause_var.get(),
                "window_geometry": self.window.geometry()
            }
            
            # Ensure directory exists
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
                
            print(f"[DEBUG] Settings saved to {self.settings_file}")
            
        except Exception as e:
            print(f"[DEBUG] Error saving settings: {str(e)}")

    def load_settings(self):
        """Load settings from file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                print(f"[DEBUG] Settings loaded from {self.settings_file}")
                return settings
            return {}
        except Exception as e:
            print(f"[DEBUG] Error loading settings: {str(e)}")
            return {}

    def check_auto_pause(self):
        """Check if we should auto-pause based on runtime."""
        if self.state["is_running"] and not self.state["is_paused"] and self.state["start_time"]:
            runtime_hours = (datetime.now() - self.state["start_time"]).total_seconds() / 3600
            auto_pause_hours = float(self.auto_pause_var.get())
            
            if runtime_hours >= auto_pause_hours:
                self.run_coroutine_in_background(
                    self.logs_manager.warning(f"Auto-pausing after {auto_pause_hours} hours of runtime")
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
            self.run_coroutine_in_background(
                self.logs_manager.info(f"CV file selected: {cv_path.name}")
            )
            
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
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error selecting CV file: {str(e)}")
            )
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
            self.run_coroutine_in_background(
                self.logs_manager.info(f"CV preview generated for {file_path.name}")
            )
            
        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error previewing CV: {str(e)}")
            )
            self.cv_preview_text.insert(tk.END, "Error loading preview")
            self.cv_preview_text.config(state=tk.DISABLED)

    async def parse_cv_content(self, file_path: Path):
        """Parse the CV content using CVParserAgent."""
        try:
            # Get CVParserAgent instance from controller
            if not hasattr(self.controller, 'cv_parser'):
                await self.logs_manager.error("CV Parser not initialized")
                return
            
            # Parse the CV
            await self.logs_manager.info("Parsing CV content...")
            cv_data = await self.controller.cv_parser.parse_cv(file_path)
            
            if cv_data:
                await self.logs_manager.info("CV parsed successfully")
                # Store parsed data in controller's settings
                self.controller.settings['parsed_cv_data'] = cv_data.dict()
                self.save_settings()
            else:
                await self.logs_manager.warning("No data extracted from CV")
        except Exception as e:
            await self.logs_manager.error(f"Error parsing CV: {str(e)}")
            raise

    def validate_cv_file(self, file_path: Path) -> bool:
        """Validate the selected CV file with enhanced checks."""
        try:
            # Check if file exists
            if not file_path.exists():
                self.run_coroutine_in_background(
                    self.logs_manager.error("Selected file does not exist")
                )
                return False
                
            # Check file size (5MB limit)
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if file_path.stat().st_size > max_size:
                self.run_coroutine_in_background(
                    self.logs_manager.error("File too large. Maximum size is 5MB")
                )
                return False
                
            # Check file format
            valid_formats = {'.pdf', '.docx', '.txt'}
            if file_path.suffix.lower() not in valid_formats:
                self.run_coroutine_in_background(
                    self.logs_manager.error(f"Unsupported file format. Please use: {', '.join(valid_formats)}")
                )
                return False
                
            # Additional validation checks
            if file_path.stat().st_size == 0:
                self.run_coroutine_in_background(
                    self.logs_manager.error("File is empty")
                )
                return False
                
            # Check if file is readable
            try:
                file_path.open('rb').close()
            except Exception:
                self.run_coroutine_in_background(
                    self.logs_manager.error("File is not readable")
                )
                return False
                
            # For PDF files, check if it's a valid PDF
            if file_path.suffix.lower() == '.pdf':
                try:
                    with open(file_path, 'rb') as f:
                        PyPDF2.PdfReader(f)
                except Exception:
                    self.run_coroutine_in_background(
                        self.logs_manager.error("Invalid PDF file")
                    )
                    return False
                    
            return True
            
        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error validating CV file: {str(e)}")
            )
            return False

    def remove_cv_file(self):
        """Handle CV file removal."""
        try:
            # Remove the CV file from the controller's settings
            self.controller.settings.pop('cv_file_path', None)
            
            # Update status
            self.cv_status_var.set("No CV uploaded")
            self.run_coroutine_in_background(
                self.logs_manager.info("CV file removed")
            )
            
            # Track the event
            self.run_coroutine_in_background(
                self._track_telemetry("cv_removed")
            )
            
            # Save settings to persist the change
            self.save_settings()
        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error removing CV file: {str(e)}")
            )
            self.cv_status_var.set("Error removing CV file")

    def setup_ui(self):
        """Set up the GUI components."""
        try:
            # Create main notebook for tabs
            self.notebook = ttk.Notebook(self.window)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create tabs
            self.control_tab = ttk.Frame(self.notebook)
            self.activity_tab = ttk.Frame(self.notebook)
            self.settings_tab = ttk.Frame(self.notebook)
            
            self.notebook.add(self.control_tab, text="Control")
            self.notebook.add(self.activity_tab, text="Activity")
            self.notebook.add(self.settings_tab, text="Settings")
            
            # Setup Control Tab
            self.setup_control_tab()
            
            # Setup Activity Tab
            self.setup_activity_tab()
            
            # Setup Settings Tab
            self.setup_settings_tab()

        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error setting up UI: {str(e)}")
            )

    def setup_activity_tab(self):
        """Set up the activity tab with AI decision view and activity log."""
        try:
            # Create left frame for AI decision view
            left_frame = ttk.Frame(self.activity_tab)
            left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create AI decision view
            self.ai_decision_view = AIDecisionView(left_frame)
            self.ai_decision_view.pack(fill=tk.BOTH, expand=True)
            
            # Create right frame for activity log
            right_frame = ttk.Frame(self.activity_tab)
            right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create activity filter view
            self.activity_filter = ActivityFilterView(right_frame)
            self.activity_filter.pack(fill=tk.BOTH, expand=True)
            
            # Create platform manager view
            self.platform_manager = PlatformManagerView(self.activity_tab)
            self.platform_manager.pack(fill=tk.X, padx=5, pady=5)

        except Exception as e:
            self.run_coroutine_in_background(
                self.logs_manager.error(f"Error setting up activity tab: {str(e)}")
            )

    def log_activity(self, message: str, activity_type: str = "SYSTEM"):
        """Log an activity with timestamp and proper formatting."""
        try:
            # Format timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Create activity content
            activity = {
                "timestamp": timestamp,
                "type": activity_type,
                "message": message,
                "agent": "system"  # Default agent
            }
            
            # Add to activity filter
            if hasattr(self, 'activity_filter'):
                self.activity_filter.add_activity(activity)
            
            # If AI-related, send to AI decision view
            if activity_type in ["ai_decision", "ai_action", "ai_error"]:
                if hasattr(self, 'ai_decision_view'):
                    self.ai_decision_view.add_decision(AIDecision(message))
            
            # Update platform metrics if relevant
            if hasattr(self, 'platform_manager'):
                self.platform_manager.update_metrics("linkedin", {
                    "total_activities": 1,
                    "error_rate": 1 if activity_type == "error" else 0
                })
            
        except Exception as e:
            if hasattr(self, 'logs_manager'):
                self.run_coroutine_in_background(
                    self.logs_manager.error(f"Error logging activity: {str(e)}")
                )
            else:
                print(f"Error logging activity: {str(e)}")

