"""
Configuration Package

This package handles application configuration and settings management.

Components:
- settings: Configuration loading and management
"""

from .settings import load_settings

__all__ = ['load_settings']
