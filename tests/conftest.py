"""
Test configuration and shared fixtures
"""
import os
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Add pytest-asyncio configuration
pytest_plugins = ["pytest_asyncio"]
asyncio_default_fixture_loop_scope = "function" 