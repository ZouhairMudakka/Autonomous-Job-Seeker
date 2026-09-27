"""Offline coverage for the optional telemetry dashboard's data layer."""
import json

import pytest

from utils.telemetry_viewer import TelemetryViewer


def test_invalid_date_does_not_schedule_work_without_an_event_loop():
    viewer = TelemetryViewer()
    assert not viewer._is_date_in_range('invalid')
    assert viewer._is_date_in_range('2026-01-02', '2026-01-01', '2026-01-03')


@pytest.mark.asyncio
async def test_event_loading_skips_corrupt_files_and_non_events(tmp_path):
    viewer = TelemetryViewer()
    viewer.data_dir = tmp_path
    (tmp_path / 'events_2026-01-02.json').write_text(json.dumps([
        {'event_type': 'search', 'timestamp': '2026-01-02T00:00:00', 'success': True}, None
    ]), encoding='utf-8')
    (tmp_path / 'events_2026-01-03.json').write_text('broken', encoding='utf-8')
    assert len(await viewer.load_events('2026-01-01', '2026-01-04')) == 1


@pytest.mark.asyncio
async def test_null_confidence_and_bad_timestamps_keep_useful_analytics():
    viewer = TelemetryViewer()
    analytics = await viewer.analyze_events([
        {'event_type': 'search', 'success': True, 'confidence_score': None,
         'timestamp': '2026-01-02T00:00:00'},
        {'event_type': 'search', 'success': False, 'confidence_score': None, 'timestamp': None},
    ])
    assert analytics['total_events'] == 2
    assert analytics['success_rate'] == 50
    assert analytics['avg_confidence'] == 0
    assert analytics['daily_events'] == {'2026-01-02': 1}
