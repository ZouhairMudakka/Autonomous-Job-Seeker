"""Regression tests for local profile, telemetry, configuration and storage bugs."""

import asyncio
from datetime import datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from agents.tracker_agent import TrackerAgent
from agents.user_profile_agent import UserProfileAgent
from config.settings import load_settings
from storage.csv_storage import CSVStorage
from storage.file_utils import atomic_text_writer
from storage.logs_manager import LogsManager
from storage.privacy import redact_data
from utils.settings_manager import SettingsManager
from utils.telemetry import TelemetryManager


@pytest.fixture
def logger():
    return SimpleNamespace(info=AsyncMock(), debug=AsyncMock(), warning=AsyncMock(), error=AsyncMock())


@pytest.fixture
def settings(tmp_path):
    return {'system': {'data_dir': str(tmp_path)}, 'telemetry': {'enabled': False},
            'profile_storage_path': str(tmp_path / 'profiles')}


@pytest.mark.asyncio
@pytest.mark.parametrize('storage_format', ['csv', 'json'])
async def test_profile_round_trip_update_delete_and_recreate(settings, logger, storage_format):
    settings['profile_storage_format'] = storage_format
    agent = UserProfileAgent(settings, logger)
    original = await agent.create_profile({'user_id': 'person-1', 'name': 'Zoë', 'email': 'zoe@example.com',
                                          'preferred_titles': ['Engineer, Senior'],
                                          'parsed_cv_data': {'skills': ['Python', 'SQL']}})
    restored = await agent.get_profile('person-1')
    assert restored == original
    updated = await agent.update_profile('person-1', {'min_salary': 100, 'remote_preference': True})
    assert (await agent.get_profile('person-1')) == updated
    assert updated.created_at == original.created_at
    with pytest.raises(ValueError, match='already exists'):
        await agent.create_profile(original.model_dump())
    with pytest.raises(ValueError, match='cannot be changed'):
        await agent.update_profile('person-1', {'user_id': 'another'})
    assert await agent.delete_profile('person-1')
    assert not await agent.delete_profile('person-1')
    await agent.create_profile(original.model_dump())
    assert await agent.get_profile('person-1') == original


@pytest.mark.asyncio
@pytest.mark.parametrize('user_id', ['../outside', '..\\outside', '', '/tmp/outside', 'C:\\outside', 'NUL', 'foo:bar'])
async def test_profile_paths_are_contained(settings, logger, tmp_path, user_id):
    settings['profile_storage_format'] = 'json'
    outside = tmp_path / 'outside.json'
    outside.write_text('keep me', encoding='utf-8')
    agent = UserProfileAgent(settings, logger)
    with pytest.raises(ValueError):
        await agent.create_profile({'user_id': user_id, 'name': 'Person', 'email': 'person@example.com'})
    with pytest.raises(ValueError):
        await agent.get_profile(user_id)
    with pytest.raises(ValueError):
        await agent.delete_profile(user_id)
    assert outside.read_text(encoding='utf-8') == 'keep me'


@pytest.mark.asyncio
async def test_csv_profile_legacy_fields_and_concurrent_writes(settings, logger):
    agent = UserProfileAgent(settings, logger)
    await asyncio.gather(*(agent.create_profile({'user_id': f'u{i}', 'name': 'Person',
                                                 'email': f'person{i}@example.com'}) for i in range(8)))
    assert len(pd.read_csv(agent._csv_path)) == 8
    row = {'user_id': 'old', 'name': 'Person', 'email': 'person@example.com',
           'preferred_titles': "['Python engineer']", 'preferred_locations': '[]',
           'parsed_cv_data': "{'skills': ['Python']}", 'min_salary': '', 'cv_last_updated': ''}
    profile = agent._decode_profile(row)
    assert profile.preferred_titles == ['Python engineer']
    assert profile.min_salary is None


@pytest.mark.parametrize('name', ['../escape', '..\\escape', 'C:\\escape', '', 'NUL', 'name:stream'])
def test_csv_path_traversal_rejected(tmp_path, name):
    storage = CSVStorage({'data_dir': str(tmp_path / 'nested' / 'data')})
    with pytest.raises(ValueError):
        storage.save_data([{'a': 1}], name)
    with pytest.raises(ValueError):
        storage.load_data(name)
    with pytest.raises(ValueError):
        storage.is_file_exists(name)
    with pytest.raises(ValueError):
        storage.save_data([{'a': 1}], 'safe', file_id=name)


def test_csv_reorders_append_columns_and_rejects_schema_drift(tmp_path):
    storage = CSVStorage({'data_dir': str(tmp_path)})
    storage.save_data([{'name': 'Alice', 'age': 30}], 'people')
    storage.save_data([{'age': 42, 'name': 'Bob'}], 'people')
    assert storage.load_data('people').to_dict('records') == [
        {'name': 'Alice', 'age': 30}, {'name': 'Bob', 'age': 42}]
    before = (tmp_path / 'people.csv').read_bytes()
    with pytest.raises(ValueError, match='existing columns'):
        storage.save_data([{'name': 'Charlie', 'email': 'charlie@example.com'}], 'people')
    assert (tmp_path / 'people.csv').read_bytes() == before


