"""
Integration Tests for Controller

Tests the interaction between the async controller and its agents.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch

# If your orchestrator.controller is async-based
from orchestrator.controller import Controller

# We assume you have "pytest-asyncio" installed if we do async tests
@pytest.mark.asyncio
@pytest.fixture
async def controller():
    """
    Creates a Controller instance with test settings, optionally does any async init if needed.
    """
    settings = {
        'linkedin': {
            'email': 'test@example.com',
            'password': 'test_password'
        },
        'data_dir': 'tests/fixtures/data',  # Test-only directory
        'log_level': 'DEBUG'
    }
    # Create controller instance
    ctrl = Controller(settings)
    # If controller has an async init method, you could do:
    # await ctrl.some_async_init()
    return ctrl

@pytest.mark.asyncio
async def test_start_session(controller):
    """
    Tests that starting a session logs the right tracker activity.
    """
    # Mock out tracker to ensure we can verify calls
    with patch.object(controller.tracker_agent, 'log_activity', new_callable=MagicMock) as mock_log:
        await controller.start_session()  # call the async version

        # Ensure log_activity was called
        mock_log.assert_awaited()
        # Optionally check the exact call details
        call_args = mock_log.call_args_list[0][0]  # first call's positional args
        call_kwargs = mock_log.call_args_list[0][1]  # first call's keyword args

        # Validate we see 'Session started'
        assert 'Session started' in call_kwargs['details']
        assert call_kwargs['activity_type'] == 'session'
        assert call_kwargs['status'] == 'success'

@pytest.mark.asyncio
async def test_run_linkedin_flow(controller):
    """
    Example test to see if run_linkedin_flow method attempts a search/apply.
    We patch the LinkedInAgent to avoid real network calls.
    """
    with patch.object(controller.linkedin_agent, 'search_jobs_and_apply', new_callable=MagicMock) as mock_search:
        # Also patch tracker
        with patch.object(controller.tracker_agent, 'log_activity', new_callable=MagicMock) as mock_log:
            await controller.run_linkedin_flow("Software Engineer", "Test City")

            # Check the agent was called
            mock_search.assert_awaited_once_with("Software Engineer", "Test City")

            # Check logging
            mock_log.assert_awaited()
            # You can check specific call details if desired

@pytest.mark.asyncio
async def test_end_session(controller):
    """
    Verifies we can end a session properly.
    """
    with patch.object(controller.tracker_agent, 'log_activity', new_callable=MagicMock) as mock_log:
        await controller.end_session()

        # Check tracker log call for session ended
        assert mock_log.await_count == 1
        args, kwargs = mock_log.call_args
        assert 'Session ended' in kwargs['details']
        assert kwargs['status'] == 'success'
