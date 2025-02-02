"""
User Interface Package

This package contains all user interface components including
command-line interface and browser extension.

Components:
- CLI: Command-line interface
- MinimalGUI: Graphical user interface for automation control
- extension: Browser extension components
"""

from .cli import CLI
from .minimal_gui import MinimalGUI

__all__ = ['CLI', 'MinimalGUI']