def test_atomic_write_keeps_existing_file_on_serialization_failure(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text('{"valid": true}', encoding='utf-8')
    with pytest.raises(TypeError):
        with atomic_text_writer(path) as stream:
            json.dump({'unsupported': object()}, stream)
    assert json.loads(path.read_text()) == {'valid': True}
    assert list(tmp_path.iterdir()) == [path]


def test_settings_failure_does_not_corrupt_disk_or_memory(tmp_path):
    manager = SettingsManager(tmp_path / 'settings.json')
    manager.set_setting('valid', {'nested': True})
    external = manager.get_setting('valid')
    external['nested'] = False
    assert manager.get_setting('valid') == {'nested': True}
    with pytest.raises(TypeError):
        manager.set_setting('unsupported', object())
    assert manager.settings == {'valid': {'nested': True}}
    assert SettingsManager(manager.settings_file).settings == manager.settings


def test_invalid_environment_values_use_defaults_and_data_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('config.settings.load_dotenv', lambda: None)
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'custom'))
    for name, value in {'CDP_PORT': '70000', 'VIEWPORT_WIDTH': 'bad', 'VIEWPORT_HEIGHT': '-1',
                        'LINKEDIN_TIMEOUT': '', 'LINKEDIN_MIN_DELAY': 'nan', 'LINKEDIN_MAX_DELAY': '-2',
                        'RETRY_DELAY': 'inf', 'MAX_RETRIES': '-1', 'TELEMETRY_BUFFER_SIZE': '0',
                        'LOG_LEVEL': 'INVALID'}.items():
        monkeypatch.setenv(name, value)
    config = load_settings()
    assert config['browser']['cdp_port'] == 9222
    assert config['browser']['viewport'] == {'width': 1280, 'height': 720}
    assert config['linkedin']['default_timeout'] == 10000
    assert config['linkedin']['min_delay'] == 1.0
    assert config['system']['retry_delay'] == 1.0
    assert config['logging']['level'] == 'INFO'
    assert Path(config['telemetry']['storage_path']).parent == tmp_path / 'custom'
    assert (tmp_path / 'custom' / 'logs').is_dir()
    assert not (tmp_path / 'data').exists()


@pytest.mark.asyncio
async def test_telemetry_persists_once_redacts_and_keeps_session_totals(tmp_path):
    config = {'telemetry': {'storage_path': str(tmp_path), 'buffer_size': 2}}
    manager = TelemetryManager(config)
    payload = {'password': 'secret-value', 'nested': [{'api_key': 'key-value'}],
               'form_data': {'name': 'Personal Name'}, 'duration': 0.25}
    await asyncio.gather(*(manager.track_event('sample', payload, True, .8) for _ in range(5)))
    await manager._save_buffer()
    events = await manager.load_events()
    assert len(events) == 5
    assert manager.get_session_metrics()['total_events'] == 5
    assert len(manager.events_buffer) == 2
    assert events[0]['duration_ms'] == 250
    stored = json.dumps(events)
    assert all(value not in stored for value in ('secret-value', 'key-value', 'Personal Name'))
    assert payload['password'] == 'secret-value'
    assert (await manager.get_analytics())['total_events'] == 5
    assert (await manager.get_analytics(end_date='2000-01-01'))['total_events'] == 0
    with pytest.raises(ValueError):
        await manager.load_events('../../outside')


@pytest.mark.asyncio
async def test_telemetry_disabled_does_not_write_or_create_storage(tmp_path):
    path = tmp_path / 'disabled'
    manager = TelemetryManager({'telemetry': {'enabled': False, 'storage_path': str(path)}})
    await manager.track_event('sample', {}, True)
    await manager.export_metrics({'total': 1})
    await manager._save_metrics()
    assert not path.exists()


@pytest.mark.asyncio
async def test_metric_datetime_serialization_and_recent_filter(tmp_path):
    manager = TelemetryManager({'telemetry': {'storage_path': str(tmp_path)}})
    manager.metrics_history = [
        {'type': 'score', 'timestamp': datetime.now(), 'value': .9},
        {'type': 'score', 'timestamp': datetime.now() - timedelta(hours=1), 'value': .1},
    ]
    await manager._save_metrics()
    assert await manager.get_recent_metrics('score') == [.9]


