"""
Performance Monitor Implementation
Provides performance monitoring and metrics collection.
"""

import time
import psutil
from datetime import datetime
from typing import Optional

class PerformanceMonitor:
    """Context manager for monitoring performance of operations."""

    def __init__(self, logs_manager, operation: str):
        self.logs_manager = logs_manager
        self.operation = operation
        self.start_time: Optional[float] = None
        self.start_memory: Optional[int] = None

    async def __aenter__(self):
        """Start monitoring."""
        self.start_time = time.time()
        self._start_monotonic = time.monotonic()
        try:
            process = psutil.Process()
            self.start_memory = process.memory_info().rss
        except Exception:
            self.start_memory = None
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """End monitoring and log results."""
        try:
            duration = time.monotonic() - self._start_monotonic
            memory_delta = None

            performance_data = {
                "operation": self.operation,
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "duration": duration,
                "success": exc_type is None
            }

            # Add memory metrics if available
            if self.start_memory is not None:
                try:
                    process = psutil.Process()
                    end_memory = process.memory_info().rss
                    memory_delta = end_memory - self.start_memory
                    performance_data.update({
                        "memory_before": self.start_memory,
                        "memory_after": end_memory,
                        "memory_delta": memory_delta
                    })
                except Exception as e:
                    await self.logs_manager.warning(f"Failed to get memory metrics: {e}")

            # Add error information if operation failed
            if exc_type is not None:
                performance_data.update({
                    "error_type": exc_type.__name__,
                    "error_message": str(exc_val)
                })

            # Log performance data
            await self.logs_manager.info(
                f"Performance data for {self.operation}: {performance_data}"
            )

            # Track slow operations
            if duration > 1.0:  # More than 1 second
                await self.logs_manager.warning(
                    f"Slow operation detected: {self.operation} took {duration:.2f} seconds"
                )

            # Track memory spikes
            if memory_delta is not None and memory_delta > 50 * 1024 * 1024:  # 50MB
                await self.logs_manager.warning(
                    f"High memory usage in operation: {self.operation} "
                    f"delta={memory_delta / 1024 / 1024:.1f}MB"
                )

        except Exception:
            # Observability must never replace the operation's result/exception.
            pass
        return False


def monitor_performance(logs_manager, operation: str):
    """Get a performance monitoring context manager."""
    return PerformanceMonitor(logs_manager, operation)
