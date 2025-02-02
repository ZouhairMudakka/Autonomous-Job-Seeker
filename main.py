"""
AI-Powered Job Application Automation System

This file sets up:
1) Configuration & logs
2) Browser selection and initialization
3) A choice among 'automatic', 'full control' mode, or 'GUI' mode
4) The asynchronous environment
5) The CLI for 'full control' mode
6) The commented MinimalGUI approach if user picks GUI (placeholder)

Future expansions:
- Incorporate concurrency for multiple tasks in parallel
- Build the actual MinimalGUI logic in ui/minimal_gui.py
- Integrate with multiple job platforms beyond LinkedIn
- Enhance AI-driven decision making for job matching
- Implement automated resume parsing and customization
- Add automated interview preparation features
- Develop job market analysis capabilities
"""

import sys
import asyncio
import threading
import os
import psutil
from config.settings import load_settings
from orchestrator.controller import Controller
from ui.cli import CLI
from storage.logs_manager import LogsManager
from ui.minimal_gui import MinimalGUI
from utils.browser_setup import BrowserSetup
from utils.telemetry import TelemetryManager
from constants import TimingConstants, Messages
from debug_sleep import debug_sleep

# Remove duplicate MinimalGUI import - will import dynamically when needed
# from ui.minimal_gui import MinimalGUI

def check_gui_dependencies():
    """Check if all required GUI dependencies are available."""
    missing_deps = []
    
    try:
        import tkinter
    except ImportError:
        missing_deps.append("tkinter")
    
    try:
        import tkcalendar
    except ImportError:
        missing_deps.append("tkcalendar")
    
    try:
        import PyPDF2
    except ImportError:
        missing_deps.append("PyPDF2")
        
    return missing_deps

async def async_main():
    """
    The main async function with proper error handling and resource management.
    """
    print("\n[DEBUG] ========== INITIALIZATION SEQUENCE START ==========")
    print("[DEBUG] Step 1: Entering async_main")
    
    browser = None
    page = None
    logs_manager = None
    controller = None
    browser_setup = None
    telemetry_manager = None

    try:
        # 1) Load configuration
        print("[DEBUG] Step 2: Loading configuration")
        settings = load_settings()
        print("[DEBUG] Configuration loaded successfully")
        
        # 2) Initialize telemetry and logs with proper cleanup handling
        print("[DEBUG] Step 3: Initializing telemetry and logs")
        telemetry_manager = TelemetryManager(settings)
        logs_manager = LogsManager(settings, telemetry_manager)
        await logs_manager.initialize()
        print("[DEBUG] Telemetry and logs initialized")
        await logs_manager.info("Starting AI-Powered Job Application System...")
        await logs_manager.info("Configuration loaded successfully")

        # 3) Browser setup with proper error handling
        print("[DEBUG] Step 4: Setting up browser")
        await logs_manager.info("Initializing browser setup...")
        browser_setup = BrowserSetup(settings, logs_manager)
        try:
            browser, page = await browser_setup.initialize(
                attach_existing=settings['browser'].get('attach_existing', False)
            )
            print("[DEBUG] Browser setup completed")
            await logs_manager.info("Browser initialization completed successfully")
        except Exception as e:
            print(f"[DEBUG] ERROR: Browser setup failed - {str(e)}")
            await logs_manager.error(f"Failed to initialize browser: {str(e)}")
            if logs_manager:
                await logs_manager.shutdown()
            return

        # 4) Create application controller
        print("[DEBUG] Step 5: Creating controller")
        print("[DEBUG] ========================================")
        print("[DEBUG] Creating application controller...")
        print(f"[DEBUG] Current thread: {threading.current_thread().name}")
        print("[DEBUG] Settings loaded:", bool(settings))
        print("[DEBUG] Page available:", bool(page))
        print("[DEBUG] ========================================")
        
        try:
            # Create controller with only required arguments
            controller = Controller(settings=settings, page=page)
            print("[DEBUG] Controller created successfully")
            await logs_manager.info("Controller created successfully")
            
        except Exception as e:
            error_msg = f"Failed to create controller: {str(e)}"
            print(f"[DEBUG] ERROR: {error_msg}")
            print(f"[DEBUG] Exception type: {type(e).__name__}")
            print("[DEBUG] ========================================")
            await logs_manager.error(error_msg)
            raise
        
        # 5) Run selected mode (session handled within modes)
        print("[DEBUG] Step 6: Ready to run selected mode")
        print("[DEBUG] ========== INITIALIZATION SEQUENCE COMPLETE ==========\n")
        await run_selected_mode(controller, logs_manager)

    except Exception as e:
        if logs_manager:
            await logs_manager.error(f"Critical error in async_main: {str(e)}")
    finally:
        # Cleanup in reverse order of creation
        if controller:
            try:
                await logs_manager.info("Ending controller session...")
                await controller.end_session()
                await logs_manager.info("Controller session ended successfully")
            except Exception as e:
                if logs_manager:
                    await logs_manager.error(f"Error during controller cleanup: {str(e)}")

        if browser and page:
            try:
                if browser_setup:
                    await logs_manager.info("Cleaning up browser resources...")
                    await browser_setup.cleanup(browser, page)
                    await logs_manager.info("Browser cleanup completed")
            except Exception as e:
                if logs_manager:
                    await logs_manager.error(f"Error during browser cleanup: {str(e)}")

        if logs_manager:
            try:
                await logs_manager.info("Shutting down logging system...")
                await logs_manager.shutdown()
            except Exception as e:
                # Can't use logs_manager here since we're shutting it down
                print(f"Error during logs cleanup: {e}")

