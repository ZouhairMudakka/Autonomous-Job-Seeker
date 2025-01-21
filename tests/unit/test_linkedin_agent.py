"""
Unit Tests for LinkedIn Agent (Async, Playwright-based)

Tests the functionality of the LinkedInAgent class by mocking Playwright calls.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from agents.linkedin_agent import LinkedInAgent
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

@pytest.mark.asyncio
@pytest.fixture
async def mock_page():
    """
    A fixture that returns an AsyncMock simulating a Playwright 'Page'.
    """
    page = AsyncMock(spec=Page)
    return page

@pytest.mark.asyncio
@pytest.fixture
async def agent(mock_page):
    """
    Creates a LinkedInAgent with a mocked Page for testing.
    """
    # Minimally, we pass the page. The rest are defaults for timing.
    ag = LinkedInAgent(
        page=mock_page,
        default_timeout=5000,
        min_delay=0.2,
        max_delay=0.5
    )
    return ag

@pytest.mark.asyncio
async def test_initialization(agent):
    """
    Test that the agent is correctly initialized.
    """
    assert agent.page is not None
    assert agent.default_timeout == 5000
    assert agent.min_delay == 0.2
    assert agent.max_delay == 0.5

@pytest.mark.asyncio
async def test_go_to_jobs_tab_success(agent):
    """
    Tests that go_to_jobs_tab clicks the 'Jobs' link if present.
    """
    # Mock the wait_for_selector and click calls to simulate a success scenario
    agent.page.wait_for_selector.return_value = True  # no exception
    await agent.go_to_jobs_tab()

    agent.page.wait_for_selector.assert_awaited_once_with(
        'a[data-control-name="nav_jobs"]',
        timeout=agent.default_timeout
    )
    agent.page.click.assert_awaited_once_with('a[data-control-name="nav_jobs"]')

@pytest.mark.asyncio
async def test_go_to_jobs_tab_fallback(agent):
    """
    Tests fallback scenario if the direct 'Jobs' link is not found initially.
    """
    # First call triggers TimeoutError
    agent.page.wait_for_selector.side_effect = [PlaywrightTimeoutError("not found"), True]
    # Then we simulate the fallback magnifier approach
    agent.page.query_selector.return_value = AsyncMock()  # magnifier found
    await agent.go_to_jobs_tab()

    # We confirm we called fallback approach
    # The second wait_for_selector call should succeed
    assert agent.page.wait_for_selector.call_count == 2
    assert agent.page.click.call_count == 2  # one for magnifier, one for 'Jobs' link

@pytest.mark.asyncio
async def test_search_jobs_basic(agent):
    """
    Tests a basic job search flow.
    """
    await agent.search_jobs("Software Engineer", "Remote")
    # We expect the agent to fill text fields, press Enter, and wait a bit
    # Checking page interactions
    fill_calls = [
        call.args for call in agent.page.fill.await_args_list
    ]
    # Expect two fills: job title, location
    assert len(fill_calls) == 2
    assert fill_calls[0] == ('input[aria-label="Search by title, skill, or company"]', 'Software Engineer')
    assert fill_calls[1] == ('input[aria-label="City, state, or zip code"]', 'Remote')

    # Check we pressed Enter on keyboard
    agent.page.keyboard.press.assert_awaited_with("Enter")

@pytest.mark.asyncio
async def test_check_captcha_or_logout_captcha_detected(agent):
    """
    If a captcha image is present, we expect an Exception to be raised.
    """
    # Mock: we found an element for captcha
    agent.page.query_selector.return_value = AsyncMock()
    with pytest.raises(Exception) as excinfo:
        await agent.check_captcha_or_logout()
    assert "Captcha encountered" in str(excinfo.value)

@pytest.mark.asyncio
async def test_check_captcha_or_logout_logged_out(agent):
    """
    If sign_in_btn is present, we raise logout exception.
    """
    # First call for captcha, second for sign in
    agent.page.query_selector.side_effect = [None, AsyncMock()]
    with pytest.raises(Exception) as excinfo:
        await agent.check_captcha_or_logout()
    assert "Looks like we got logged out" in str(excinfo.value)

@pytest.mark.asyncio
async def test_handle_easy_apply(agent):
    """
    Ensure handle_easy_apply tries to click the easy apply button, 
    and calls multi-step logic. We'll patch the multi-step method.
    """
    with patch.object(agent, '_multi_step_easy_apply', new_callable=AsyncMock) as mock_multi:
        mock_multi.return_value = "applied"
        result = await agent._handle_easy_apply()
        assert result == "applied"
        agent.page.click.assert_awaited_once()
        mock_multi.assert_awaited_once()

@pytest.mark.asyncio
async def test_apply_external(agent):
    """
    Tests _handle_external_apply. We simulate a new tab popup.
    """
    apply_button_mock = AsyncMock()
    # Suppose new tab is triggered
    new_page_mock = AsyncMock()
    agent.page.wait_for_event.return_value = asyncio.Future()
    agent.page.wait_for_event.return_value.set_result(new_page_mock)

    result = await agent._handle_external_apply(apply_button_mock)
    assert result == "redirected"
    apply_button_mock.click.assert_awaited_once()
    new_page_mock.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_missing_elements(agent):
    """
    Ensures we attempt a reload when missing elements.
    """
    await agent._handle_missing_elements()
    agent.page.reload.assert_awaited_once()

@pytest.mark.asyncio
async def test_safe_get_text(agent):
    """
    Test that _safe_get_text returns stripped text or empty string on failures.
    """
    # mock a found element
    mock_elem = AsyncMock()
    mock_elem.text_content.return_value = "  Some Text\n"
    agent.page.query_selector.return_value = mock_elem
    txt = await agent._safe_get_text("test_selector")
    assert txt == "Some Text"

    # Now no element found
    agent.page.query_selector.return_value = None
    txt2 = await agent._safe_get_text("test_selector")
    assert txt2 == ""

@pytest.mark.asyncio
async def test_human_delay(agent):
    """
    We won't verify the actual sleep time, but ensure it doesn't raise errors.
    """
    await agent._human_delay()
    # Possibly check coverage or time, but in unit tests we typically skip.
    assert True
