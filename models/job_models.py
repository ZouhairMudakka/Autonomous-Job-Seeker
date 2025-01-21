"""
Job Posting Models (MVP Version)

Pydantic models for representing job postings with minimal fields
needed for MVP: internal job_id, matching_score, and essential info.
Additional fields are commented out for future updates.

We generate 'job_id' internally. If you scrape from LinkedIn or Google,
you can store an external reference or job URL instead.
"""

from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime
from enum import Enum

# Future: from .user_models import WorkMode, EmploymentType  # If you store them in user_models

# For future expansions if needed
class ExperienceLevel(str, Enum):
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"

# Minimal company info for MVP
class CompanyInfo(BaseModel):
    name: str
    # industry: Optional[str] = None
    # size: Optional[str] = None
    # linkedin_url: Optional[HttpUrl] = None
    # website: Optional[HttpUrl] = None
    # description: Optional[str] = None

# Minimal SalaryRange placeholder for future
"""
class SalaryRange(BaseModel):
    currency: str = "USD"
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    period: str = "yearly"
    is_disclosed: bool = False
"""

class JobPosting(BaseModel):
    # Basic info
    job_id: str  # generated internally
    title: str
    company: CompanyInfo
    location: str
    description: str  # job description text

    # Minimal MVP field: matching_score
    matching_score: Optional[float] = None  # used for profile-job matching

    # Additional fields for future expansion (commented out)
    """
    employment_type: EmploymentType
    work_mode: WorkMode
    experience_level: ExperienceLevel
    salary: Optional[SalaryRange] = None

    required_skills: List[str] = []
    preferred_skills: List[str] = []
    required_education: Optional[str] = None
    required_experience_years: Optional[int] = None

    benefits: List[str] = []
    applied_count: Optional[int] = None
    is_quick_apply: bool = False

    posted_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True
    source: str = "linkedin"
    last_updated: datetime = datetime.now()
    """

    # For external reference or apply link
    application_url: Optional[HttpUrl] = None

    class Config:
        # Quick MVP example
        json_schema_extra = {
            "example": {
                "job_id": "internal-001",
                "title": "Senior Software Engineer",
                "company": {
                    "name": "Tech Corp",
                },
                "location": "San Francisco, CA",
                "description": "Looking for a Senior Engineer...",
                "matching_score": 0.85,
                "application_url": "https://www.linkedin.com/jobs/view/123456789"
            }
        }