async def run_selected_mode(controller: Controller, logs_manager: LogsManager):
    """Handle mode selection and execution with proper error handling."""
    while True:
        try:
            print("\n[DEBUG] ========================================")
            print("[DEBUG] Starting mode selection sequence")
            await logs_manager.info("Prompting user for operation mode selection")
            
            # Display menu to user (keep prints for UI)
            print("\nOperation Mode:")
            print("1) Automatic Mode (autopilot)")
            print("2) Full Control Mode (interactive CLI)")
            print("3) GUI Mode")
            print("4) Exit")
            
            # Use async input
            print("[DEBUG] Waiting for user input...")
            mode_choice = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("\nSelect mode (1-4): ").strip()
            )
            print(f"[DEBUG] User selected mode: {mode_choice}")
            
            if mode_choice == '4':
                await logs_manager.info("User selected to exit the application")
                break
                
            if mode_choice in ['1', '2', '3']:
                success = False
                try:
                    # Start session before running mode
                    print("[DEBUG] Starting controller session...")
                    await logs_manager.info("Starting controller session...")
                    await controller.start_session()
                    print("[DEBUG] Controller session started successfully")
                    
                    if mode_choice == '1':
                        await logs_manager.info("Starting Automatic Mode...")
                        await run_automatic_mode(controller, logs_manager)
                    elif mode_choice == '2':
                        await logs_manager.info("Starting Full Control Mode...")
                        await run_full_control_mode(controller, logs_manager)
                    else:  # mode_choice == '3'
                        print("[DEBUG] ========================================")
                        print("[DEBUG] Pre-GUI Initialization Checks:")
                        print(f"[DEBUG] Python version: {sys.version}")
                        print(f"[DEBUG] Platform: {sys.platform}")
                        print(f"[DEBUG] Current working directory: {os.getcwd()}")
                        print(f"[DEBUG] Available memory: {psutil.virtual_memory().available / (1024 * 1024):.2f} MB")
                        
                        # Check GUI dependencies
                        print("[DEBUG] Checking GUI dependencies...")
                        missing_deps = check_gui_dependencies()
                        if missing_deps:
                            error_msg = f"Missing required GUI dependencies: {', '.join(missing_deps)}"
                            print(f"[DEBUG] ERROR: {error_msg}")
                            await logs_manager.error(error_msg)
                            raise ImportError(error_msg)
                        print("[DEBUG] All GUI dependencies available")
                        print("[DEBUG] ========================================")
                        
                        await logs_manager.info("Starting GUI Mode...")
                        try:
                            print("[DEBUG] GUI Mode Transition Sequence:")
                            print("[DEBUG] 1. Mode '3' selected - Starting GUI initialization")
                            print(f"[DEBUG] Current thread: {threading.current_thread().name}")
                            print(f"[DEBUG] Is main thread: {threading.current_thread() is threading.main_thread()}")
                            print("[DEBUG] ========================================")
                            
                            if sys.platform == 'win32':
                                print("[DEBUG] Windows detected - Setting event loop policy...")
                                print(f"[DEBUG] Current event loop policy: {asyncio.get_event_loop_policy().__class__.__name__}")
                                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                                print(f"[DEBUG] New event loop policy: {asyncio.get_event_loop_policy().__class__.__name__}")
                            
                            print("[DEBUG] 2. About to create MinimalGUI instance")
                            print("[DEBUG] - Controller state:", "valid" if controller else "invalid")
                            print("[DEBUG] - Logs manager state:", "valid" if logs_manager else "invalid")
                            print("[DEBUG] - Current event loop:", asyncio.get_event_loop())
                            print("[DEBUG] - Loop is running:", asyncio.get_event_loop().is_running())
                            print("[DEBUG] ========================================")
                            
                            print("[DEBUG] Importing MinimalGUI...")
                            try:
                                from ui.minimal_gui import MinimalGUI
                                print("[DEBUG] MinimalGUI imported successfully")
                            except ImportError as e:
                                error_msg = f"Failed to import MinimalGUI: {str(e)}"
                                print(f"[DEBUG] ERROR: {error_msg}")
                                await logs_manager.error(error_msg)
                                raise
                            
                            print("[DEBUG] Creating MinimalGUI instance...")
                            try:
                                gui = MinimalGUI(controller)
                                print("[DEBUG] MinimalGUI instance created successfully")
                            except Exception as e:
                                error_msg = f"Failed to create MinimalGUI instance: {str(e)}"
                                print(f"[DEBUG] ERROR: {error_msg}")
                                await logs_manager.error(error_msg)
                                raise
                            
                            print("[DEBUG] 3. MinimalGUI instance created successfully")
                            print("[DEBUG] 4. About to call gui.run_app()")
                            print("[DEBUG] - GUI window exists:", gui.window.winfo_exists() if hasattr(gui, 'window') else "No window")
                            print("[DEBUG] - GUI window is mapped:", gui.window.winfo_ismapped() if hasattr(gui, 'window') else "No window")
                            print("[DEBUG] - GUI window geometry:", gui.window.geometry() if hasattr(gui, 'window') else "No window")
                            print("[DEBUG] ========================================")
                            
                            gui.run_app()  # This should block until GUI is closed
                            
                            print("[DEBUG] 5. gui.run_app() has returned")
                            print("[DEBUG] 6. GUI Mode completed successfully")
                            print("[DEBUG] ========================================")
                            
                            await logs_manager.info("GUI Mode completed successfully")
                        except Exception as e:
                            error_msg = f"Error in GUI mode: {str(e)}"
                            print(f"[DEBUG] ERROR: {error_msg}")
                            print("[DEBUG] Exception details:")
                            print(f"[DEBUG] - Type: {type(e).__name__}")
                            print(f"[DEBUG] - Module: {type(e).__module__}")
                            print(f"[DEBUG] - Thread: {threading.current_thread().name}")
                            print(f"[DEBUG] - Traceback:", e.__traceback__)
                            print("[DEBUG] ========================================")
                            await logs_manager.error(error_msg)
                            raise
                        
                    success = True
                    await logs_manager.info("Mode execution completed successfully")
                    
                except asyncio.CancelledError:
                    await logs_manager.warning("Mode execution was cancelled")
                    raise
                except Exception as e:
                    await logs_manager.error(f"Error during mode execution: {str(e)}")
                    retry = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: input("\nWould you like to try another mode? (y/n): ").strip().lower()
                    )
                    if retry != 'y':
                        await logs_manager.info("User chose not to retry after error")
                        break
                finally:
                    # End session after mode completes or fails
                    await logs_manager.info("Ending controller session...")
                    await controller.end_session()
                    
                if success:
                    await logs_manager.info("Mode completed successfully")
                    retry = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: input("\nWould you like to run another mode? (y/n): ").strip().lower()
                    )
                    if retry != 'y':
                        await logs_manager.info("User chose to exit after successful execution")
                        break
            else:
                await logs_manager.warning(f"Invalid mode choice: {mode_choice}")
                print("Invalid choice. Please select 1-4.")
        except Exception as e:
            await logs_manager.error(f"Error displaying mode selection menu: {str(e)}")
            continue

