"""
Orchestrator Package

This package contains components that manage and coordinate the automation flow.
It includes the main controller and task management functionality.

Components:
- Controller: Main automation flow coordinator
- TaskManager: Handles task queuing and execution
"""

from .controller import Controller
from .task_manager import TaskManager

__all__ = ['Controller', 'TaskManager'] 