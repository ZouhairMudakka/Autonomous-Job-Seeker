"""
Settings Manager Implementation
Handles loading and saving application settings.
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, Any, Optional
from storage.file_utils import atomic_text_writer, file_lock

class SettingsManager:
    def __init__(self, settings_file: Path):
        """Initialize the SettingsManager with a settings file path."""
        self.settings_file = Path(settings_file)
        self._settings: Dict[str, Any] = {}
        self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file."""
        try:
            if self.settings_file.exists():
                with file_lock(self.settings_file), open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                if not isinstance(settings, dict):
                    raise ValueError('Settings must be a JSON object')
                self._settings = settings
            return deepcopy(self._settings)
        except (OSError, ValueError) as e:
            # Do not silently replace unreadable user settings with defaults.
            raise ValueError('Could not load settings file') from e

    def save_settings(self, settings: Optional[Dict[str, Any]] = None):
        """Save settings to file."""
        candidate = deepcopy(self._settings)
        if settings is not None:
            candidate.update(settings)
        with file_lock(self.settings_file), atomic_text_writer(self.settings_file) as f:
            json.dump(candidate, f, indent=4)
        self._settings = candidate

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value by key."""
        return deepcopy(self._settings.get(key, default))

    def set_setting(self, key: str, value: Any):
        """Set a setting value and save to file."""
        self.save_settings({key: value})

    def update_settings(self, settings: Dict[str, Any]):
        """Update multiple settings at once and save to file."""
        self.save_settings(settings)

    def clear_settings(self):
        """Clear all settings."""
        with file_lock(self.settings_file), atomic_text_writer(self.settings_file) as f:
            json.dump({}, f)
        self._settings = {}

    @property
    def settings(self) -> Dict[str, Any]:
        """Get all settings."""
        return deepcopy(self._settings)
