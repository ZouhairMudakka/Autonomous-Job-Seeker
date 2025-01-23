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
from typing import Dict, Any, List
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json

@dataclass
class TelemetryEvent:
    timestamp: datetime
    event_type: str
    data: Dict[str, Any]
    success: bool
    duration_ms: float
    confidence_score: float = None

class TelemetryManager:
    def __init__(self, settings: Dict):
        self.logger = logging.getLogger(__name__)
        self.enabled = settings.get('telemetry', {}).get('enabled', True)
        self.storage_path = Path(settings.get('telemetry', {}).get('storage_path', './data/telemetry'))
        
    async def track_event(self, event_type: str, data: Dict[str, Any], 
                         success: bool, confidence: float = None):
        """Track a single telemetry event."""
        if not self.enabled:
            return

        event = TelemetryEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            data=data,
            success=success,
            duration_ms=time.time() * 1000,
            confidence_score=confidence
        )
        
        await self._store_event(event)
    
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

        except Exception as e:
            self.logger.error(f"Failed to store telemetry event: {e}") 

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
            else:
                # Load all dates
                for event_file in events_dir.glob("events_*.json"):
                    with event_file.open('r') as f:
                        events.extend(json.load(f))
            
            return events
        except Exception as e:
            self.logger.error(f"Failed to load events: {e}")
            return []

    async def get_analytics(self, start_date: str = None, end_date: str = None) -> Dict:
        """Generate analytics from telemetry data."""
        events = await self.load_events()
        
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

        return analytics

    async def export_metrics(self, analytics: Dict):
        """Export analytics to metrics file."""
        try:
            metrics_dir = self.storage_path / "metrics"
            date_str = datetime.now().strftime("%Y-%m-%d")
            metrics_file = metrics_dir / f"metrics_{date_str}.json"
            
            with metrics_file.open('w') as f:
                json.dump(analytics, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to export metrics: {e}") 