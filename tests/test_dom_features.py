"""Test DOM Service Features"""

import asyncio
from utils.browser_setup import BrowserSetup
from utils.dom.dom_service import DomService

async def test_dom_features():
    # Initialize browser
    settings = {
        'browser': {
            'headless': False,
            'type': 'chrome',
            'data_dir': './data',
            'viewport': {'width': 1280, 'height': 720},
            'should_prompt': False
        },
        'system': {
            'data_dir': './data'
        }
    }
    
    browser_setup = BrowserSetup(settings)
    browser_or_context, page = await browser_setup.initialize()
    
    try:
        # Navigate to test page
        await page.goto('https://www.linkedin.com')
        
        # Initialize DOM service
        dom_svc = DomService(page, telemetry=browser_setup.telemetry)
        
        # Single shot test
        print("\nTesting single shot highlighting...")
        clickable_elems = await dom_svc.get_clickable_elements(highlight=True, max_highlight=75)
        print(f"\nFound {len(clickable_elems)} clickable elements. First 5:")
        for elem in clickable_elems[:5]:
            print(f" - {elem.tag} (highlight #{elem.highlight_index})")
            print(f"   Attributes: {elem.attributes}")
        
        # Auto-refresh test
        print("\nTesting auto-refresh (2s intervals, 3 iterations)...")
        await dom_svc.refresh_highlights(interval_sec=2, iterations=3)
        
        # Wait to see final result
        print("\nWaiting 5 seconds to view final state...")
        await asyncio.sleep(5)
        
    finally:
        await browser_setup.cleanup(browser_or_context, page)

if __name__ == "__main__":
    asyncio.run(test_dom_features()) 