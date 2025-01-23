"""
Telemetry Module for tracking system performance and usage.
"""

import logging
from typing import Dict, Any
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