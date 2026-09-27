"""Offline regressions for orchestration, cancellation and truthful action outcomes."""

import asyncio
import threading
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agents.ai_navigator import AINavigator, NavigationMetrics
from agents.general_agent import GeneralAgent
from async_manager.event_loop_manager import AsyncEventLoopManager
from constants import TimingConstants
from orchestrator.controller import Controller
from orchestrator.task_manager import TaskManager
from storage.learning_pipeline import LearningPipeline
from utils.confidence_scorer import ConfidenceScorer
from utils.performance_monitor import PerformanceMonitor


def logger():
    return SimpleNamespace(**{name: AsyncMock() for name in
                              ('info', 'debug', 'warning', 'error', 'initialize', 'shutdown')})


def manager():
    return TaskManager(SimpleNamespace(logs_manager=logger(),
                                      tracker_agent=SimpleNamespace(log_activity=AsyncMock())))


def navigator():
    nav = AINavigator.__new__(AINavigator)
    nav.logs_manager = logger()
    nav.page = SimpleNamespace(url='https://www.linkedin.com/jobs/')
    nav.settings = {}
    nav.metrics = NavigationMetrics()
    nav.min_confidence = 0.8
    nav.max_retries = 2
    nav.retry_count = 0
    return nav


@pytest.mark.asyncio
async def test_cancel_running_task_stops_coroutine_and_releases_slot():
    tasks = manager()
    entered, cancelled = asyncio.Event(), asyncio.Event()

    async def work():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    task = await tasks.create_task(work())
    runner = asyncio.create_task(tasks.run_task(task))
    await entered.wait()
    assert await tasks.cancel_task(task.task_id)
    with pytest.raises(asyncio.CancelledError):
        await runner
    assert cancelled.is_set()
    assert task.status == 'cancelled'
    assert not tasks.active_tasks


@pytest.mark.asyncio
async def test_pending_cancel_closes_coroutine_without_running_it():
    tasks = manager()
    work = AsyncMock()
    task = await tasks.create_task(work())
    assert await tasks.cancel_task(task.task_id)
    work.assert_not_awaited()
    with pytest.raises(ValueError, match='pending'):
        await tasks.run_task(task)


@pytest.mark.asyncio
async def test_concurrency_limit_is_preserved_for_waiting_tasks():
    tasks = manager()
    tasks.max_concurrent = 2
    active = peak = 0

    async def work():
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.005)
        active -= 1

    queued = [await tasks.create_task(work()) for _ in range(10)]
    await asyncio.gather(*(tasks.run_task(task) for task in queued))
    assert peak == 2
    assert all(task.status == 'completed' for task in queued)


@pytest.mark.asyncio
async def test_task_timeout_cancels_and_sets_terminal_state():
    tasks = manager()
    assert tasks.task_timeout == TimingConstants.TASK_TIMEOUT / 1000
    tasks.task_timeout = 0.005
    task = await tasks.create_task(asyncio.Event().wait())
    with pytest.raises(asyncio.TimeoutError):
        await tasks.run_task(task)
    assert task.status == 'timeout'
    assert task.completed_at is not None
    assert not tasks.active_tasks


@pytest.mark.asyncio
async def test_queue_initializes_processes_and_accounts_for_items():
    tasks = manager()
    tasks._execute_task = AsyncMock()
    await tasks.add_task('job_search', {'job_title': 'Engineer'})
    await tasks.start_processing()
    await asyncio.wait_for(tasks.task_queue.join(), timeout=1)
    await tasks.stop_processing()
    tasks._execute_task.assert_awaited_once()
    assert tasks.processor_task is None


def test_event_loop_shutdown_runs_finally_and_supports_restart():
    loop = AsyncEventLoopManager()
    started, cleaned = threading.Event(), threading.Event()

    async def work():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    loop.start()
    future = loop.run_coroutine(work())
    assert started.wait(2)
    loop.stop()
    assert cleaned.is_set()
    assert future.cancelled()
    assert loop.async_loop.is_closed()
    loop.start()
    assert loop.run_coroutine(asyncio.sleep(0, result=7)).result(timeout=2) == 7
    loop.stop()


