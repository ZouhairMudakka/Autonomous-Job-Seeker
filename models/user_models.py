"""
User Profile Models (MVP Version)

Pydantic models for representing user profile data and preferences.
Minimal approach for MVP: essential fields + job preferences (titles, work modes, locations).
Other fields are commented out for future expansion.
"""

from pydantic import BaseModel, EmailStr, HttpUrl, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

# If you still want to keep them for partial usage, you can uncomment as needed
class WorkMode(str, Enum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"
    FLEXIBLE = "flexible"

# For future usage, if needed
"""
class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
"""

"""
class SalaryPreference(BaseModel):
    currency: str = "USD"
    minimum: int
    maximum: Optional[int] = None
    period: str = "yearly"
"""

class JobPreference(BaseModel):
    titles: List[str]
    work_modes: List[WorkMode] = []
    locations: List[str] = []

    # Future expansions:
    """
    industries: List[str] = []
    employment_types: List[EmploymentType] = []
    salary: Optional[SalaryPreference] = None
    willing_to_relocate: bool = False
    notice_period_days: Optional[int] = None
    """

class UserProfile(BaseModel):
    # Basic Information
    user_id: str
    email: EmailStr
    name: str
    phone: Optional[str] = None
    location: Optional[str] = None

    # Job Search Preferences
    job_preferences: JobPreference

    # For future expansions:
    """
    # Professional Information
    current_title: Optional[str] = None
    years_of_experience: Optional[float] = None
    linkedin_url: Optional[HttpUrl] = None
    github_url: Optional[HttpUrl] = None
    portfolio_url: Optional[HttpUrl] = None

    # Application History
    applied_jobs: List[str] = []
    saved_jobs: List[str] = []

    # System Fields
    """

    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "u123456",
                "email": "user@example.com",
                "name": "Jane Smith",
                "phone": "+1-555-555-5555",
                "location": "New York, NY",
                "job_preferences": {
                    "titles": ["Software Engineer"],
                    "work_modes": ["remote"],
                    "locations": ["San Francisco, CA", "Remote"]
                },
                "is_active": True
            }
        }
