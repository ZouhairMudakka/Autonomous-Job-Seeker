"""Opt-in live browser/provider smoke test: pytest --run-live tests/test_dom_features.py.

LIVE_BROWSER, LIVE_DOM_URL and VISION_MODEL can override the demo defaults.
This test visits a public page, captures it, and sends that image to the selected
model provider. It requires a browser installation and the provider API key.
"""

import os
import pytest

from storage.logs_manager import LogsManager
from utils.browser_setup import BrowserSetup
from utils.dom.dom_service import DomService
from utils.model_selector import ModelSelector


@pytest.mark.live
@pytest.mark.asyncio
async def test_dom_features_with_vision(tmp_path):
    settings = {
        'browser': {
            'headless': True,
            'type': os.getenv('LIVE_BROWSER', 'chrome'),
            'data_dir': str(tmp_path),
            'viewport': {'width': 1280, 'height': 720},
            'should_prompt': False,
        },
        'system': {'data_dir': str(tmp_path), 'log_level': 'DEBUG'},
        'telemetry': {'enabled': False},
    }
    logs_manager = LogsManager(settings)
    browser_setup = None
    browser_or_context = page = None
    try:
        await logs_manager.initialize()
        browser_setup = BrowserSetup(settings, logs_manager)
        browser_or_context, page = await browser_setup.initialize()
        await page.goto(os.getenv('LIVE_DOM_URL', 'https://www.linkedin.com'), wait_until='domcontentloaded')
        dom = DomService(page, telemetry=browser_setup.telemetry, logs_manager=logs_manager)
        first = await dom.get_clickable_elements(highlight=True, max_highlight=75)
        second = await dom.get_clickable_elements(highlight=True, max_highlight=75)
        assert isinstance(first, list) and isinstance(second, list)
        image_data = await page.screenshot()
        selector = ModelSelector(logs_manager=logs_manager)
        await selector.initialize()
        response = await selector.vision_completion(
            model=os.getenv('VISION_MODEL', 'gpt-4o-mini'),
            image=image_data,
            prompt='Describe the visible page layout, highlighted overlays and clickable elements.',
        )
        assert isinstance(response, str) and response.strip(), 'Vision provider returned no content'
        await logs_manager.info('Live DOM and vision smoke test passed; provider cost was not measured')
    finally:
        try:
            if browser_setup is not None:
                await browser_setup.cleanup(browser_or_context, page)
        finally:
            await logs_manager.shutdown()