@pytest.mark.asyncio
async def test_false_action_result_fails_navigation(monkeypatch):
    monkeypatch.setattr(TimingConstants, 'BASE_RETRY_DELAY', 0)
    nav = navigator()
    action = AsyncMock(return_value=False)
    success, confidence = await nav.navigate(action, {'step': 'verify_action'})
    assert not success
    assert action.await_count == 2


@pytest.mark.asyncio
async def test_retry_budget_resets_for_each_action(monkeypatch):
    monkeypatch.setattr(TimingConstants, 'BASE_RETRY_DELAY', 0)
    nav = navigator()
    first = AsyncMock(side_effect=[RuntimeError('transient'), True])
    second = AsyncMock(side_effect=[RuntimeError('transient'), True])
    assert (await nav.navigate(first, {'step': 'first'}))[0]
    assert (await nav.navigate(second, {'step': 'second'}))[0]
    assert first.await_count == second.await_count == 2


@pytest.mark.asyncio
async def test_submission_is_never_automatically_retried():
    nav = navigator()
    submit = AsyncMock(side_effect=TimeoutError('confirmation was lost'))
    assert not (await nav.navigate(submit, {'step': 'submit_application'}))[0]
    submit.assert_awaited_once()


@pytest.mark.asyncio
async def test_plan_stops_on_failed_verification():
    nav = navigator()
    nav._execute_step = AsyncMock(side_effect=[(False, 0.5), (True, 1)])
    assert not (await nav.execute_master_plan(['verify_action', 'track_application']))[0]
    nav._execute_step.assert_awaited_once_with('verify_action')
    assert nav.completed_steps == []


@pytest.mark.asyncio
async def test_application_requires_real_data_and_mapping():
    nav = navigator()
    nav.form_filler_agent = SimpleNamespace(fill_form=AsyncMock())
    with pytest.raises(ValueError, match='form_data'):
        await nav._fill_application_form()
    nav.form_filler_agent.fill_form.assert_not_awaited()
    nav.settings = {'form_data': {'full_name': 'Applicant'}, 'form_mapping': {'full_name': {'selector': '#name'}}}
    nav.form_filler_agent.fill_form.return_value = True
    await nav._fill_application_form()
    nav.form_filler_agent.fill_form.assert_awaited_once_with(
        nav.settings['form_data'], nav.settings['form_mapping'])


@pytest.mark.asyncio
async def test_required_field_validation_reads_the_input_value():
    nav = navigator()
    field = SimpleNamespace(input_value=AsyncMock(return_value=''),
                            get_attribute=AsyncMock(return_value='phone'))
    nav.dom_service = SimpleNamespace(query_selector_all=AsyncMock(return_value=[field]))
    assert not await nav._verify_form_state()


@pytest.mark.asyncio
async def test_general_navigation_timeout_is_not_success(tmp_path):
    dom = SimpleNamespace(page=Mock(), goto=AsyncMock(side_effect=asyncio.TimeoutError))
    agent = GeneralAgent(dom, logger(), min_delay=0, max_delay=0,
                         settings={'telemetry': {'enabled': False, 'storage_path': str(tmp_path)}})
    with pytest.raises(asyncio.TimeoutError):
        await agent._navigate_operation('https://example.com')


@pytest.mark.asyncio
async def test_confidence_awaits_history_and_distinguishes_all_failures(tmp_path):
    log = logger()
    pipeline = LearningPipeline(log)
    scorer = ConfidenceScorer(pipeline, log,
                              settings={'telemetry': {'enabled': False, 'storage_path': str(tmp_path)}})
    assert await scorer.compute_confidence('click') == pytest.approx(0.6)
    await pipeline.record_outcome('click', False, 0.8)
    assert await scorer.compute_confidence('click') == pytest.approx(0.3)
    assert await scorer.calculate_confidence('click') == 0


@pytest.mark.asyncio
async def test_performance_logging_cannot_mask_operation_error():
    log = logger()
    log.info.side_effect = RuntimeError('logging unavailable')
    log.error.side_effect = RuntimeError('logging unavailable')
    with pytest.raises(ValueError, match='operation failed'):
        async with PerformanceMonitor(log, 'test'):
            raise ValueError('operation failed')


