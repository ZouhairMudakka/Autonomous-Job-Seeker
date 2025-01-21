"""
Storage Package

This package handles all data persistence operations including CSV storage
and logging functionality.

Components:
- CSVStorage: Handles CSV file operations
- LogsManager: Manages application logging
"""

from .csv_storage import CSVStorage
from .logs_manager import LogsManager

__all__ = ['CSVStorage', 'LogsManager'] 