@pytest.mark.asyncio
async def test_tracker_default_logging_filter_restart_and_disable(settings, logger):
    tracker = TrackerAgent(settings, logger)
    await tracker.log_activity('apply', 'Completed', 'success')
    assert len(await tracker.get_recent_activities(activity_type='apply', status='success')) == 1
    restarted = TrackerAgent(settings, logger)
    await restarted.log_activity('search', 'Completed', 'success')
    assert len(await restarted.get_recent_activities()) == 2
    assert len(await restarted.get_activities()) == 2
    async with restarted.temp_disable():
        await restarted.log_activity('apply', 'Should not exist', 'success')
    assert len(await restarted.get_recent_activities()) == 2
    restarted.enable_bypass(['disk_write'])
    before = restarted.activity_file.read_bytes()
    await restarted.log_activity('apply', 'Memory only', 'success')
    assert restarted.activity_file.read_bytes() == before


def test_tracker_can_be_constructed_without_running_loop(settings, logger):
    TrackerAgent(settings, logger)


@pytest.mark.asyncio
async def test_logs_redact_credentials_and_respect_console_setting(tmp_path, capsys):
    logger = LogsManager({'system': {'data_dir': str(tmp_path)}, 'logging': {'console_output': False}})
    logger.logger = SimpleNamespace(info=AsyncMock())
    await logger.info('password=secret-value email=person@example.com Bearer token-value')
    message = logger.logger.info.call_args.args[0]
    assert all(value not in message for value in ('secret-value', 'person@example.com', 'token-value'))
    assert capsys.readouterr().out == ''


def test_docx_cv_preview_and_saved_selection(tmp_path, logger):
    from docx import Document
    from utils.file_manager import CVFileManager
    path = tmp_path / 'resume.docx'
    document = Document()
    document.add_paragraph('Engineering experience')
    document.save(path)
    settings_manager = SettingsManager(tmp_path / 'settings.json')
    settings_manager.set_setting('cv_file_path', str(path))
    manager = CVFileManager(logger, settings_manager)
    assert manager.has_cv_file
    assert manager.validate_cv_file(path)
    assert manager.get_cv_preview(path) == 'Engineering experience'
    assert not manager.validate_cv_file(tmp_path)
    # A synchronous GUI callback must not create an unawaited logger coroutine.
    logger.error.assert_not_called()


@pytest.mark.asyncio
async def test_learning_event_without_optional_telemetry(logger):
    from storage.learning_pipeline import LearningPipeline
    pipeline = LearningPipeline(logger)
    await pipeline.record_learning_event('click', {'password': 'sensitive-value'})
    assert 'sensitive-value' not in str(logger.debug.call_args_list)
    await pipeline.record_outcome('click', True, .9)
    assert await pipeline.get_success_rate('click') == 1
    with pytest.raises(ValueError):
        await pipeline.get_success_rate('click', window=0)


@pytest.mark.asyncio
async def test_multiple_telemetry_instances_do_not_lose_events(tmp_path):
    config = {'telemetry': {'storage_path': str(tmp_path)}}
    first, second = TelemetryManager(config), TelemetryManager(config)
    await asyncio.gather(first.track_event('first', {}, True), second.track_event('second', {}, False))
    assert (await first.get_analytics())['total_events'] == 2
    assert (await second.get_analytics())['success_rate'] == .5


@pytest.mark.asyncio
async def test_model_utils_merge_string_descriptions_without_mutating_inputs(logger):
    from datetime import date
    from models.cv_models import Experience
    from utils.model_utils import CVUtils
    first = Experience(company='Company', title='Engineer', start_date=date(2020, 1, 1),
                       end_date=date(2021, 1, 1), description='Built systems', technologies=['Python'])
    second = Experience(company='Company', title='Engineer', start_date=date(2020, 6, 1),
                        end_date=date(2022, 1, 1), description='Led projects', technologies=['Python', 'SQL'])
    merged = await CVUtils.merge_experiences([first, second], logger)
    assert len(merged) == 1
    assert merged[0].description == 'Built systems\nLed projects'
    assert merged[0].technologies == ['Python', 'SQL']
    assert first.end_date == date(2021, 1, 1)
    assert first.description == 'Built systems'
    assert await CVUtils.calculate_total_experience([first, second], logger) == 2.0


@pytest.mark.asyncio
async def test_application_utilities_accept_current_mvp_model(logger):
    from datetime import timezone
    from models.application_models import ApplicationTracking
    from utils.model_utils import ApplicationUtils
    application = ApplicationTracking(application_id='a1', job_id='j1', user_id='u1', status='applied',
                                      applied_at=datetime.now(timezone.utc) - timedelta(days=8))
    assert await ApplicationUtils.should_follow_up(application, logger)
    metrics = await ApplicationUtils.get_application_metrics([application], logger)
    assert metrics == {'total': 1, 'response_rate': 0.0, 'interview_rate': 0.0, 'average_response_time': 0.0}
    draft = application.model_copy(update={'status': 'draft'})
    assert not await ApplicationUtils.should_follow_up(draft, logger)
