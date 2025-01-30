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
- Implement advanced resume parsing and customization
- Add automated interview preparation features
- Develop job market analysis capabilities
"""

import sys
import asyncio
from config.settings import load_settings
from orchestrator.controller import Controller
from ui.cli import CLI
from storage.logs_manager import LogsManager
from ui.minimal_gui import MinimalGUI
from utils.browser_setup import BrowserSetup
from constants import TimingConstants, Messages

async def async_main():
    """
    The main async function with proper error handling and resource management.
    """
    browser = None
    page = None
    logs_manager = None
    controller = None
    browser_setup = None

    try:
        # 1) Load configuration
        settings = load_settings()
        
        # 2) Initialize logs with proper cleanup handling
        logs_manager = LogsManager(settings)
        await logs_manager.initialize()
        await logs_manager.info("Starting AI-Powered Job Application System...")
        await logs_manager.info("Configuration loaded successfully")

        # 3) Browser setup with proper error handling
        await logs_manager.info("Initializing browser setup...")
        browser_setup = BrowserSetup(settings, logs_manager)
        try:
            browser, page = await browser_setup.initialize(
                attach_existing=settings['browser'].get('attach_existing', False)
            )
            await logs_manager.info("Browser initialization completed successfully")
        except Exception as e:
            await logs_manager.error(f"Failed to initialize browser: {str(e)}")
            if logs_manager:
                await logs_manager.shutdown()
            return

        # 4) Create controller (but don't start session yet)
        await logs_manager.info("Creating application controller...")
        controller = Controller(settings, page)
        await logs_manager.info("Controller created successfully")
        
        # 5) Run selected mode (session handled within modes)
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
                await logs_manager.error(f"Error during controller cleanup: {str(e)}")

        if browser and page:
            try:
                if browser_setup:
                    await logs_manager.info("Cleaning up browser resources...")
                    await browser_setup.cleanup(browser, page)
                    await logs_manager.info("Browser cleanup completed")
            except Exception as e:
                await logs_manager.error(f"Error during browser cleanup: {str(e)}")

        if logs_manager:
            try:
                await logs_manager.info("Shutting down logging system...")
                await logs_manager.shutdown()
            except Exception as e:
                # Can't log this through logs_manager since we're shutting it down
                print(f"Error during logs cleanup: {e}")

async def run_selected_mode(controller: Controller, logs_manager: LogsManager):
    """Handle mode selection and execution with proper error handling."""
    while True:
        try:
            await logs_manager.info("Prompting user for operation mode selection")
            
            # Display menu to user (keep prints for UI)
            print("\nOperation Mode:")
            print("1) Automatic Mode (autopilot)")
            print("2) Full Control Mode (interactive CLI)")
            print("3) GUI Mode")
            print("4) Exit")
            
            # Use async input
            mode_choice = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("\nSelect mode (1-4): ").strip()
            )
            
            if mode_choice == '4':
                await logs_manager.info("User selected to exit the application")
                break
                
            if mode_choice in ['1', '2', '3']:
                success = False
                try:
                    # Start session before running mode
                    await logs_manager.info("Starting controller session...")
                    await controller.start_session()
                    
                    if mode_choice == '1':
                        await logs_manager.info("Starting Automatic Mode...")
                        await run_automatic_mode(controller, logs_manager)
                    elif mode_choice == '2':
                        await logs_manager.info("Starting Full Control Mode...")
                        await run_full_control_mode(controller, logs_manager)
                    else:  # mode_choice == '3'
                        await logs_manager.info("Starting GUI Mode...")
                        await asyncio.to_thread(run_gui_mode, controller)
                        
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
                
        except asyncio.CancelledError:
            await logs_manager.warning("Mode selection was cancelled")
            raise
        except Exception as e:
            await logs_manager.error(f"Error in mode selection: {str(e)}")
            await logs_manager.info("Please try again")

async def run_automatic_mode(controller: Controller, logs_manager: LogsManager):
    """Automatic Mode - self-runs until completion."""
    await logs_manager.info("[Automatic Mode Selected]")
    
    await asyncio.sleep(TimingConstants.ACTION_DELAY)

    # Example: applying to some job
    job_title = "Software Engineer"
    location = "Remote"
    await logs_manager.info(f"Applying for {job_title} in {location}...")
    await controller.run_linkedin_flow(job_title, location)

    await asyncio.sleep(TimingConstants.ACTION_DELAY)
    await logs_manager.info("[Automatic] Finished tasks")

async def run_full_control_mode(controller: Controller, logs_manager: LogsManager):
    """
    Full Control Mode:
    - Launches the CLI where the user can type commands step by step.
    """
    await logs_manager.info("[Full Control Mode Selected]")
    await asyncio.sleep(TimingConstants.ACTION_DELAY)
    cli = CLI(controller, logs_manager)
    cli.start()  # typically calls cmdloop() internally
    await logs_manager.info("[Full Control Mode] CLI ended. Returning to main.")

def run_gui_mode(controller: Controller):
    """
    GUI Mode:
    - Opens a minimal window with start/resume/pause/stop + text input
    - Blocks until user closes the GUI
    """
    # Note: Since this is synchronous and GUI-specific, we keep print statements here
    print("\n[GUI Mode Selected]")
    gui = MinimalGUI(controller)
    gui.run_app()  # blocks until GUI is closed
    print("\n[GUI Mode] GUI closed. Returning to main.")

async def main():
    """
    Main entry point that runs the async_main logic with proper task handling.
    """
    try:
        await async_main()
    except KeyboardInterrupt:
        # We don't have logs_manager here, so we keep this print
        print("\nUser pressed Ctrl+C. Initiating graceful shutdown...")
    except Exception as e:
        # We don't have logs_manager here, so we keep this print
        print(f"Unexpected error in main: {str(e)}")
    finally:
        print("\nCleaning up resources...")
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
        await asyncio.sleep(0.1)
        print("Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(main())
