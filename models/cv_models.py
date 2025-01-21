"""
CV Data Models (MVP Version)

Pydantic models for representing CV/Resume data structures.
The AI will parse a PDF or other resume format and populate these fields.
CSV is used for initial storage, JSON or DB can be added later.
"""

from pydantic import BaseModel, EmailStr, HttpUrl, Field
from typing import List, Optional, Dict, Any
from datetime import date
from pathlib import Path


class Education(BaseModel):
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    gpa: Optional[float] = None
    description: Optional[str] = None


class Experience(BaseModel):
    company: str
    title: str
    location: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    is_current: bool = False
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)


class Skill(BaseModel):
    name: str
    level: Optional[str] = None
    years: Optional[float] = None


class Language(BaseModel):
    name: str
    proficiency: str


class Certification(BaseModel):
    name: str
    issuer: str
    date_obtained: date
    expiry_date: Optional[date] = None
    credential_id: Optional[str] = None
    credential_url: Optional[HttpUrl] = None


class CVData(BaseModel):
    # File Information
    filename: str = ""
    file_path: Optional[Path] = None
    raw_text: str = ""
    last_modified: Optional[date] = None
    file_size: Optional[int] = None
    
    # Personal Info
    name: str
    email: EmailStr
    phone: str
    location: Optional[str] = None
    linkedin_url: Optional[HttpUrl] = None
    portfolio_url: Optional[HttpUrl] = None
    
    # Summary
    summary: Optional[str] = None
    summary_of_skills: Optional[str] = None
    top_5_skills: List[str] = Field(default_factory=list)
    
    # Detailed Sections
    education: List[Education] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    skills: List[Skill] = Field(default_factory=list)
    languages: List[Language] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    
    # Additional Info
    achievements: List[str] = Field(default_factory=list)
    volunteer_work: List[Experience] = Field(default_factory=list)
    publications: List[str] = Field(default_factory=list)
    
    # Metadata
    parsed_date: Optional[date] = None
    parsing_version: str = "1.0"
    parsing_status: str = "pending"  # pending, success, failed
    parsing_errors: List[str] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "john_doe_resume.pdf",
                "name": "John Doe",
                "email": "john.doe@example.com",
                "phone": "+1-123-456-7890",
                "location": "New York, NY",
                "summary": "Passionate software engineer with 3+ years of experience...",
                "summary_of_skills": "Expert in Python, comfortable with Docker & AWS",
                "top_5_skills": ["Python", "AWS", "Docker", "SQL", "Data Analysis"],
                "education": [
                    {
                        "institution": "MIT",
                        "degree": "BS",
                        "field_of_study": "Computer Science",
                        "start_date": "2018-09-01",
                        "end_date": "2022-05-31",
                        "gpa": 3.8
                    }
                ],
                "experience": [
                    {
                        "company": "TechCorp",
                        "title": "Software Engineer",
                        "start_date": "2022-06-01",
                        "description": "Developed microservices using Python and Docker"
                    }
                ],
                "skills": [
                    {"name": "Python", "level": "Expert", "years": 4.0}
                ],
                "languages": [
                    {"name": "English", "proficiency": "Native"}
                ],
                "certifications": [
                    {
                        "name": "AWS Solutions Architect",
                        "issuer": "Amazon",
                        "date_obtained": "2023-01-15"
                    }
                ]
            }
        }

    def update_file_info(self, file_path: Path) -> None:
        """Update file-related information."""
        self.filename = file_path.name
        self.file_path = file_path
        self.last_modified = date.fromtimestamp(file_path.stat().st_mtime)
        self.file_size = file_path.stat().st_size

    def update_parsing_status(self, status: str, error: Optional[str] = None) -> None:
        """Update parsing status and optionally add error."""
        self.parsing_status = status
        if error:
            self.parsing_errors.append(error)

    def to_user_profile_data(self) -> Dict[str, Any]:
        """Convert CV data to user profile format."""
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "current_title": self.experience[0].title if self.experience else None,
            "current_cv_path": str(self.file_path) if self.file_path else None,
            "parsed_cv_data": {
                "filename": self.filename,
                "skills": [skill.name for skill in self.skills],
                "last_parsed": self.parsed_date.isoformat() if self.parsed_date else None
            }
        }
