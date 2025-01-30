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

        # 3) Browser setup with proper error handling
        browser_setup = BrowserSetup(settings)
        try:
            browser, page = await browser_setup.initialize(
                attach_existing=settings['browser'].get('attach_existing', False)
            )
        except Exception as e:
            print(f"Failed to initialize browser: {e}")
            if logs_manager:
                await logs_manager.shutdown()
            return

        # 4) Create controller (but don't start session yet)
        controller = Controller(settings, page)
        
        # 5) Run selected mode (session handled within modes)
        await run_selected_mode(controller)

    except Exception as e:
        print(f"Error in async_main: {str(e)}")
    finally:
        # Cleanup in reverse order of creation
        if controller:
            try:
                await controller.end_session()
            except Exception as e:
                print(f"Error during controller cleanup: {e}")

        if browser and page:
            try:
                if browser_setup:
                    await browser_setup.cleanup(browser, page)
            except Exception as e:
                print(f"Error during browser cleanup: {e}")

        if logs_manager:
            try:
                await logs_manager.shutdown()
            except Exception as e:
                print(f"Error during logs cleanup: {e}")

async def run_selected_mode(controller: Controller):
    """Handle mode selection and execution with proper error handling."""
    while True:
        try:
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
                print("\nExiting...")
                break
                
            if mode_choice in ['1', '2', '3']:
                success = False
                try:
                    # Start session before running mode
                    await controller.start_session()
                    
                    if mode_choice == '1':
                        await run_automatic_mode(controller)
                    elif mode_choice == '2':
                        await run_full_control_mode(controller)
                    else:  # mode_choice == '3'
                        await asyncio.to_thread(run_gui_mode, controller)
                        
                    success = True
                    
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print(f"\nError during mode execution: {e}")
                    retry = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: input("\nWould you like to try another mode? (y/n): ").strip().lower()
                    )
                    if retry != 'y':
                        break
                finally:
                    # End session after mode completes or fails
                    await controller.end_session()
                    
                if success:
                    print("\nMode completed successfully.")
                    retry = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: input("\nWould you like to run another mode? (y/n): ").strip().lower()
                    )
                    if retry != 'y':
                        break
            else:
                print("Invalid choice. Please try again.")
                
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Error in mode selection: {e}")
            print("Please try again.")

async def run_automatic_mode(controller: Controller):
    """Automatic Mode - self-runs until completion."""
    print("\n[Automatic Mode Selected]\n")
    
    await asyncio.sleep(TimingConstants.ACTION_DELAY)

    # Example: applying to some job
    job_title = "Software Engineer"
    location = "Remote"
    print(f"\nApplying for {job_title} in {location}...\n")
    await controller.run_linkedin_flow(job_title, location)

    await asyncio.sleep(TimingConstants.ACTION_DELAY)
    print("\n[Automatic] Finished tasks.\n")

async def run_full_control_mode(controller: Controller):
    """
    Full Control Mode:
    - Launches the CLI where the user can type commands step by step.
    """
    print("\n[Full Control Mode Selected]\n")
    await asyncio.sleep(TimingConstants.ACTION_DELAY)
    cli = CLI(controller)
    cli.start()  # typically calls cmdloop() internally
    print("\n[Full Control Mode] CLI ended. Returning to main.\n")

def run_gui_mode(controller: Controller):
    """
    GUI Mode:
    - Opens a minimal window with start/resume/pause/stop + text input
    - Blocks until user closes the GUI
    """
    gui = MinimalGUI(controller)
    gui.run_app()  # blocks until GUI is closed

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