def controller_stub():
    ctrl = Controller.__new__(Controller)
    ctrl.logs_manager = logger()
    ctrl.settings = {}
    ctrl.tracker_agent = SimpleNamespace(log_activity=AsyncMock(), get_recent_activities=AsyncMock(return_value=[]))
    ctrl.ai_navigator = navigator()
    ctrl._is_high_activity_period = AsyncMock(return_value=False)
    ctrl._resume_event = asyncio.Event()
    ctrl._resume_event.set()
    return ctrl


@pytest.mark.asyncio
async def test_multiple_critical_steps_keep_their_verification_order():
    ctrl = controller_stub()
    result = await ctrl._modify_plan_for_conditions(['apply', 'fill_application_form', 'submit_application'])
    assert result == ['apply', 'verify_action', 'fill_application_form', 'submit_application', 'verify_action']


@pytest.mark.asyncio
async def test_failure_after_submission_does_not_replay_plan():
    ctrl = controller_stub()
    ctrl._modify_plan_for_conditions = AsyncMock(return_value=['submit_application', 'track_application'])
    ctrl.ai_navigator.current_step = 1
    ctrl.ai_navigator.completed_steps = ['submit_application']
    ctrl.ai_navigator.execute_master_plan = AsyncMock(return_value=(False, 0.9))
    assert not await ctrl.run_master_plan(['submit_application', 'track_application'])
    ctrl.ai_navigator.execute_master_plan.assert_awaited_once()
    assert ctrl.completed_steps == ['submit_application']


@pytest.mark.asyncio
async def test_invalid_state_does_not_replace_last_saved_state():
    ctrl = controller_stub()
    ctrl.pause_state = {'previous': 'valid snapshot'}
    assert not await ctrl._save_session_state()
    assert ctrl.pause_state == {'previous': 'valid snapshot'}


@pytest.mark.asyncio
async def test_session_state_rejects_negative_step():
    ctrl = controller_stub()
    state = {'session_version': '1.0', 'timestamp': datetime.now().isoformat(),
             'current_plan': ['check_login'], 'current_step': -1,
             'job_data': {'title': 'Engineer', 'location': 'Remote'}}
    assert not (await ctrl._validate_session_state(state))[0]


@pytest.mark.asyncio
async def test_pause_and_resume_control_browser_agent():
    ctrl = controller_stub()
    ctrl.linkedin_agent = SimpleNamespace(pause=AsyncMock(), resume=AsyncMock())
    ctrl._save_session_state = AsyncMock(return_value=True)
    await ctrl.pause_session()
    assert not ctrl._resume_event.is_set()
    ctrl.linkedin_agent.pause.assert_awaited_once()
    await ctrl.resume_session()
    assert ctrl._resume_event.is_set()
    ctrl.linkedin_agent.resume.assert_awaited_once()

@pytest.mark.asyncio
async def test_page_context_rejects_linkedin_in_an_unrelated_url():
    nav = navigator()
    assert await nav._verify_page_context('https://www.linkedin.com/jobs/view/123')
    assert not await nav._verify_page_context('https://example.com/linkedin.com/jobs')
    assert not await nav._verify_page_context('https://linkedin.com.attacker.example/jobs')


@pytest.mark.asyncio
async def test_general_wait_preserves_cancellation(tmp_path):
    agent = GeneralAgent(SimpleNamespace(page=Mock()), logger(), min_delay=0, max_delay=0,
                         settings={'telemetry': {'enabled': False, 'storage_path': str(tmp_path)}})
    started = asyncio.Event()

    async def extract(_selector):
        started.set()
        await asyncio.Event().wait()

    agent.extract_text = extract
    task = asyncio.create_task(agent.wait_for_text('#name', 'expected'))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_end_session_cancels_ui_flow_runner():
    ctrl = controller_stub()
    ctrl._owns_logs_manager = False
    ctrl.task_manager = TaskManager(ctrl)
    entered, cleaned = asyncio.Event(), asyncio.Event()

    async def search(_title, _location):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    ctrl.linkedin_agent = SimpleNamespace(search_jobs_and_apply=search)
    flow = asyncio.create_task(ctrl.run_linkedin_flow('Engineer', 'Remote'))
    await entered.wait()
    await ctrl.end_session()
    assert flow.cancelled()
    assert cleaned.is_set()
