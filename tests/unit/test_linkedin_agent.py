"""Offline tests for the current Playwright LinkedIn agent contract."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import pytest
from agents.linkedin_agent import LinkedInAgent
from constants import TimingConstants

@pytest.fixture
def agent(monkeypatch):
    for name in ('MODAL_TRANSITION_DELAY', 'EASY_APPLY_MODAL_DELAY', 'PAGE_TRANSITION_DELAY'):
        monkeypatch.setattr(TimingConstants, name, 0)
    page = AsyncMock()
    page.url = 'https://www.linkedin.com/feed/'
    controller = SimpleNamespace(settings={}, logs_manager=AsyncMock(), tracker_agent=AsyncMock())
    agent = LinkedInAgent(page, controller, default_timeout=5000, min_delay=0.2, max_delay=0.5)
    agent._human_delay = AsyncMock()
    return agent


def test_initialization(agent):
    assert agent.default_timeout == 5000
    assert agent.min_delay == 0.2
    assert agent.max_delay == 0.5
    assert agent.dom_service.page is agent.page


@pytest.mark.asyncio
async def test_go_to_jobs_tab_success(agent):
    button = AsyncMock()
    agent.page.query_selector.return_value = button
    async def click():
        agent.page.url = 'https://www.linkedin.com/jobs/'
    button.click.side_effect = click
    assert await agent.go_to_jobs_tab()
    button.click.assert_awaited_once()
    agent.page.goto.assert_not_awaited()


@pytest.mark.asyncio
async def test_go_to_jobs_tab_fallback(agent):
    agent.page.query_selector.return_value = None
    async def navigate(url, **kwargs):
        agent.page.url = url
    agent.page.goto.side_effect = navigate
    assert await agent.go_to_jobs_tab()
    agent.page.goto.assert_awaited_once_with('https://www.linkedin.com/jobs/', timeout=30000)


@pytest.mark.asyncio
async def test_check_captcha_detected(agent):
    agent._verify_login_state = AsyncMock(return_value=True)
    agent.page.query_selector.return_value = AsyncMock()
    with pytest.raises(Exception, match='Captcha encountered'):
        await agent.check_captcha_or_logout()


@pytest.mark.asyncio
async def test_check_logged_out(agent):
    agent._verify_login_state = AsyncMock(return_value=False)
    with pytest.raises(Exception, match='logged out'):
        await agent.check_captcha_or_logout()


@pytest.mark.asyncio
async def test_easy_apply_uses_form_agent_result(agent):
    agent.form_filler_agent = AsyncMock()
    agent.form_filler_agent.fill_easy_apply.return_value = 'failed'
    assert await agent._handle_easy_apply() == 'failed'
    agent.form_filler_agent.fill_easy_apply.assert_awaited_once_with({})


@pytest.mark.asyncio
async def test_external_apply_popup_is_closed(agent):
    popup = AsyncMock()
    callbacks = {}
    agent.page.on = MagicMock(side_effect=lambda event, callback: callbacks.update({event: callback}))
    agent.page.remove_listener = MagicMock()
    button = AsyncMock()
    async def click():
        callbacks['popup'](popup)
    button.click.side_effect = click
    assert await agent._handle_external_apply(button) == 'redirected'
    popup.close.assert_awaited_once()
    agent.page.remove_listener.assert_called_once()
    agent.page.go_back.assert_not_awaited()


@pytest.mark.asyncio
async def test_external_apply_same_tab_restores_results(agent):
    agent.page.on = MagicMock()
    agent.page.remove_listener = MagicMock()
    button = AsyncMock()
    async def click():
        agent.page.url = 'https://jobs.example/application'
    button.click.side_effect = click
    assert await agent._handle_external_apply(button) == 'redirected'
    agent.page.go_back.assert_awaited_once_with(timeout=agent.default_timeout)


@pytest.mark.asyncio
async def test_safe_get_text_supports_card_root(agent):
    card = AsyncMock()
    card.query_selector.return_value.text_content.return_value = '  Engineer  '
    assert await agent._safe_get_text('h3', card) == 'Engineer'
    agent.page.query_selector.assert_not_awaited()
    card.query_selector.return_value = None
    assert await agent._safe_get_text('h3', card) == ''


@pytest.mark.asyncio
async def test_application_delegates_cv_and_answers(agent):
    agent.settings.update({'cv_path': 'resume.pdf', 'form_data': {'phone': '123'}})
    agent.form_filler_agent = AsyncMock()
    agent.form_filler_agent.fill_easy_apply.return_value = 'skipped'
    assert await agent._multi_step_easy_apply() == 'skipped'
    agent.form_filler_agent.fill_easy_apply.assert_awaited_once_with({'cv_path': 'resume.pdf', 'phone': '123'})
