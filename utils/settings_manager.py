"""
Settings Manager Implementation
Handles loading and saving application settings.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

class SettingsManager:
    def __init__(self, settings_file: Path):
        """Initialize the SettingsManager with a settings file path."""
        self.settings_file = settings_file
        self._settings: Dict[str, Any] = {}
        self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    self._settings = json.load(f)
            return self._settings
        except Exception as e:
            print(f"Error loading settings: {str(e)}")
            return {}

    def save_settings(self, settings: Optional[Dict[str, Any]] = None):
        """Save settings to file."""
        try:
            if settings is not None:
                self._settings.update(settings)

            # Ensure directory exists
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.settings_file, 'w') as f:
                json.dump(self._settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {str(e)}")

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value by key."""
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: Any):
        """Set a setting value and save to file."""
        self._settings[key] = value
        self.save_settings()

    def update_settings(self, settings: Dict[str, Any]):
        """Update multiple settings at once and save to file."""
        self._settings.update(settings)
        self.save_settings()

    def clear_settings(self):
        """Clear all settings."""
        self._settings = {}
        self.save_settings()

    @property
    def settings(self) -> Dict[str, Any]:
        """Get all settings."""
        return self._settings.copy() 