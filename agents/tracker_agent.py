"""
Activity Tracking Agent with Size-Based Rotation

Features:
1. Uses pandas for CSV read/write.
2. Concurrency-safe (via an asyncio.Lock).
3. Columns: row_id, timestamp, agent_name, job_id, type, details, status.
4. Logs each entry for real-time feedback.
5. Size-based rotation: if activity_log.csv exceeds max_file_size_bytes,
   it renames the old file with a timestamp suffix and starts a new one.

TODO (AI Integration):
- Add confidence score tracking to activity logs
- Integrate with learning pipeline events
- Add AI-specific activity types and statuses
- Setup unified logging for AI and systematic approaches
"""

import pandas as pd
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import uuid
import os
from constants import TimingConstants, Messages
import json
import aiofiles
from utils.telemetry import TelemetryManager
from storage.logs_manager import LogsManager

class TrackerAgent:
    def __init__(self, settings: dict, logs_manager: LogsManager = None):
        """
        Args:
            settings (dict): Example:
                {
                    "data_dir": "./logs",
                    "max_file_size_bytes": 5_000_000  # 5 MB
                }
            logs_manager (LogsManager, optional): Instance of LogsManager for logging.
                If not provided, direct prints will be used as fallback.
        """
        # Store logs_manager reference
        self.logs_manager = logs_manager
        
        # Log initialization start
        if self.logs_manager:
            asyncio.create_task(self.logs_manager.info("[TrackerAgent] Initializing tracker agent..."))

        self.data_dir = Path(settings.get("data_dir", "./logs"))
        self.data_dir.mkdir(exist_ok=True)
        self.activity_file = self.data_dir / "activity_log.csv"

        # Set a max file size for rotation
        self.max_file_size_bytes = settings.get("max_file_size_bytes", 5_000_000)  # default 5 MB

        # We'll store an asyncio.Lock for concurrency protection if multiple tasks write logs
        self._lock = asyncio.Lock()

        # Columns we expect in our log
        self.log_columns = [
            "row_id",
            "timestamp",
            "agent_name",
            "job_id",
            "type",
            "details",
            "status"
        ]

        # Set default timeout for operations
        self.default_timeout = TimingConstants.DEFAULT_TIMEOUT

        self.activity_history = []  # Store recent activities
        self.storage_path = Path(settings.get('tracker_path', './data/tracker'))
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize telemetry manager
        self.telemetry = TelemetryManager(settings)
        self.current_state = {}
        self.state_history = []
        self.metrics = {}

        # Log initialization complete
        if self.logs_manager:
            asyncio.create_task(self.logs_manager.info("[TrackerAgent] Initialization complete"))

    async def log_activity(
        self,
        activity_type: str,
        details: str,
        status: str,
        agent_name: str = "",
        job_id: str = ""
    ) -> None:
        """
        Log an activity with a timestamp, agent name, job_id, etc.
        Also logs the activity for real-time feedback.
        """
        row_id = str(uuid.uuid4())
        timestamp_str = datetime.now().isoformat(sep=' ', timespec='seconds')

        activity = {
            "row_id": row_id,
            "timestamp": timestamp_str,
            "agent_name": agent_name,
            "job_id": job_id,
            "type": activity_type,
            "details": details,
            "status": status
        }

        # Log for real-time feedback
        log_msg = f"{timestamp_str} | {agent_name} | {activity_type} | {details} | {status}"
        if self.logs_manager:
            await self.logs_manager.info(f"[TrackerAgent] Activity: {log_msg}")

        df = pd.DataFrame([activity], columns=self.log_columns)

        async with self._lock:
            try:
                # Add delay before file operations
                await asyncio.sleep(TimingConstants.ACTION_DELAY)
                
                # Rotate if needed before writing
                await self._rotate_if_needed()

                file_exists = self.activity_file.exists()
                
                if self.logs_manager:
                    await self.logs_manager.debug(f"[TrackerAgent] Writing activity to CSV: {activity_type}")
                
                df.to_csv(
                    self.activity_file,
                    mode="a",
                    header=not file_exists,
                    index=False
                )

                if self.logs_manager:
                    await self.logs_manager.debug("[TrackerAgent] Successfully wrote activity to CSV")

                # Add delay after file operations
                await asyncio.sleep(TimingConstants.FILE_UPLOAD_DELAY)

            except Exception as e:
                error_msg = f"Error writing to CSV: {e}"
                if self.logs_manager:
                    await self.logs_manager.error(f"[TrackerAgent] {error_msg}")
                else:
                    print(f"[TrackerAgent] {error_msg}")
                await asyncio.sleep(TimingConstants.ERROR_DELAY)

        self.activity_history.append(activity)
        await self._save_activities()

    async def get_activities(self, activity_type: str = None) -> pd.DataFrame:
        """
        Retrieve logged activities from the CSV as a pandas DataFrame.
        Optional: filter by activity_type.
        """
        if not self.activity_file.exists():
            if self.logs_manager:
                await self.logs_manager.warning("[TrackerAgent] Activity file does not exist yet")
            return pd.DataFrame(columns=self.log_columns)

        try:
            if self.logs_manager:
                filter_msg = f" filtered by type '{activity_type}'" if activity_type else ""
                await self.logs_manager.info(f"[TrackerAgent] Retrieving activities{filter_msg}")
            
            # Add delay before file read
            await asyncio.sleep(TimingConstants.ACTION_DELAY)
            
            df = pd.read_csv(self.activity_file)
            if activity_type:
                df = df[df["type"] == activity_type]
            
            # Add delay after file read
            await asyncio.sleep(TimingConstants.TEXT_EXTRACTION_DELAY)

            if self.logs_manager:
                await self.logs_manager.info(f"[TrackerAgent] Retrieved {len(df)} activities")
            return df
            
        except Exception as e:
            error_msg = f"Error reading CSV: {e}"
            if self.logs_manager:
                await self.logs_manager.error(f"[TrackerAgent] {error_msg}")
                await asyncio.sleep(TimingConstants.ERROR_DELAY)
            return pd.DataFrame(columns=self.log_columns)

    async def _rotate_if_needed(self):
        """
        Checks if the current log file exceeds max_file_size_bytes.
        If so, rename it with a timestamp suffix and start a fresh one.
        """
        if not self.activity_file.exists():
            return

        file_size = self.activity_file.stat().st_size
        if file_size >= self.max_file_size_bytes:
            # Create a timestamped filename
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_name = self.data_dir / f"activity_log_{timestamp_str}.csv"

            try:
                # Add delay before file rotation
                await asyncio.sleep(TimingConstants.ACTION_DELAY)
                
                if self.logs_manager:
                    await self.logs_manager.info(f"[TrackerAgent] Rotating log file. Size: {file_size} bytes")
                
                self.activity_file.rename(rotated_name)
                
                if self.logs_manager:
                    await self.logs_manager.info(f"[TrackerAgent] Log file rotated to: {rotated_name}")
                
                # Add delay after file rotation
                await asyncio.sleep(TimingConstants.FILE_UPLOAD_DELAY)
                
            except Exception as e:
                error_msg = f"Error rotating log file: {e}"
                if self.logs_manager:
                    await self.logs_manager.error(f"[TrackerAgent] {error_msg}")
                await asyncio.sleep(TimingConstants.ERROR_DELAY)

    async def get_recent_activities(
        self,
        timeframe_minutes: int = 30,
        activity_type: str | list[str] = None,
        status: str = None
    ) -> list[dict]:
        """Get recent activities within timeframe."""
        if self.logs_manager:
            await self.logs_manager.debug(
                f"[TrackerAgent] Retrieving recent activities for past {timeframe_minutes} minutes"
                f"{f' with type {activity_type}' if activity_type else ''}"
                f"{f' and status {status}' if status else ''}"
            )
        
        await self._load_activities()  # Load from disk before querying
        cutoff_time = datetime.now() - timedelta(minutes=timeframe_minutes)
        
        # Handle activity_type as string or list
        activity_types = (
            [activity_type] if isinstance(activity_type, str)
            else activity_type
        )
        
        filtered_activities = [
            activity for activity in self.activity_history
            if (
                activity['timestamp'] >= cutoff_time and
                (not activity_types or activity['type'] in activity_types) and
                (not status or activity['status'] == status)
            )
        ]

        if self.logs_manager:
            await self.logs_manager.info(
                f"[TrackerAgent] Found {len(filtered_activities)} activities in the specified timeframe"
            )
        
        return filtered_activities

    async def _load_activities(self):
        """Load activities from disk."""
        activities_file = self.storage_path / 'activity_history.json'
        if activities_file.exists():
            try:
                if self.logs_manager:
                    await self.logs_manager.debug("[TrackerAgent] Loading activities from disk")
                
                async with aiofiles.open(activities_file, 'r') as f:
                    content = await f.read()
                    self.activity_history = json.loads(content)
                
                if self.logs_manager:
                    await self.logs_manager.info(f"[TrackerAgent] Loaded {len(self.activity_history)} activities from disk")
            except Exception as e:
                if self.logs_manager:
                    await self.logs_manager.error(f"[TrackerAgent] Error loading activities: {e}")
                
    async def _save_activities(self):
        """Save activities to disk."""
        activities_file = self.storage_path / 'activity_history.json'
        try:
            if self.logs_manager:
                await self.logs_manager.debug("[TrackerAgent] Saving activities to disk")
            
            async with aiofiles.open(activities_file, 'w') as f:
                await f.write(json.dumps(self.activity_history))
            
            if self.logs_manager:
                await self.logs_manager.info(f"[TrackerAgent] Saved {len(self.activity_history)} activities to disk")
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"[TrackerAgent] Error saving activities: {e}")

    async def track_action(self, action_name: str, context: dict = None) -> None:
        """
        Track an action with its context and update metrics.
        """
        if self.logs_manager:
            await self.logs_manager.info(f"[TrackerAgent] Tracking action: {action_name}")
            if context:
                await self.logs_manager.debug(f"[TrackerAgent] Action context: {json.dumps(context)}")

        timestamp = datetime.now().isoformat()
        
        action_data = {
            "action": action_name,
            "timestamp": timestamp,
            "context": context or {},
            "state": self.current_state.copy()
        }
        
        # Update state history
        self.state_history.append(action_data)
        
        # Update metrics
        self._update_metrics(action_name, context)
        
        # Send telemetry
        success = context.get("success", True) if context else True
        confidence = context.get("confidence", None) if context else None
        
        await self.telemetry.track_event(
            event_type=action_name,
            data={
                "timestamp": timestamp,
                "context": context,
                "metrics": self.metrics
            },
            success=success,
            confidence=confidence
        )

        if self.logs_manager:
            await self.logs_manager.info(f"[TrackerAgent] Successfully tracked action: {action_name}")
            if not success:
                await self.logs_manager.warning(f"[TrackerAgent] Action {action_name} reported as unsuccessful")
    
    def _update_metrics(self, action_name: str, context: dict = None) -> None:
        """Update metrics based on the action and context."""
        if action_name not in self.metrics:
            self.metrics[action_name] = {
                "count": 0,
                "success_count": 0,
                "failure_count": 0,
                "last_occurrence": None,
                "avg_duration": 0
            }
        
        metric = self.metrics[action_name]
        metric["count"] += 1
        metric["last_occurrence"] = datetime.now().isoformat()
        
        if context and "success" in context:
            if context["success"]:
                metric["success_count"] += 1
            else:
                metric["failure_count"] += 1
        
        if context and "duration" in context:
            # Update running average
            prev_avg = metric["avg_duration"]
            metric["avg_duration"] = (prev_avg * (metric["count"] - 1) + context["duration"]) / metric["count"]
    
    async def update_state(self, state_updates: dict) -> None:
        """
        Update the current state with new values.
        """
        if self.logs_manager:
            await self.logs_manager.info(f"[TrackerAgent] Updating state with {len(state_updates)} changes")
            await self.logs_manager.debug(f"[TrackerAgent] State updates: {json.dumps(state_updates)}")

        self.current_state.update(state_updates)
        
        # Track state change
        await self.track_action("state_updated", {
            "updates": state_updates
        })

        if self.logs_manager:
            await self.logs_manager.info("[TrackerAgent] State update completed successfully")
    
    def get_state_snapshot(self) -> dict:
        """
        Get a snapshot of the current state and metrics.
        """
        return {
            "current_state": self.current_state.copy(),
            "metrics": self.metrics.copy(),
            "history_length": len(self.state_history)
        }
    
    async def analyze_performance(self, time_window: int = None) -> dict:
        """
        Analyze performance metrics within the given time window (in seconds).
        """
        if self.logs_manager:
            window_msg = f"within {time_window} seconds" if time_window else "for all time"
            await self.logs_manager.info(f"[TrackerAgent] Analyzing performance {window_msg}")

        now = datetime.now()
        metrics = {}
        
        for action, data in self.metrics.items():
            if time_window:
                # Filter metrics within time window
                last_occurrence = datetime.fromisoformat(data["last_occurrence"])
                if (now - last_occurrence).total_seconds() > time_window:
                    continue
            
            success_rate = data["success_count"] / data["count"] if data["count"] > 0 else 0
            metrics[action] = {
                "success_rate": success_rate,
                "total_count": data["count"],
                "avg_duration": data["avg_duration"]
            }

            if self.logs_manager:
                await self.logs_manager.debug(
                    f"[TrackerAgent] Metrics for {action}: "
                    f"success_rate={success_rate:.2f}, "
                    f"count={data['count']}, "
                    f"avg_duration={data['avg_duration']:.2f}"
                )
        
        if self.logs_manager:
            await self.logs_manager.info(f"[TrackerAgent] Performance analysis completed for {len(metrics)} actions")
        
        return metrics
