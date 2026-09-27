"""Headless regressions for UI state, reentrant callbacks and worker dispatch."""

from datetime import datetime, timedelta
from queue import SimpleQueue
from threading import Lock, Thread
from unittest.mock import Mock

from ui.components.ai_decision import AIDecision, AIDecisionView
from ui.components.analytics import JobMarketMetrics
from ui.components.platform_manager import PlatformConfig, PlatformManagerView, PlatformStatus
from ui.components.profile_manager import ProfileManagerView
from ui.components.activity_filter import ActivityFilterView
from ui.components.ui_dispatch import UIUpdateDispatcher


def bare_view(cls):
    view = object.__new__(cls)
    view._update_lock = Lock()
    view.schedule_ui_update = Mock()
    return view


def test_platform_status_callback_can_reenter_without_lock():
    view = bare_view(PlatformManagerView)
    view._platforms, view._status, view._status_callbacks = {}, {}, []
    invoked = []
    def callback(status):
        acquired = view._update_lock.acquire(blocking=False)
        invoked.append(acquired)
        if acquired:
            view._update_lock.release()
            view.add_platform(PlatformConfig('p2', 'Second', {}, {}))
    view.register_status_callback(callback)
    status = PlatformStatus('p1', True, 'good', datetime.now(), 0, {})
    view.update_platform_status(status)
    assert invoked == [True]
    assert 'p2' in view.platforms


def test_worker_dispatch_calls_no_tk_until_owner_drains():
    dispatcher = object.__new__(UIUpdateDispatcher)
    dispatcher.after = Mock(return_value='timer')
    dispatcher._init_ui_dispatcher()
    dispatcher.after.reset_mock()
    update = Mock()
    thread = Thread(target=dispatcher.schedule_ui_update, args=(update,))
    thread.start()
    thread.join(timeout=1)
    assert not thread.is_alive()
    update.assert_not_called()
    dispatcher.after.assert_not_called()
    dispatcher._drain_ui_updates()
    update.assert_called_once_with()
    dispatcher.after.assert_called_once()


def test_ai_decision_history_and_contract():
    view = bare_view(AIDecisionView)
    view.current_decision = None
    view.decision_history = []
    decision = AIDecision(decision_id='d1', confidence_score=.9, strategy='test', reasoning='reason',
                          fallback_triggers=[], timestamp=datetime.now(), metadata={})
    view.update_decision(decision)
    assert view.current_decision is decision
    assert view.decision_history == [decision]
    view.clear()
    assert view.current_decision is None
    assert view.decision_history == []


def test_profile_version_ids_do_not_overwrite_after_delete():
    view = bare_view(ProfileManagerView)
    view._versions, view._version_order = {}, []
    view.current_version = None
    view._next_version_number = 1
    view.resume_path_var = Mock(get=Mock(return_value=''))
    view.cover_path_var = Mock(get=Mock(return_value=''))
    view._show_status = Mock()
    view._create_new_version()
    view._create_new_version()
    second = view._versions['v2']
    del view._versions['v1']
    view._version_order.remove('v1')
    view._create_new_version()
    assert view._versions['v2'] is second
    assert list(view.profile_versions) == ['v2', 'v3']
    assert view.current_version.version_id == 'v3'


def test_metrics_compatibility_and_platform_credentials_repr():
    metrics = JobMarketMetrics(total_jobs=100, applications_sent=50, success_rate=.75,
                               avg_response_time=timedelta(days=2), skill_demand={'Python': 30},
                               salary_ranges={}, locations={'Dubai': 60}, timestamp=datetime.now())
    assert metrics.total_applications == 50
    assert metrics.avg_response_time == 48
    assert metrics.skills_demand == {'Python': 30}
    assert metrics.geographic_distribution == {'Dubai': 60}
    config = PlatformConfig(platform_id='p1', name='Platform', enabled=True,
                            credentials={'password': 'secret-value'}, settings={}, last_sync=datetime.now())
    assert 'secret-value' not in repr(config)


def test_activity_type_filter_and_yesterday_exclusion():
    view = bare_view(ActivityFilterView)
    view.activity_text = Mock()
    view.filter_var = Mock(get=Mock(return_value='Errors Only'))
    view.agent_filter_var = Mock(get=Mock(return_value='ALL'))
    view.time_filter_var = Mock(get=Mock(return_value='Today'))
    view.search_var = Mock(get=Mock(return_value=''))
    now = datetime.now()
    view._activity_content = (f'[{now:%Y-%m-%d %H:%M:%S}] [SYSTEM] Healthy\n'
                              f'[{now:%Y-%m-%d %H:%M:%S}] [ERROR] Failure\n'
                              f'[{now-timedelta(days=1):%Y-%m-%d %H:%M:%S}] [ERROR] Old failure\n')
    view._insert_line_with_tags = Mock()
    view._apply_filter()
    view._insert_line_with_tags.assert_called_once_with(f'[{now:%Y-%m-%d %H:%M:%S}] [ERROR] Failure')
