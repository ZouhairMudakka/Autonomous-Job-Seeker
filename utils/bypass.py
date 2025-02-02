"""
Utility module for bypassing operations in various components.

This module provides context managers and utilities for temporarily bypassing
operations in different components of the application.

Example usage:
    async with TemporaryBypass(tracker_agent):
        # All tracking operations will be bypassed here
        await some_operation()
    # Tracking returns to normal after the block
"""

from typing import List, Optional
import asyncio

class TemporaryBypass:
    """Context manager to temporarily bypass specified TrackerAgent operations."""
    
    def __init__(self, tracker_agent, operations: Optional[List[str]] = None, logs_manager=None):
        """
        Initialize the bypass context manager.
        
        Args:
            tracker_agent: The TrackerAgent instance to bypass
            operations: Optional list of specific operations to bypass.
                       If None, bypasses all operations.
                       Available operations:
                       - 'uuid_gen': Skip UUID generation
                       - 'timestamp': Skip timestamp formatting
                       - 'activity_dict': Skip activity dictionary creation
                       - 'logging': Skip activity message logging
                       - 'history': Skip adding to internal history
                       - 'disk_write': Skip writing to disk
            logs_manager: Optional LogsManager instance for logging
        """
        self.tracker = tracker_agent
        self.operations = operations
        self.previous_state = {}
        self.logs_manager = logs_manager
        self.initialized = False

    async def initialize(self):
        """Async initialization that can be called after __init__."""
        if self.initialized:
            return

        if self.logs_manager:
            await self.logs_manager.debug("TemporaryBypass initialized")
            await self.logs_manager.debug(f"Operations to bypass: {self.operations if self.operations else 'ALL'}")
        
        self.initialized = True

    async def __aenter__(self):
        """Enable bypass for specified operations and store previous state."""
        # Ensure initialization is complete
        await self.initialize()
            
        # Store current state
        self.previous_state = {
            'bypass_mode': self.tracker._bypass_mode,
            'operations': self.tracker._bypass_operations.copy()
        }
        
        if self.logs_manager:
            await self.logs_manager.debug("Stored previous state:")
            await self.logs_manager.debug(f"bypass_mode: {self.previous_state['bypass_mode']}")
            await self.logs_manager.debug(f"operations: {self.previous_state['operations']}")
        
        # Enable bypass
        self.tracker.enable_bypass(self.operations)
        
        if self.logs_manager:
            await self.logs_manager.debug("Bypass enabled:")
            await self.logs_manager.debug(f"bypass_mode: {self.tracker._bypass_mode}")
            await self.logs_manager.debug(f"operations: {self.tracker._bypass_operations}")
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Restore previous state."""
        if self.logs_manager:
            await self.logs_manager.debug("Restoring previous state:")
            await self.logs_manager.debug(f"bypass_mode: {self.previous_state['bypass_mode']}")
            await self.logs_manager.debug(f"operations: {self.previous_state['operations']}")
        
        self.tracker._bypass_mode = self.previous_state['bypass_mode']
        self.tracker._bypass_operations = self.previous_state['operations']
        
        if self.logs_manager:
            await self.logs_manager.debug("State restored. Current state:")
            await self.logs_manager.debug(f"bypass_mode: {self.tracker._bypass_mode}")
            await self.logs_manager.debug(f"operations: {self.tracker._bypass_operations}")
        
        if exc_type and self.logs_manager:
            await self.logs_manager.error(f"Exception occurred during bypass: {exc_type.__name__}: {str(exc_val)}") 