async def run_automatic_mode(controller: Controller, logs_manager: LogsManager):
    """Automatic Mode - self-runs until completion."""
    await logs_manager.info("[Automatic Mode Selected]")
    
    await debug_sleep.sleep(TimingConstants.ACTION_DELAY, "Initial delay before automatic mode tasks")

    # Example: applying to some job
    job_title = "Software Engineer"
    location = "Remote"
    await logs_manager.info(f"Applying for {job_title} in {location}...")
    await controller.run_linkedin_flow(job_title, location)

    await debug_sleep.sleep(TimingConstants.ACTION_DELAY, "Final delay after automatic mode tasks")
    await logs_manager.info("[Automatic] Finished tasks")

async def run_full_control_mode(controller: Controller, logs_manager: LogsManager):
    """
    Full Control Mode:
    - Launches the CLI where the user can type commands step by step.
    """
    await logs_manager.info("[Full Control Mode Selected]")
    await debug_sleep.sleep(TimingConstants.ACTION_DELAY, "Initial delay before CLI mode")
    cli = CLI(controller, logs_manager)
    cli.start()  # typically calls cmdloop() internally
    await logs_manager.info("[Full Control Mode] CLI ended. Returning to main.")

def run_gui_mode(controller: Controller):
    """
    GUI Mode:
    - Opens a minimal window with start/resume/pause/stop + text input
    - Blocks until user closes the GUI
    - Handles cleanup properly
    """
    try:
        # TODO: Move to logs_manager once GUI initialization is complete
        print(">>> Entered run_gui_mode function")
        print(">>> Current thread:", threading.current_thread().name)
        print(">>> Main thread:", threading.main_thread().name)
        print(">>> Is main thread:", threading.current_thread() is threading.main_thread())
        
        # TODO: Move to logs_manager once GUI initialization is complete
        print("\n[GUI Mode Selected]")
        
        if sys.platform == 'win32':
            # TODO: Move to logs_manager once GUI initialization is complete
            print("[GUI Debug] Setting WindowsSelectorEventLoopPolicy...")
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # TODO: Move to logs_manager once GUI initialization is complete
        print(">>> About to create MinimalGUI instance...")
        print("[GUI Debug] Instantiating MinimalGUI...")
        gui = MinimalGUI(controller)
        
        # TODO: Move to logs_manager once GUI initialization is complete
        print(">>> MinimalGUI instance created. Now calling run_app()...")
        print(">>> This call should block until the GUI is closed...")
        print("[GUI Debug] Calling gui.run_app() (blocking call)...")
        gui.run_app()  # blocks until GUI is closed
        
        # If we reach here, the GUI was properly closed
        # TODO: Move to logs_manager if async_loop is still available
        print(">>> run_app() has returned normally - GUI was closed properly")
        print("[GUI Debug] gui.run_app() returned normally (GUI closed).")
        
    except KeyboardInterrupt:
        # Keep this print since it's a critical user-facing message
        print("\n[GUI Mode] Received interrupt signal, shutting down...")
    except Exception as e:
        # Keep this print since it's a critical error message
        print(f"\n[GUI Mode] Error: {str(e)}")
        raise
    finally:
        # Keep this print since it's a critical shutdown message
        print("\n[GUI Mode] GUI closed. Returning to main.")
        print(">>> Exiting run_gui_mode function")

async def main():
    """
    Main entry point that runs the async_main logic with proper task handling.
    """
    try:
        await async_main()
    except KeyboardInterrupt:
        print("\nUser pressed Ctrl+C. Initiating graceful shutdown...")
    except Exception as e:
        print(f"Unexpected error in main: {str(e)}")
    finally:
        print("\nCleaning up resources...")
        try:
            # Get all tasks except the current one
            pending_tasks = [t for t in asyncio.all_tasks() 
                           if t is not asyncio.current_task()]
            
            if pending_tasks:
                # Cancel all pending tasks
                for task in pending_tasks:
                    task.cancel()
                
                # Wait for all tasks to complete their cancellation
                try:
                    await asyncio.gather(*pending_tasks, return_exceptions=True)
                except asyncio.CancelledError:
                    pass  # This is expected during cleanup
                
            # Final delay to ensure cleanup
            await debug_sleep.sleep(0.1, "Final cleanup delay")
            print("Cleanup complete.")
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
