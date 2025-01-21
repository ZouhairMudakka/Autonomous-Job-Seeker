"""
Agents Package

This package contains all automation agents used in the application.
Each agent is responsible for specific automation tasks.

Available Agents:
- LinkedInAgent:       Handles LinkedIn-specific automation
- GeneralAgent:        Handles generic web automation
- CredentialsAgent:    Manages credentials, captcha solving, and future authentication flows
- TrackerAgent:        Tracks job application progress/status
- FormFillerAgent:     Handles form-filling operations (text fields, uploads, dropdowns, etc.)
- CVParserAgent:       Parses CV/Resume documents and extracts structured data
- UserProfileAgent:    Manages user profile data and preferences for job applications
"""

from .linkedin_agent import LinkedInAgent
from .general_agent import GeneralAgent
from .credentials_agent import CredentialsAgent
from .tracker_agent import TrackerAgent
from .form_filler_agent import FormFillerAgent
from .cv_parser_agent import CVParserAgent
from .user_profile_agent import UserProfileAgent

__all__ = [
    "LinkedInAgent",
    "GeneralAgent",
    "CredentialsAgent",
    "TrackerAgent",
    "FormFillerAgent",
    "CVParserAgent",
    "UserProfileAgent"
]
