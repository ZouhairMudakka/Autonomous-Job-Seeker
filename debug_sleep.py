"""
Debug sleep functionality for tracking and logging wait operations.
"""

import asyncio
import time
from typing import Optional, Union

from storage.logs_manager import LogsManager
from constants import DebugTimingConstants, DebugSleepHelper

class DebugSleep:
    """Debug sleep functionality for tracking wait operations."""
    
    def __init__(self, logs_manager: Optional[LogsManager] = None):
        """Initialize debug sleep with optional logs manager."""
        self.logs_manager = logs_manager
    
    @staticmethod
    def _normalize_sleep_time(seconds: Union[int, float]) -> float:
        """
        Convert input time to seconds.
        - If value >= 10, assume it's milliseconds and convert to seconds
        - If value < 10, assume it's already in seconds
        
        This handles both formats from TimingConstants:
        - millisecond integers (e.g., 200 -> 0.2s)
        - second decimals (e.g., 0.3 -> 0.3s)
        """
        if seconds >= 10:  # Assume it's milliseconds
            return seconds / 1000
        return seconds  # Assume it's already in seconds
    
    async def _log_message(self, message: str) -> None:
        """Log a message using logs manager if available, otherwise print."""
        if self.logs_manager:
            await self.logs_manager.debug(message)
        else:
            print(message)
    
    async def sleep(self, seconds: Union[int, float], reason: str = "") -> None:
        """
        Debug sleep that logs the start and end of wait operations.
        
        Args:
            seconds: Number of seconds (or milliseconds if >= 10) to sleep
            reason: Optional reason for the sleep operation
        """
        # Convert to seconds if needed
        sleep_seconds = self._normalize_sleep_time(seconds)
        
        if not DebugSleepHelper.should_log_wait(sleep_seconds):
            await asyncio.sleep(sleep_seconds)
            return
            
        # Log sleep start
        start_message = DebugSleepHelper.format_sleep_start(sleep_seconds, reason)
        await self._log_message(start_message)
        
        # Perform sleep
        start_time = time.time()
        await asyncio.sleep(sleep_seconds)
        end_time = time.time()
        
        # Log sleep end
        duration = end_time - start_time
        end_message = DebugSleepHelper.format_sleep_end(duration)
        await self._log_message(end_message)

# Global instance for convenience
debug_sleep = DebugSleep() 