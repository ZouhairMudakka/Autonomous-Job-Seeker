"""
Logging Management Module (Async)

Uses aiologger for async log output:
- Daily log file naming (app_YYYYMMDD.log)
- Console output with optional color for errors
- Archive function is commented out (for future use)
"""

import os
import asyncio
from datetime import datetime
from pathlib import Path

# aiologger essentials
from aiologger.logger import Logger
from aiologger.handlers.files import AsyncFileHandler
from aiologger.handlers.streams import AsyncStreamHandler

# For optional color in logs
from colorama import init as colorama_init, Fore, Style

class LogsManager:
    def __init__(self, settings):
        """
        Args:
            settings (dict): Contains at least:
                {
                    "system": {
                        "data_dir": "./data",
                        "log_level": "INFO" or "DEBUG"
                    }
                }
        """
        # Get data_dir from system settings
        system_settings = settings.get('system', {})
        data_dir = system_settings.get('data_dir', './data')
        log_level = system_settings.get('log_level', 'INFO').upper()
        
        # Setup log directory
        self.log_dir = Path(data_dir) / 'logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # For MVP, we allow 'INFO' or 'DEBUG' only
        self.log_level = log_level
        
        # Daily filename approach
        self.log_file = self.log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"

        # We'll create the logger in `initialize()`
        self.logger = None

        # Optional: colorize error/critical logs
        colorama_init(autoreset=True)  # ensures we reset color after each line

    async def initialize(self):
        """
        Async init to set up the aiologger's file + console handlers.
        Call this after creating LogsManager in your async setup.
        """
        # Create an async logger with the chosen log level
        self.logger = Logger(name="AppLogger", level=self.log_level)

        # File handler -> daily file
        file_handler = AsyncFileHandler(filename=str(self.log_file))
        # Console handler -> logs to stdout
        console_handler = AsyncStreamHandler()

        # Add both handlers
        self.logger.add_handler(file_handler)
        self.logger.add_handler(console_handler)

    async def shutdown(self):
        """
        Cleanly shut down the logger, flushing any pending logs.
        Should be called before application exit.
        """
        if self.logger:
            await self.logger.shutdown()

    # -------------------------------------------------------------------------
    # Logging methods for convenience (info, debug, error, etc.)
    # -------------------------------------------------------------------------

    async def info(self, msg: str):
        """Log an INFO-level message."""
        await self.logger.info(self._color_if_needed(msg, level="INFO"))

    async def debug(self, msg: str):
        """Log a DEBUG-level message."""
        if self.log_level == "DEBUG":  # optional check
            await self.logger.debug(self._color_if_needed(msg, level="DEBUG"))

    async def warning(self, msg: str):
        """Log a WARNING-level message."""
        # Could color warnings in yellow if desired
        await self.logger.warning(self._color_if_needed(msg, level="WARNING"))

    async def error(self, msg: str):
        """Log an ERROR-level message."""
        await self.logger.error(self._color_if_needed(msg, level="ERROR"))

    async def critical(self, msg: str):
        """Log a CRITICAL-level message."""
        await self.logger.critical(self._color_if_needed(msg, level="CRITICAL"))

    def _color_if_needed(self, msg: str, level: str) -> str:
        """
        Optionally color errors/critical in red. 
        Info/Debug/Warning remain uncolored for MVP simplicity.
        """
        if level in ["ERROR", "CRITICAL"]:
            return f"{Fore.RED}{msg}{Style.RESET_ALL}"
        # Could color warnings or debug differently if desired
        return msg

    # -------------------------------------------------------------------------
    # Commented-out archive logic for future expansion
    # -------------------------------------------------------------------------
    """
    def archive_logs(self, days_to_keep=30):
        # Move or compress logs older than X days
        # For example, if user wants to keep only 30 days of logs:
        current_time = datetime.now()
        for log_file in self.log_dir.glob("app_*.log"):
            # Parse the date from app_YYYYMMDD.log
            date_str = log_file.stem.split('_')[1]  # e.g. "YYYYMMDD"
            file_date = datetime.strptime(date_str, '%Y%m%d')
            if (current_time - file_date).days > days_to_keep:
                # Could compress or move to 'archive' subfolder
                archive_dir = self.log_dir / 'archive'
                archive_dir.mkdir(exist_ok=True)
                log_file.rename(archive_dir / log_file.name)
    """
