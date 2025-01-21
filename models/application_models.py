"""
Application Status Models (MVP Version)

Pydantic models for tracking a basic job application lifecycle:
- 'draft' vs 'applied' status only.
- Minimal fields for storing in CSV.
"""

from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime
from enum import Enum
from pydantic import Field

class ApplicationStatus(str, Enum):
    DRAFT = "draft"
    APPLIED = "applied"

class ApplicationTracking(BaseModel):
    # Basic IDs
    application_id: str
    job_id: str
    user_id: str

    # Status & Timestamps
    status: ApplicationStatus
    applied_at: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    # Documents
    resume_used: Optional[str] = None  # Path or identifier for the resume
    cover_letter_used: Optional[str] = None

    # Additional fields for custom usage
    custom_fields: Dict[str, str] = Field(default_factory=dict)

    class Config:
        # Example usage for quick reference
        json_schema_extra = {
            "example": {
                "application_id": "a123456",
                "job_id": "j123456",
                "user_id": "u123456",
                "status": "applied",
                "applied_at": "2025-01-15T14:30:00Z",
                "resume_used": "resume_v3.pdf",
            }
        }
