"""
Configuration Management Module

This module handles loading and managing application configuration settings,
including environment variables and default values.

Required Modules:
- os: For environment variable access
- dotenv: For loading .env files
- sys: For potential exit or error handling if mandatory env vars are missing
"""

import os
import sys
from dotenv import load_dotenv
from pathlib import Path

def _normalize_browser_type(browser_type: str | None) -> tuple[str, dict]:
    """
    Normalize browser type for Playwright compatibility.
    Returns tuple of (playwright_browser_type, launch_options).
    
    Note: Returns (None, {}) if browser_type is None to allow for user prompting.
    """
    # Explicitly handle None/empty cases
    if not browser_type or browser_type.strip() == '':
        return None, {}

    browser_type = browser_type.lower().strip()
    browser_configs = {
        'edge': ('chromium', {'channel': 'msedge'}),
        'chrome': ('chromium', {'channel': 'chrome'}),
        'brave': ('chromium', {'channel': 'brave'}),
        'chromium': ('chromium', {}),
        'firefox': ('firefox', {}),
        'webkit': ('webkit', {})
    }

    # Return None if browser type isn't recognized
    if browser_type not in browser_configs:
        return None, {}

    return browser_configs[browser_type]

def _validate_env_vars(config: dict) -> list[str]:
    """Validate environment variables and return list of warnings."""
    warnings = []
    
    # Check numeric values
    try:
        int(config['browser']['cdp_port'])
    except ValueError:
        warnings.append("Invalid CDP_PORT value. Using default: 9222")
        config['browser']['cdp_port'] = 9222

    try:
        int(config['linkedin']['default_timeout'])
    except ValueError:
        warnings.append("Invalid LINKEDIN_TIMEOUT value. Using default: 10000")
        config['linkedin']['default_timeout'] = 10000

    # Check delay values
    try:
        min_delay = float(config['linkedin']['min_delay'])
        max_delay = float(config['linkedin']['max_delay'])
        if min_delay > max_delay:
            warnings.append("MIN_DELAY is greater than MAX_DELAY. Swapping values.")
            config['linkedin']['min_delay'] = max_delay
            config['linkedin']['max_delay'] = min_delay
    except ValueError:
        warnings.append("Invalid delay values. Using defaults: min=1.0, max=3.0")
        config['linkedin']['min_delay'] = 1.0
        config['linkedin']['max_delay'] = 3.0

    return warnings

def _setup_data_directories(config: dict) -> list[str]:
    """Setup required data directories and return any warnings."""
    warnings = []
    required_dirs = [
        'data',
        'data/logs',
        'data/screenshots',
        'data/cookies'
    ]

    for dir_path in required_dirs:
        path = Path(dir_path)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            warnings.append(f"Failed to create directory '{dir_path}': {e}")

    return warnings

def _validate_critical_settings(config: dict) -> None:
    """Ensure critical settings are properly set."""
    # Validate system settings
    system = config.get('system', {})
    if not system.get('data_dir'):
        print("[Settings] WARNING: No DATA_DIR specified, using './data'")
        system['data_dir'] = './data'
    
    if not system.get('log_level'):
        print("[Settings] WARNING: No LOG_LEVEL specified, using 'INFO'")
        system['log_level'] = 'INFO'
    
    # Create base directories
    try:
        Path(system['data_dir']).mkdir(parents=True, exist_ok=True)
        for subdir in ['logs', 'cookies', 'screenshots']:
            Path(system['data_dir']).joinpath(subdir).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[Settings] WARNING: Failed to create directories: {e}")

def load_settings() -> dict:
    """
    Load and validate all configuration settings.
    
    Note: Browser type will be None if:
    - BROWSER_TYPE is not set in .env
    - BROWSER_TYPE is empty in .env
    - BROWSER_TYPE is invalid in .env
    This allows for user prompting in the browser setup.
    """
    load_dotenv()  # Load variables from .env
    
    # Initialize warnings list
    warnings = []
    
    # Get base data directory FIRST - before any other operations
    base_data_dir = os.getenv('DATA_DIR', './data')
    Path(base_data_dir).mkdir(parents=True, exist_ok=True)  # Ensure it exists
    
    # Get browser type after data dir is set up
    raw_browser_type = os.getenv('BROWSER_TYPE', '').strip() or None
    playwright_browser_type, launch_options = _normalize_browser_type(raw_browser_type)
    
    config = {
        'browser': {
            'type': playwright_browser_type,
            'raw_type': raw_browser_type,
            'launch_options': launch_options or {},
            'headless': os.getenv('BROWSER_HEADLESS', 'False').lower() == 'true',
            'cdp_port': os.getenv('CDP_PORT', '9222'),
            'viewport': {
                'width': int(os.getenv('VIEWPORT_WIDTH', '1280')),
                'height': int(os.getenv('VIEWPORT_HEIGHT', '720'))
            },
            'user_agent': os.getenv('USER_AGENT', ''),
            'attach_existing': os.getenv('ATTACH_EXISTING', 'False').lower() == 'true',
            'should_prompt': playwright_browser_type is None,
            'data_dir': base_data_dir  # Ensure data_dir is set
        },
        'linkedin': {
            'email': os.getenv('LINKEDIN_EMAIL', ''),  # Empty string if not set
            'password': os.getenv('LINKEDIN_PASSWORD', ''),  # Empty string if not set
            'default_timeout': int(os.getenv('LINKEDIN_TIMEOUT', '10000')),
            'min_delay': float(os.getenv('LINKEDIN_MIN_DELAY', '1.0')),
            'max_delay': float(os.getenv('LINKEDIN_MAX_DELAY', '3.0')),
            'max_retries': int(os.getenv('LINKEDIN_MAX_RETRIES', '3'))
        },
        'api': {
            'key': os.getenv('API_KEY', ''),  # Empty string if not set
            'base_url': os.getenv('API_BASE_URL', 'http://localhost'),  # Default value
            'timeout': int(os.getenv('API_TIMEOUT', '30'))  # Default 30 seconds
        },
        'system': {
            'debug_mode': os.getenv('DEBUG_MODE', 'False').lower() == 'true',
            'log_level': os.getenv('LOG_LEVEL', 'INFO').upper(),
            'data_dir': base_data_dir,  # Also set here
            'max_retries': int(os.getenv('MAX_RETRIES', '3')),
            'retry_delay': float(os.getenv('RETRY_DELAY', '1.0'))
        },
        'telemetry': {
            'enabled': os.getenv('TELEMETRY_ENABLED', 'true').lower() == 'true',
            'storage_path': os.getenv('TELEMETRY_STORAGE_PATH', './data/telemetry')
        }
    }
    
    # Add validation for critical settings
    _validate_critical_settings(config)
    
    # Setup data directories AFTER config is created
    warnings.extend(_setup_data_directories(config))
    
    # Validate environment variables
    warnings.extend(_validate_env_vars(config))
    
    # Print any warnings
    for warning in warnings:
        print(f"[Settings] WARNING: {warning}")
    
    return config
