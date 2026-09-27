"""Offline controller integration against real component wiring."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from orchestrator.controller import Controller


@pytest.fixture
def controller(tmp_path):
    settings = {
        'system': {'data_dir': str(tmp_path)},
        'data_dir': str(tmp_path),
        'telemetry': {'enabled': False, 'storage_path': str(tmp_path / 'telemetry')},
    }
    logs = SimpleNamespace(**{name: AsyncMock() for name in
                             ('info', 'debug', 'warning', 'error', 'initialize', 'shutdown')})
    ctrl = Controller(settings, page=SimpleNamespace(url='https://www.linkedin.com/jobs/'),
                      logs_manager=logs)
    ctrl.tracker_agent.log_activity = AsyncMock()
    return ctrl


@pytest.mark.asyncio
async def test_start_session_uses_shared_logger_and_records_session(controller):
    await controller.start_session()
    controller.logs_manager.initialize.assert_not_awaited()
    controller.tracker_agent.log_activity.assert_awaited_once_with(
        activity_type='session', details='Session started', status='success',
        agent_name='Controller',
    )
    assert controller.credentials_agent.dom_service is controller.dom_service


@pytest.mark.asyncio
async def test_run_linkedin_flow_calls_full_search_and_passes_parameters(controller):
    controller.linkedin_agent.search_jobs_and_apply = AsyncMock(return_value=None)
    await controller.run_linkedin_flow('Software Engineer', 'Test City')
    controller.linkedin_agent.search_jobs_and_apply.assert_awaited_once_with(
        'Software Engineer', 'Test City')
    assert controller.settings['job_title'] == 'Software Engineer'
    assert controller.settings['location'] == 'Test City'
    assert len(controller.task_manager.tasks) == 1
    assert next(iter(controller.task_manager.tasks.values())).status == 'completed'


@pytest.mark.asyncio
async def test_run_linkedin_flow_does_not_retry_uncertain_application_failure(controller):
    controller.linkedin_agent.search_jobs_and_apply = AsyncMock(side_effect=RuntimeError('connection lost'))
    with pytest.raises(RuntimeError, match='connection lost'):
        await controller.run_linkedin_flow('Engineer', 'Remote')
    controller.linkedin_agent.search_jobs_and_apply.assert_awaited_once()
    assert next(iter(controller.task_manager.tasks.values())).status == 'failed'


@pytest.mark.asyncio
async def test_end_session_cancels_active_flow_and_preserves_shared_logger(controller):
    await controller.start_session()
    entered, cleaned = asyncio.Event(), asyncio.Event()

    async def search(_title, _location):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    controller.linkedin_agent.search_jobs_and_apply = search
    flow = asyncio.create_task(controller.run_linkedin_flow('Engineer', 'Remote'))
    await entered.wait()
    await controller.end_session()
    assert flow.cancelled()
    assert cleaned.is_set()
    assert not controller.task_manager.active_tasks
    controller.logs_manager.shutdown.assert_not_awaited()
    assert controller.tracker_agent.log_activity.call_args.kwargs['details'] == 'Session ended'


@pytest.mark.asyncio
async def test_owned_logger_is_initialized_and_closed(tmp_path):
    ctrl = Controller({'system': {'data_dir': str(tmp_path)}, 'data_dir': str(tmp_path),
                       'telemetry': {'enabled': False, 'storage_path': str(tmp_path / 'telemetry')}})
    ctrl.logs_manager.initialize = AsyncMock()
    ctrl.logs_manager.shutdown = AsyncMock()
    ctrl.logs_manager.info = AsyncMock()
    ctrl.tracker_agent.log_activity = AsyncMock()
    await ctrl.start_session()
    await ctrl.end_session()
    ctrl.logs_manager.initialize.assert_awaited_once()
    ctrl.logs_manager.shutdown.assert_awaited_once()

@pytest.mark.asyncio
async def test_repeated_session_lifecycle_is_idempotent_and_clears_pause(controller):
    await controller.start_session()
    await controller.start_session()
    assert controller.tracker_agent.log_activity.await_count == 1
    controller._save_session_state = AsyncMock(return_value=True)
    await controller.pause_session()
    assert controller.linkedin_agent.is_paused
    await controller.end_session()
    ended_count = controller.tracker_agent.log_activity.await_count
    await controller.end_session()
    assert controller.tracker_agent.log_activity.await_count == ended_count
    await controller.start_session()
    assert not controller.linkedin_agent.is_paused
    assert controller._resume_event.is_set()
    await controller.end_session()


@pytest.mark.asyncio
async def test_job_flow_does_not_inherit_short_generic_task_deadline(controller):
    controller.task_manager.task_timeout = 0.001

    async def search(_title, _location):
        await asyncio.sleep(0.01)
        return 'done'

    controller.linkedin_agent.search_jobs_and_apply = search
    assert await controller.run_linkedin_flow('Engineer', 'Remote') == 'done'
    controller.settings['job_search_timeout_seconds'] = 0.001
    with pytest.raises(asyncio.TimeoutError):
        await controller.run_linkedin_flow('Engineer', 'Remote')
