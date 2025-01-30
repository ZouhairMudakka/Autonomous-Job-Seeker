"""
Test DOM Service Features + Vision Model Inference

1. Initialize browser in headed mode
2. Highlight elements (2 cycles)
3. Take one screenshot after second cycle
4. Process with vision model
5. End session and show cost
"""

import asyncio
from pathlib import Path
import sys
from utils.browser_setup import BrowserSetup
from utils.dom.dom_service import DomService
from utils.model_selector import ModelSelector
from storage.logs_manager import LogsManager
import pytest

@pytest.mark.asyncio
async def test_dom_features_with_vision():
    settings = {
        'browser': {
            'headless': False,
            'type': 'chrome',
            'data_dir': './data',
            'viewport': {'width': 1280, 'height': 720},
            'should_prompt': False
        },
        'system': {
            'data_dir': './data',
            'log_level': 'DEBUG'  # Enable debug logging
        }
    }

    browser_setup = BrowserSetup(settings)
    browser_or_context, page = await browser_setup.initialize()
    screenshot_file = None
    vision_cost = 0.0

    # Initialize LogsManager
    logs_manager = LogsManager(settings)
    await logs_manager.initialize()

    try:
        await page.goto('https://www.linkedin.com')
        dom_svc = DomService(page, telemetry=browser_setup.telemetry, logs_manager=logs_manager)

        # First highlight cycle
        await logs_manager.info("Starting first highlight cycle...")
        clickable_elems = await dom_svc.get_clickable_elements(highlight=True, max_highlight=75)
        await logs_manager.info(f"Found {len(clickable_elems)} clickable elements")
        await asyncio.sleep(15)  # Wait 15 seconds

        # Second highlight cycle
        await logs_manager.info("Starting second highlight cycle...")
        clickable_elems = await dom_svc.get_clickable_elements(highlight=True, max_highlight=75)
        await logs_manager.info(f"Refreshed {len(clickable_elems)} clickable elements")
        await asyncio.sleep(5)  # Brief pause before screenshot

        # Take screenshot after second cycle
        await logs_manager.info("Capturing screenshot...")
        screenshot_path = Path("./data/screenshots")
        screenshot_path.mkdir(parents=True, exist_ok=True)
        screenshot_file = screenshot_path / "vision_test_screenshot.png"
        await page.screenshot(path=str(screenshot_file))

        # Process with vision model
        model_selector = ModelSelector()
        vision_model = "google/gemini-2.0-flash-thinking"
        with open(screenshot_file, "rb") as f:
            image_data = f.read()

        # Vision prompt
        vision_prompt = """
        Please analyze this screenshot and describe:
        1. The main elements visible on the page
        2. Any highlighted or colored overlays you see
        3. The general layout and structure
        4. Any clickable elements you can identify
        """

        await logs_manager.info(f"Processing screenshot with {vision_model}...")
        await logs_manager.debug(f"Vision prompt: {vision_prompt.strip()}")
        
        try:
            response = model_selector.vision_completion(
                model=vision_model,
                image=image_data,
                prompt=vision_prompt
            )
            
            if response.startswith("Error"):
                raise Exception(response)
                
            await logs_manager.info("Vision processing completed successfully")
                
        except Exception as e:
            await logs_manager.error(f"Vision processing failed: {str(e)}")
            vision_cost = 0.0

        # Print vision model's response
        print("\n===== VISION MODEL RESPONSE =====")
        print(response)
        print("================================")

        # Calculate vision cost (placeholder)
        vision_cost = 0.05  # Example cost per vision call

        # Final viewing time
        print("\nFinal viewing period (15 seconds)...")
        await asyncio.sleep(15)

    finally:
        # Clean up
        await logs_manager.info("Cleaning up test resources...")
        if screenshot_file and screenshot_file.exists():
            screenshot_file.unlink()
        await browser_setup.cleanup(browser_or_context, page)
        await logs_manager.shutdown()
        
        # Print cost summary after cleanup
        print("\n===== SESSION SUMMARY =====")
        print(f"Screenshot saved: {screenshot_file}")
        print(f"Vision processing cost: ${vision_cost:.2f}")
        print("=========================")

if __name__ == "__main__":
    asyncio.run(test_dom_features_with_vision())
