"""Local telemetry with sanitized payloads and atomic daily event storage."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import uuid

from storage.file_utils import atomic_text_writer, file_lock
from storage.privacy import redact_data

if TYPE_CHECKING:
    from storage.logs_manager import LogsManager


@dataclass
class TelemetryEvent:
    timestamp: datetime
    event_type: str
    data: Dict[str, Any]
    success: bool
    duration_ms: float
    confidence_score: Optional[float] = None
    session_id: Optional[str] = None
    session_duration: Optional[float] = None


class TelemetryManager:
    def __init__(self, settings: Dict, logs_manager: Optional['LogsManager'] = None):
        self.logger = logging.getLogger(__name__)
        config = settings.get('telemetry', {})
        self.enabled = config.get('enabled', True)
        data_dir = Path(settings.get('system', {}).get('data_dir', settings.get('data_dir', './data')))
        self.storage_path = Path(config.get('storage_path', data_dir / 'telemetry'))
        self.buffer_size = max(1, int(config.get('buffer_size', 100)))
        self.metrics_history = []
        self.session_id = str(uuid.uuid4())
        self.session_start = datetime.now()
        self.events_buffer = []
        self.logs_manager = logs_manager
        self._event_counts = {}
        self._error_count = 0
        self._total_duration = 0.0
        if self.enabled:
            self.storage_path.mkdir(parents=True, exist_ok=True)

    async def track_event(self, event_type: str, data: Dict[str, Any],
                          success: bool, confidence: float = None):
        if not self.enabled:
            return
        timestamp = datetime.now()
        session_duration = (timestamp - self.session_start).total_seconds()
        # Operation duration is supplied in seconds by callers; a Unix timestamp
        # is not an elapsed duration.
        duration = data.get('duration', 0)
        duration = duration if isinstance(duration, (int, float)) and duration >= 0 else 0
        enhanced_data = redact_data({**data, 'session_id': self.session_id,
                                     'session_duration': session_duration})
        event = TelemetryEvent(timestamp, event_type, enhanced_data, success,
                               duration * 1000, confidence, self.session_id, session_duration)
        self._event_counts[event_type] = self._event_counts.get(event_type, 0) + 1
        self._error_count += not success
        self._total_duration += duration
        self.events_buffer.append(self._event_to_dict(event))
        # Keep a bounded recent window for callers, independent of durable data.
        del self.events_buffer[:-self.buffer_size]
        await self._store_event(event)

    def _event_to_dict(self, event: TelemetryEvent) -> dict:
        return {**vars(event), 'timestamp': event.timestamp.isoformat()}

    async def _save_buffer(self) -> None:
        """Compatibility flush: events are already persisted once in daily files."""
        return None

    def get_session_metrics(self) -> dict:
        return {
            'session_id': self.session_id,
            'session_duration': (datetime.now() - self.session_start).total_seconds(),
            'total_events': sum(self._event_counts.values()),
            'event_counts': self._event_counts.copy(),
            'error_count': self._error_count,
            'total_operation_duration': self._total_duration,
        }

    async def track_ai_performance(self, operation: str, confidence: float, success: bool):
        await self.track_event('ai_operation', {'operation': operation}, success, confidence)

    async def track_cli_command(self, command: str, args: Dict[str, Any] = None):
        await self.track_event('cli_command', {'command': command, 'arguments': args or {}}, True)

    async def track_gui_interaction(self, action: str, component: str):
        await self.track_event('gui_interaction', {'action': action, 'component': component}, True)

    async def track_browser_setup(self, browser_type: str, headless: bool,
                                  success: bool, error: str = None):
        await self.track_event('browser_setup', {'browser_type': browser_type,
                               'headless': headless, 'error': error}, success)

    async def track_job_match(self, job_id: str, match_score: float, criteria: Dict[str, Any]):
        await self.track_event('job_match', {'job_id': job_id, 'criteria': criteria}, True, match_score)

    async def _store_event(self, event: TelemetryEvent):
        if not self.enabled:
            return
        event_file = self.storage_path / 'events' / f'events_{event.timestamp:%Y-%m-%d}.json'
        try:
            with file_lock(event_file):
                events = []
                if event_file.exists():
                    with event_file.open(encoding='utf-8') as stream:
                        events = json.load(stream)
                events.append(self._event_to_dict(event))
                with atomic_text_writer(event_file) as stream:
                    json.dump(events, stream, ensure_ascii=False, indent=2)
        except (OSError, ValueError, TypeError) as exc:
            self.logger.error('Failed to store telemetry event: %s', type(exc).__name__)

    async def load_events(self, date_str: str = None) -> List[Dict]:
        events_dir = self.storage_path / 'events'
        if date_str is not None:
            # Validate before interpolation to prevent file traversal.
            parsed = date.fromisoformat(date_str)
            if parsed.isoformat() != date_str:
                raise ValueError('Date must use YYYY-MM-DD')
            paths = [events_dir / f'events_{date_str}.json']
        else:
            # Ignore old session-buffer copies, which duplicate daily events.
            paths = sorted(events_dir.glob('events_????-??-??.json'))
        events = []
        for path in paths:
            if not path.exists():
                continue
            try:
                with file_lock(path), path.open(encoding='utf-8') as stream:
                    data = json.load(stream)
                if isinstance(data, list):
                    events.extend(data)
            except (OSError, ValueError) as exc:
                self.logger.warning('Could not read telemetry file %s: %s', path.name, type(exc).__name__)
        return events

    async def get_analytics(self, start_date: str = None, end_date: str = None) -> Dict:
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
        if start and end and start > end:
            raise ValueError('start_date must not be after end_date')
        events = await self.load_events()
        events = [event for event in events
                  if (not start or date.fromisoformat(event['timestamp'][:10]) >= start)
                  and (not end or date.fromisoformat(event['timestamp'][:10]) <= end)]
        analytics = {'total_events': len(events), 'success_rate': 0,
                     'event_types': {}, 'confidence_scores': {'average': 0, 'by_type': {}}, 'errors': []}
        if not events:
            return analytics
        analytics['success_rate'] = sum(bool(event['success']) for event in events) / len(events)
        for event in events:
            kind = event['event_type']
            analytics['event_types'][kind] = analytics['event_types'].get(kind, 0) + 1
            if event.get('confidence_score') is not None:
                analytics['confidence_scores']['by_type'].setdefault(kind, []).append(event['confidence_score'])
            if not event['success'] and event['data'].get('error'):
                analytics['errors'].append({'timestamp': event['timestamp'], 'type': kind,
                                            'error': event['data']['error']})
        scores = [score for group in analytics['confidence_scores']['by_type'].values() for score in group]
        if scores:
            analytics['confidence_scores']['average'] = sum(scores) / len(scores)
        return analytics

    async def export_metrics(self, analytics: Dict):
        if not self.enabled:
            return
        path = self.storage_path / 'metrics' / f'metrics_{datetime.now():%Y-%m-%d}.json'
        with file_lock(path), atomic_text_writer(path) as stream:
            json.dump(redact_data(analytics), stream, ensure_ascii=False, indent=2)

    async def get_recent_metrics(self, metric_type: str, timeframe_minutes: int = 15) -> list[float]:
        await self._load_metrics()
        cutoff = datetime.now().astimezone() - timedelta(minutes=timeframe_minutes)
        result = []
        for metric in self.metrics_history:
            timestamp = metric.get('timestamp')
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            if isinstance(timestamp, datetime) and timestamp.astimezone() >= cutoff and metric['type'] == metric_type:
                result.append(metric['value'])
        return result

    async def _load_metrics(self):
        path = self.storage_path / 'metrics_history.json'
        if path.exists():
            with file_lock(path), path.open(encoding='utf-8') as stream:
                self.metrics_history = json.load(stream)

    async def _save_metrics(self):
        if not self.enabled:
            return
        path = self.storage_path / 'metrics_history.json'
        def serialize(value):
            if isinstance(value, datetime):
                return value.isoformat()
            raise TypeError(f'Cannot serialize {type(value).__name__}')
        with file_lock(path), atomic_text_writer(path) as stream:
            json.dump(redact_data(self.metrics_history), stream, default=serialize)
