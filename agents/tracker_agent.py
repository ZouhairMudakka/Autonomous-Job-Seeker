"""
Activity Tracking Agent with Size-Based Rotation

Features:
1. Uses pandas for CSV read/write.
2. Concurrency-safe (via an asyncio.Lock).
3. Columns: row_id, timestamp, agent_name, job_id, type, details, status.
4. Prints each log entry to terminal for real-time feedback.
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
from datetime import datetime
from pathlib import Path
import uuid
import os
from constants import TimingConstants, Messages

class TrackerAgent:
    def __init__(self, settings: dict):
        """
        Args:
            settings (dict): Example:
                {
                    "data_dir": "./logs",
                    "max_file_size_bytes": 5_000_000  # 5 MB
                }
        """
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
        Also prints the activity to the terminal for real-time feedback.
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

        # Print to terminal for real-time user feedback
        print(f"[Tracker] {timestamp_str} | {agent_name} | {activity_type} | {details} | {status}")

        df = pd.DataFrame([activity], columns=self.log_columns)

        async with self._lock:
            try:
                # Add delay before file operations
                await asyncio.sleep(TimingConstants.ACTION_DELAY)
                
                # Rotate if needed before writing
                await self._rotate_if_needed()

                file_exists = self.activity_file.exists()
                df.to_csv(
                    self.activity_file,
                    mode="a",
                    header=not file_exists,
                    index=False
                )

                # Add delay after file operations
                await asyncio.sleep(TimingConstants.FILE_UPLOAD_DELAY)

            except Exception as e:
                print(f"[TrackerAgent] Error writing to CSV: {e}")
                await asyncio.sleep(TimingConstants.ERROR_DELAY)

    async def get_activities(self, activity_type: str = None) -> pd.DataFrame:
        """
        Retrieve logged activities from the CSV as a pandas DataFrame.
        Optional: filter by activity_type.
        """
        if not self.activity_file.exists():
            return pd.DataFrame(columns=self.log_columns)

        try:
            # Add delay before file read
            await asyncio.sleep(TimingConstants.ACTION_DELAY)
            
            df = pd.read_csv(self.activity_file)
            if activity_type:
                return df[df["type"] == activity_type]
            
            # Add delay after file read
            await asyncio.sleep(TimingConstants.TEXT_EXTRACTION_DELAY)
            return df
            
        except Exception as e:
            print(f"[TrackerAgent] Error reading CSV: {e}")
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
                
                self.activity_file.rename(rotated_name)
                print(f"[TrackerAgent] Log file rotated. Old file: {rotated_name}")
                
                # Add delay after file rotation
                await asyncio.sleep(TimingConstants.FILE_UPLOAD_DELAY)
                
            except Exception as e:
                print(f"[TrackerAgent] Error rotating log file: {e}")
                await asyncio.sleep(TimingConstants.ERROR_DELAY)
