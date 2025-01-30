"""
Logging Management Module (Async)

Uses aiologger for async log output:
- Daily log file naming (app_YYYYMMDD.log)
- Console output with print for Windows compatibility
- Learning pipeline event logging
- Archive function is commented out (for future use)
"""

import os
import asyncio
from datetime import datetime
from pathlib import Path
import logging
from typing import Optional

# aiologger essentials
from aiologger.logger import Logger
from aiologger.handlers.files import AsyncFileHandler

# For optional color in logs
from colorama import init as colorama_init, Fore, Style

class LogsManager:
    def __init__(self, settings, telemetry_manager=None):
        """
        Args:
            settings (dict): Contains at least:
                {
                    "system": {
                        "data_dir": "./data",
                        "log_level": "INFO" or "DEBUG"
                    }
                }
            telemetry_manager: Optional TelemetryManager instance for tracking events
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
        self.file_handler = None
        self.is_initialized = False

        # Optional: colorize error/critical logs
        # Initialize colorama without auto-reset to prevent handle issues
        colorama_init(autoreset=False)

        # Store telemetry manager
        self.telemetry_manager = telemetry_manager

    async def initialize(self):
        """
        Async init to set up the aiologger's file handler.
        Call this after creating LogsManager in your async setup.
        """
        if self.is_initialized:
            return

        try:
            # Create an async logger with the chosen log level
            self.logger = Logger(name="AppLogger", level=self.log_level)

            # File handler -> daily file
            self.file_handler = AsyncFileHandler(filename=str(self.log_file))
            
            # Add file handler only - console output will be handled separately
            self.logger.add_handler(self.file_handler)
            
            self.is_initialized = True
            
            # Log initialization success to file only
            await self.logger.info("Logging system initialized successfully")
            
        except Exception as e:
            print(f"Failed to initialize logger: {e}")
            raise

    async def shutdown(self):
        """
        Cleanly shut down the logger, flushing any pending logs.
        Should be called before application exit.
        """
        if not self.is_initialized:
            return

        try:
            if self.logger:
                # Remove file handler and close it
                if self.file_handler:
                    self.logger.remove_handler(self.file_handler)
                    await self.file_handler.close()
                
                # Then shutdown logger
                await self.logger.shutdown()
                
            self.is_initialized = False
            
        except Exception as e:
            # Use print since we can't log during shutdown
            print(f"Error during logs cleanup: {e}")

    # -------------------------------------------------------------------------
    # Logging methods for convenience (info, debug, error, etc.)
    # -------------------------------------------------------------------------

    async def info(self, msg: str):
        """Log an INFO-level message."""
        # Print to console with timestamp
        print(f"[INFO] {msg}")
        
        # Log to file if initialized
        if self.logger:
            await self.logger.info(msg)

    async def debug(self, msg: str):
        """Log a DEBUG-level message."""
        if self.log_level == "DEBUG":
            # Print debug messages only if in debug mode
            print(f"[DEBUG] {msg}")
            
            # Log to file if initialized
            if self.logger:
                await self.logger.debug(msg)

    async def warning(self, msg: str):
        """Log a WARNING-level message."""
        # Print to console with color
        print(f"{Fore.YELLOW}[WARNING] {msg}{Style.RESET_ALL}")
        
        # Log to file if initialized
        if self.logger:
            await self.logger.warning(msg)

    async def error(self, msg: str):
        """Log an ERROR-level message."""
        # Print to console with color
        print(f"{Fore.RED}[ERROR] {msg}{Style.RESET_ALL}")
        
        # Log to file if initialized
        if self.logger:
            await self.logger.error(msg)

    async def critical(self, msg: str):
        """Log a CRITICAL-level message."""
        # Print to console with color
        print(f"{Fore.RED}[CRITICAL] {msg}{Style.RESET_ALL}")
        
        # Log to file if initialized
        if self.logger:
            await self.logger.critical(msg)

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

    async def log_learning_event(self, msg: str, confidence: float):
        """Log a learning pipeline event with confidence score."""
        formatted_msg = f"[LEARNING] {msg} (confidence={confidence:.2f})"
        await self.info(formatted_msg)

    async def log_confidence_threshold(self, action: str, new_threshold: float):
        """Log when confidence thresholds are adjusted."""
        msg = f"[LEARNING] Adjusted confidence threshold for {action}: {new_threshold:.2f}"
        await self.info(msg)
