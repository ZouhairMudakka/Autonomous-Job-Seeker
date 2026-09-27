"""Application entry point. Browser operations stay on one asyncio event loop."""

import asyncio
import sys

from config.settings import load_settings
from orchestrator.controller import Controller
from storage.logs_manager import LogsManager
from ui.cli import CLI
from utils.browser_setup import BrowserSetup
from utils.telemetry import TelemetryManager
from utils.console_input import async_input


async def read_input(prompt):
    return (await async_input(prompt)).strip()


async def async_main():
    settings = load_settings()
    telemetry = TelemetryManager(settings)
    logs = LogsManager(settings, telemetry)
    browser_setup = None
    browser = page = controller = None
    try:
        await logs.initialize()
        browser_setup = BrowserSetup(settings, logs)
        browser, page = await browser_setup.initialize(
            attach_existing=settings.get("browser", {}).get("attach_existing", False)
        )
        controller = Controller(settings=settings, page=page, logs_manager=logs)
        await run_selected_mode(controller, logs)
    finally:
        # Each cleanup runs even when a preceding resource fails to close.
        try:
            if controller is not None:
                await controller.end_session()
        finally:
            try:
                if browser_setup is not None:
                    await browser_setup.cleanup(browser, page)
            finally:
                await logs.shutdown()


async def run_selected_mode(controller, logs_manager):
    while True:
        print("\n1) Automatic mode\n2) Interactive CLI\n3) GUI\n4) Exit")
        try:
            choice = await read_input("Select mode (1-4): ")
        except EOFError:
            return
        if choice == "4":
            return
        if choice not in {"1", "2", "3"}:
            print("Invalid choice. Please select 1-4.")
            continue
        try:
            await controller.start_session()
            if choice == "1":
                await run_automatic_mode(controller, logs_manager)
            elif choice == "2":
                await run_full_control_mode(controller, logs_manager)
            else:
                await run_gui_mode(controller)
        except EOFError:
            return
        except Exception as exc:
            await logs_manager.error(f"Mode failed: {exc}")
        finally:
            await controller.end_session()


async def run_automatic_mode(controller, logs_manager):
    """Use explicitly supplied search criteria, never hard-coded applications."""
    job_title = controller.settings.get("job_title") or await read_input("Job title: ")
    location = controller.settings.get("location") or await read_input("Location: ")
    if not job_title.strip() or not location.strip():
        raise ValueError("A job title and location are required")
    await controller.run_linkedin_flow(job_title.strip(), location.strip())


async def run_full_control_mode(controller, logs_manager):
    await CLI(controller).start()


async def run_gui_mode(controller):
    # CLI and automated runs must not require Tk or GUI dependencies.
    from ui.minimal_gui import MinimalGUI

    await MinimalGUI(controller).run_app()


async def main():
    await async_main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as exc:
        print(f"Application failed: {exc}", file=sys.stderr)
        sys.exit(1)
