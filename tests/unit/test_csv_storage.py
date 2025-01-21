"""
Unit Tests for LinkedIn Agent

Tests the functionality of the LinkedInAgent class.
"""

import pytest
from agents.linkedin_agent import LinkedInAgent
from unittest.mock import MagicMock

@pytest.fixture
def agent():
    credentials = {
        'email': 'test@example.com',
        'password': 'test_password'
    }
    return LinkedInAgent(credentials)

def test_initialization(agent):
    assert agent.email == 'test@example.com'
    assert agent.password == 'test_password'
    assert agent.driver is None

def test_login_success(agent):
    # Mock Selenium components
    agent.driver = MagicMock()
    agent.driver.find_element.return_value = MagicMock()
    
    agent.login()
    assert agent.driver.get.called_with('https://www.linkedin.com/login') 