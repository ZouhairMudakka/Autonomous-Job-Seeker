"""
Telemetry Module for tracking system performance and usage.

Future Enhancements:
-------------------
1. User-AI Chat Tracking: [HIGH PRIORITY]
   - Add conversation_id tracking        # Critical for debugging
   - Track token usage and costs        # Critical for billing
   - Monitor response times             # Critical for performance
   - Track success/error rates          # Critical for reliability

2. Enhanced Metrics: [HIGH PRIORITY]
   - Token usage analytics              # Critical for cost management
   - Cost tracking per model            # Critical for billing
   - Response time monitoring           # Critical for SaaS SLAs
   - Success rate by conversation       # Important for quality

3. Performance Monitoring: [URGENT]
   - Add performance alerts             # Critical for system health
   - Track model-specific metrics       # Critical for reliability
   - Monitor rate limits                # Critical to prevent failures
   - Track resource usage               # Critical for scaling

4. Conversation Analytics: [MEDIUM]
   - Group by conversation_id
   - Track messages per conversation
   - Average tokens per turn
   - Topic/category tracking

5. Session Management: [MEDIUM]
   - Add anonymous session IDs
   - Track session durations
   - Monitor user patterns
   - Track peak usage times
"""

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import json
import aiofiles
import uuid

if TYPE_CHECKING:
    from storage.logs_manager import LogsManager

@dataclass
class TelemetryEvent:
    timestamp: datetime
    event_type: str
    data: Dict[str, Any]
    success: bool
    duration_ms: float
    confidence_score: float = None
    session_id: str = None
    session_duration: float = None

