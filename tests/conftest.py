"""
Pytest Configuration and Shared Fixtures

This module provides the core test configuration and shared fixtures for the LinkedIn Job Application Assistant.
It sets up the testing environment, manages resources, and provides common test utilities.

Key Components:
--------------
1. Path Configuration:
   - Sets up project root path
   - Configures Python path for imports
   - Manages test resources and data directories

2. Test Environment:
   - Configures test mode and environment variables
   - Manages test data directory
   - Provides mock settings and credentials

3. GUI Testing Support:
   - Automatic Tkinter window cleanup
   - Window management utilities
   - GUI test configurations

4. Workspace Management:
   - Temporary workspace creation
   - Standard directory structure setup
   - Resource cleanup

Fixtures:
---------
- test_env: Test environment variables
- test_data_dir: Test data directory management
- resource_path: Access to test resources
- auto_cleanup_tk: Automatic Tkinter cleanup
- mock_settings: Application settings for testing
- mock_credentials: Test credentials
- temp_workspace: Temporary workspace with standard structure

Usage:
------
Import fixtures directly in test files:
```python
def test_something(test_env, mock_settings):
    assert test_env['TEST_MODE'] == 'true'
    assert mock_settings['gui_enabled'] == True
```

Notes:
------
- Uses pytest-asyncio for async test support
- Automatically cleans up Tkinter windows after each test
- Provides consistent test environment across all test modules
"""

import pytest
import tkinter as tk
import os
import sys
from pathlib import Path

# Add the project root directory to Python path (using pathlib)
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Add pytest-asyncio configuration
pytest_plugins = ["pytest_asyncio"]
asyncio_default_fixture_loop_scope = "function"

@pytest.fixture(scope="session")
def test_env():
    """Set up test environment variables."""
    # Store original env vars
    original_env = {}
    test_vars = {
        'TEST_MODE': 'true',
        'DATA_DIR': './test_data',
        'LOG_LEVEL': 'DEBUG',
        'PYTEST_RUNNING': 'true'
    }
    
    # Set test env vars
    for key, value in test_vars.items():
        if key in os.environ:
            original_env[key] = os.environ[key]
        os.environ[key] = value
    
    yield test_vars
    
    # Restore original env vars
    for key in test_vars:
        if key in original_env:
            os.environ[key] = original_env[key]
        else:
            del os.environ[key]

@pytest.fixture(scope="session")
def test_data_dir(test_env):
    """Create and manage test data directory."""
    data_dir = project_root / 'test_data'
    data_dir.mkdir(exist_ok=True)
    yield data_dir
    # Cleanup can be added here if needed

@pytest.fixture(scope="session")
def resource_path():
    """Provide access to test resources directory."""
    return project_root / 'tests' / 'resources'

@pytest.fixture(autouse=True)
def auto_cleanup_tk():
    """Automatically clean up Tkinter windows after each test."""
    yield
    for window in tk._default_root.children.copy():
        if isinstance(window, tk.Toplevel):
            window.destroy()
    if tk._default_root:
        tk._default_root.destroy()
        tk._default_root = None

@pytest.fixture
def mock_settings():
    """Provide mock application settings."""
    return {
        'app_name': 'LinkedIn Job Application Assistant',
        'version': '1.0.0',
        'data_dir': './test_data',
        'log_level': 'DEBUG',
        'gui_enabled': True,
        'headless': False,
        'auto_pause_hours': 1.0,
        'default_delay': 1.0
    }

@pytest.fixture
def mock_credentials():
    """Provide mock credentials for testing."""
    return {
        'username': 'test_user',
        'password': 'test_pass',
        'api_key': 'test_key_123',
        'client_id': 'test_client_456'
    }

@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace for file operations."""
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    
    # Create common subdirectories
    (workspace / 'data').mkdir()
    (workspace / 'logs').mkdir()
    (workspace / 'config').mkdir()
    (workspace / 'temp').mkdir()
    
    yield workspace 