class TelemetryManager:
    def __init__(self, settings: Dict, logs_manager: Optional['LogsManager'] = None):
        """Initialize TelemetryManager with settings and optional logs_manager."""
        self.logger = logging.getLogger(__name__)
        self.enabled = settings.get('telemetry', {}).get('enabled', True)
        self.storage_path = Path(settings.get('telemetry', {}).get('storage_path', './data/telemetry'))
        self.metrics_history = []  # Store recent metrics
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Session management
        self.session_id = str(uuid.uuid4())
        self.session_start = datetime.now()
        self.events_buffer = []  # In-memory event buffer
        
        # Store logs_manager reference
        self.logs_manager = logs_manager

    async def track_event(self, event_type: str, data: Dict[str, Any], 
                         success: bool, confidence: float = None):
        """Track a single telemetry event with session data."""
        if not self.enabled:
            return

        timestamp = datetime.now()
        session_duration = (timestamp - self.session_start).total_seconds()

        # Enhance data with session info
        enhanced_data = {
            **data,
            "session_id": self.session_id,
            "session_duration": session_duration
        }

        event = TelemetryEvent(
            timestamp=timestamp,
            event_type=event_type,
            data=enhanced_data,
            success=success,
            duration_ms=time.time() * 1000,
            confidence_score=confidence,
            session_id=self.session_id,
            session_duration=session_duration
        )
        
        # Add to in-memory buffer
        self.events_buffer.append(self._event_to_dict(event))
        
        # Log the event using LogsManager if available
        if self.logs_manager:
            await self.logs_manager.info(
                f"[Telemetry] Event: {event_type} at {timestamp.isoformat()} "
                f"(success={success}, confidence={confidence})"
            )
        
        # Save events periodically
        if len(self.events_buffer) >= 100:
            if self.logs_manager:
                await self.logs_manager.debug("Buffer reached 100 events, saving to storage...")
            await self._save_buffer()
        
        await self._store_event(event)

    def _event_to_dict(self, event: TelemetryEvent) -> dict:
        """Convert TelemetryEvent to dictionary format."""
        return {
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type,
            "data": event.data,
            "success": event.success,
            "duration_ms": event.duration_ms,
            "confidence_score": event.confidence_score,
            "session_id": event.session_id,
            "session_duration": event.session_duration
        }

    async def _save_buffer(self) -> None:
        """Save buffered events to storage."""
        if not self.events_buffer:
            return
            
        try:
            events_file = self.storage_path / "events" / f"events_{self.session_id}.json"
            events_file.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(events_file, 'w') as f:
                await f.write(json.dumps(self.events_buffer))
                
            if self.logs_manager:
                await self.logs_manager.info(f"Successfully saved {len(self.events_buffer)} events to storage")
                
            self.events_buffer = []  # Clear after saving
            
        except Exception as e:
            error_msg = f"Failed to save events buffer: {str(e)}"
            if self.logs_manager:
                await self.logs_manager.error(error_msg)
            self.logger.error(error_msg)

    def get_session_metrics(self) -> dict:
        """Get metrics for the current session."""
        event_counts = {}
        total_duration = 0
        error_count = 0
        
        for event in self.events_buffer:
            # Count events by type
            event_type = event["event_type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            # Track errors
            if not event["success"]:
                error_count += 1
                
            # Track durations
            if "duration" in event["data"]:
                total_duration += event["data"]["duration"]
        
        return {
            "session_id": self.session_id,
            "session_duration": (datetime.now() - self.session_start).total_seconds(),
            "total_events": len(self.events_buffer),
            "event_counts": event_counts,
            "error_count": error_count,
            "total_operation_duration": total_duration
        }

    async def track_ai_performance(self, operation: str, 
                                 confidence: float, success: bool):
        """Specifically track AI operation performance."""
        await self.track_event(
            event_type="ai_operation",
            data={"operation": operation},
            success=success,
            confidence=confidence
        )

    async def track_cli_command(self, command: str, args: Dict[str, Any] = None):
        """Track CLI command usage."""
        await self.track_event(
            event_type="cli_command",
            data={
                "command": command,
                "arguments": args or {}
            },
            success=True
        )

    async def track_gui_interaction(self, action: str, component: str):
        """Track GUI interactions."""
        await self.track_event(
            event_type="gui_interaction",
            data={
                "action": action,
                "component": component
            },
            success=True
        )

    async def track_browser_setup(self, browser_type: str, headless: bool, 
                                success: bool, error: str = None):
        """Track browser setup events."""
        await self.track_event(
            event_type="browser_setup",
            data={
                "browser_type": browser_type,
                "headless": headless,
                "error": error
            },
            success=success
        )

    async def track_job_match(self, job_id: str, match_score: float, 
                            criteria: Dict[str, Any]):
        """Track job matching scores and criteria."""
        await self.track_event(
            event_type="job_match",
            data={
                "job_id": job_id,
                "criteria": criteria
            },
            success=True,
            confidence=match_score
        )

    async def _store_event(self, event: TelemetryEvent):
        """Store telemetry event to appropriate file."""
        try:
            # Create directories if they don't exist
            events_dir = self.storage_path / "events"
            metrics_dir = self.storage_path / "metrics"
            events_dir.mkdir(parents=True, exist_ok=True)
            metrics_dir.mkdir(parents=True, exist_ok=True)

            # Store event in daily file
            date_str = event.timestamp.strftime("%Y-%m-%d")
            event_file = events_dir / f"events_{date_str}.json"

            # Convert event to dict
            event_dict = {
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "data": event.data,
                "success": event.success,
                "duration_ms": event.duration_ms,
                "confidence_score": event.confidence_score
            }

            # Append to daily file
            events = []
            if event_file.exists():
                with event_file.open('r') as f:
                    events = json.load(f)
            events.append(event_dict)
            
            with event_file.open('w') as f:
                json.dump(events, f, indent=2)

            if self.logs_manager:
                await self.logs_manager.debug(f"Stored event in {event_file}")

        except Exception as e:
            error_msg = f"Failed to store telemetry event: {e}"
            if self.logs_manager:
                await self.logs_manager.error(error_msg)
            self.logger.error(error_msg)

    async def load_events(self, date_str: str = None) -> List[Dict]:
        """Load events for a specific date or all dates."""
        events = []
        events_dir = self.storage_path / "events"
        
        try:
            if date_str:
                # Load specific date
                event_file = events_dir / f"events_{date_str}.json"
                if event_file.exists():
                    with event_file.open('r') as f:
                        events = json.load(f)
                    if self.logs_manager:
                        await self.logs_manager.info(f"Loaded {len(events)} events from {date_str}")
            else:
                # Load all dates
                for event_file in events_dir.glob("events_*.json"):
                    with event_file.open('r') as f:
                        file_events = json.load(f)
                        events.extend(file_events)
                    if self.logs_manager:
                        await self.logs_manager.debug(f"Loaded {len(file_events)} events from {event_file.name}")
            
            return events
        except Exception as e:
            error_msg = f"Failed to load events: {e}"
            if self.logs_manager:
                await self.logs_manager.error(error_msg)
            self.logger.error(error_msg)
            return []

    async def get_analytics(self, start_date: str = None, end_date: str = None) -> Dict:
        """Generate analytics from telemetry data."""
        events = await self.load_events()
        
        if self.logs_manager:
            await self.logs_manager.info(f"Generating analytics from {len(events)} events")
            if start_date:
                await self.logs_manager.debug(f"Start date filter: {start_date}")
            if end_date:
                await self.logs_manager.debug(f"End date filter: {end_date}")

        analytics = {
            'total_events': len(events),
            'success_rate': 0,
            'event_types': {},
            'confidence_scores': {
                'average': 0,
                'by_type': {}
            },
            'errors': []
        }

        if not events:
            if self.logs_manager:
                await self.logs_manager.warning("No events found for analytics generation")
            return analytics

        # Calculate statistics
        successful = sum(1 for e in events if e['success'])
        analytics['success_rate'] = successful / len(events)

        # Group by event type
        for event in events:
            event_type = event['event_type']
            if event_type not in analytics['event_types']:
                analytics['event_types'][event_type] = 0
            analytics['event_types'][event_type] += 1

            # Track confidence scores
            if event['confidence_score'] is not None:
                if event_type not in analytics['confidence_scores']['by_type']:
                    analytics['confidence_scores']['by_type'][event_type] = []
                analytics['confidence_scores']['by_type'][event_type].append(
                    event['confidence_score']
                )

            # Track errors
            if not event['success'] and event['data'].get('error'):
                analytics['errors'].append({
                    'timestamp': event['timestamp'],
                    'type': event_type,
                    'error': event['data']['error']
                })

        # Calculate average confidence scores
        all_scores = [
            score for scores in analytics['confidence_scores']['by_type'].values()
            for score in scores
        ]
        if all_scores:
            analytics['confidence_scores']['average'] = sum(all_scores) / len(all_scores)

        if self.logs_manager:
            await self.logs_manager.info(
                f"Analytics generated: {len(events)} events, "
                f"{analytics['success_rate']*100:.1f}% success rate, "
                f"{len(analytics['errors'])} errors"
            )

        return analytics

    async def export_metrics(self, analytics: Dict):
        """Export analytics to metrics file."""
        try:
            metrics_dir = self.storage_path / "metrics"
            date_str = datetime.now().strftime("%Y-%m-%d")
            metrics_file = metrics_dir / f"metrics_{date_str}.json"
            
            if self.logs_manager:
                await self.logs_manager.info(f"Exporting metrics to {metrics_file}")
            
            with metrics_file.open('w') as f:
                json.dump(analytics, f, indent=2)
                
            if self.logs_manager:
                await self.logs_manager.info("Metrics export completed successfully")
                
        except Exception as e:
            error_msg = f"Failed to export metrics: {e}"
            if self.logs_manager:
                await self.logs_manager.error(error_msg)
            self.logger.error(error_msg)

    async def get_recent_metrics(self, metric_type: str, timeframe_minutes: int = 15) -> list[float]:
        """Get recent metrics of specified type within timeframe."""
        if self.logs_manager:
            await self.logs_manager.debug(
                f"Fetching {metric_type} metrics for last {timeframe_minutes} minutes"
            )
        
        await self._load_metrics()  # Load from disk before querying
        cutoff_time = datetime.now() - timedelta(minutes=timeframe_minutes)
        
        metrics = [
            metric['value'] for metric in self.metrics_history
            if (
                metric['type'] == metric_type and
                metric['timestamp'] >= cutoff_time
            )
        ]

        if self.logs_manager:
            await self.logs_manager.debug(f"Found {len(metrics)} matching metrics")
        
        return metrics
        
    async def _load_metrics(self):
        """Load metrics from disk."""
        metrics_file = self.storage_path / 'metrics_history.json'
        if metrics_file.exists():
            try:
                async with aiofiles.open(metrics_file, 'r') as f:
                    content = await f.read()
                    self.metrics_history = json.loads(content)
                if self.logs_manager:
                    await self.logs_manager.debug(
                        f"Loaded {len(self.metrics_history)} metrics from disk"
                    )
            except Exception as e:
                error_msg = f"Failed to load metrics from disk: {e}"
                if self.logs_manager:
                    await self.logs_manager.error(error_msg)
                self.logger.error(error_msg)
                
    async def _save_metrics(self):
        """Save metrics to disk."""
        metrics_file = self.storage_path / 'metrics_history.json'
        try:
            async with aiofiles.open(metrics_file, 'w') as f:
                await f.write(json.dumps(self.metrics_history))
            if self.logs_manager:
                await self.logs_manager.debug(
                    f"Saved {len(self.metrics_history)} metrics to disk"
                )
        except Exception as e:
            error_msg = f"Failed to save metrics to disk: {e}"
            if self.logs_manager:
                await self.logs_manager.error(error_msg)
            self.logger.error(error_msg)