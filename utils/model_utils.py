"""
Model Utility Functions (Async + Moderate Strictness + MVP)

Q2: Business/User Perspective on Pydantic Strictness
-----------------------------------------------------
From a user perspective, "strict" modes or custom JSON encoders in Pydantic 
help ensure data is in exactly the format we expect (reducing errors in production). 
If data is strictly validated, users or other agents might see more validation 
errors if they pass incorrect data. If 'coerce_types' is used, we’re more lenient 
(e.g., turning "123" into 123). For an MVP, a moderate approach is typically 
sufficient: raise errors on obviously invalid fields, but allow slight flexibility 
for minor mismatches. Long-term, a stricter setup can reduce unexpected data 
issues in production.

Note on Future Splitting
------------------------
We have created the following placeholder utility files for post-MVP usage:
- cv_utils.py        (Will host CVUtils methods)
- job_match_utils.py (Will host JobMatchUtils methods)
- application_utils.py (Will host ApplicationUtils methods)
- data_export_utils.py (Will host DataExportUtils methods)

Currently, all utility classes remain here in model_utils.py for the MVP. 
When the codebase grows, we will move each class to its respective file.
"""

import asyncio
import json
from datetime import datetime, date
from typing import Dict, List, Type, TypeVar, Optional, Any

# Pydantic v2 usage with moderate strictness:
# We won't forcibly coerce totally incorrect types, 
# but we allow small flexibility for typical field usage.
# For instance, we might set each model's config to strict mode 
# or just rely on defaults. This code simply notes we adopt a moderate stance.

from models.cv_models import CVData, Education, Experience, Skill
from models.user_models import UserProfile, JobPreference
from models.job_models import JobPosting, CompanyInfo
from models.application_models import ApplicationTracking, Interview

ModelType = TypeVar('ModelType', CVData, UserProfile, JobPosting, ApplicationTracking)

class ModelUtils:
    """
    Basic model serialization/deserialization with async stubs.
    """

    @staticmethod
    async def to_dict(model: ModelType) -> Dict[str, Any]:
        """
        Convert any model instance to a dictionary with datetime handling (async).
        """
        return json.loads(await ModelUtils.to_json(model))

    @staticmethod
    async def to_json(model: ModelType) -> str:
        """
        Convert any model instance to a JSON string (async).
        """
        return model.model_dump_json()

    @staticmethod
    async def from_dict(data: Dict[str, Any], model_class: Type[ModelType]) -> ModelType:
        """
        Create a model instance from a dictionary (async).
        If model_class uses moderate strictness, some minor type coersion might be allowed,
        but major mismatches will raise validation errors.
        """
        return model_class.model_validate(data)

    @staticmethod
    async def from_json(json_str: str, model_class: Type[ModelType]) -> ModelType:
        """
        Create a model instance from a JSON string (async).
        """
        return model_class.model_validate_json(json_str)


class CVUtils:
    """
    CV/Resume-related utilities. 
    (Will move to cv_utils.py post-MVP)
    """

    @staticmethod
    async def merge_experiences(experiences: List[Experience]) -> List[Experience]:
        """
        Merge overlapping or continuous experiences at the same company (async).
        Future expansions:
        - Handle partial overlaps more gracefully
        - Possibly unify multiple 'current' experiences if end_date=None in each
        """
        if not experiences:
            return []

        sorted_exp = sorted(experiences, key=lambda x: (x.company, x.start_date))
        merged = []
        current = sorted_exp[0]

        for next_exp in sorted_exp[1:]:
            if (current.company == next_exp.company and
                current.title == next_exp.title and
                (current.end_date is None or next_exp.start_date <= current.end_date)):
                # Merge
                if current.end_date and next_exp.end_date:
                    current.end_date = max(current.end_date, next_exp.end_date)
                else:
                    current.end_date = None

                current.description.extend(next_exp.description)
                current.technologies.extend(next_exp.technologies)
            else:
                merged.append(current)
                current = next_exp

        merged.append(current)
        return merged

    @staticmethod
    async def calculate_total_experience(experiences: List[Experience]) -> float:
        """
        Calculate total years of experience (async).
        """
        total_days = 0
        for exp in experiences:
            start = exp.start_date
            end = exp.end_date if exp.end_date else date.today()
            total_days += (end - start).days

        return round(total_days / 365.25, 1)


class JobMatchUtils:
    """
    Job matching and scoring utilities.
    (Will move to job_match_utils.py post-MVP)
    """

    @staticmethod
    async def calculate_match_score(job: JobPosting, profile: UserProfile) -> float:
        """
        Calculate match score between job and user profile (async).
        """
        score = 0.0
        weights = {
            'title_match': 0.3,
            'skills_match': 0.3,
            'experience_match': 0.2,
            'location_match': 0.1,
            'work_mode_match': 0.1
        }

        # Title match
        if any(title.lower() in job.title.lower() for title in profile.job_preferences.titles):
            score += weights['title_match']

        # If job has a 'work_mode' attribute
        if hasattr(job, 'work_mode') and hasattr(profile.job_preferences, 'work_modes'):
            if job.work_mode in profile.job_preferences.work_modes:
                score += weights['work_mode_match']

        # Location match
        if any(loc.lower() in job.location.lower() for loc in profile.job_preferences.locations):
            score += weights['location_match']

        # In MVP, we skip skill checking or experience comparison
        return round(score, 2)


class ApplicationUtils:
    """
    Utilities for application tracking.
    (Will move to application_utils.py post-MVP)
    """

    @staticmethod
    async def should_follow_up(application: ApplicationTracking) -> bool:
        """
        Determine if application needs follow-up (async).
        Future expansions: incorporate user’s preference or typical response times.
        """
        if not application.last_contact_date:
            return False

        days_since_contact = (datetime.now() - application.last_contact_date).days
        follow_up_threshold = 7  # MVP default
        if hasattr(application, 'follow_up_count') and application.follow_up_count < 3:
            return days_since_contact >= follow_up_threshold
        return False

    @staticmethod
    async def get_application_metrics(applications: List[ApplicationTracking]) -> Dict[str, float]:
        """
        Calculate application metrics (async).
        """
        total = len(applications)
        if not total:
            return {
                'total': 0,
                'response_rate': 0.0,
                'interview_rate': 0.0,
                'average_response_time': 0.0
            }

        responses = sum(1 for app in applications if app.time_to_response is not None)
        interviews = sum(1 for app in applications if getattr(app, 'interviews', None))
        avg_response_time = 0.0
        if responses:
            sum_responses = sum((app.time_to_response or 0) for app in applications 
                                if app.time_to_response is not None)
            avg_response_time = sum_responses / responses

        return {
            'total': total,
            'response_rate': round((responses / total) * 100, 1),
            'interview_rate': round((interviews / total) * 100, 1),
            'average_response_time': round(avg_response_time, 1)
        }


class DataExportUtils:
    """
    Future data export & reporting utilities (commented out for MVP).
    (Will move to data_export_utils.py post-MVP)
    """

    """
    @staticmethod
    async def export_applications_to_csv(applications: List[ApplicationTracking],
                                         output_path: Path) -> str:
        # Export applications to CSV format
        # For now, commented out in the MVP.

        return str(output_path)

    @staticmethod
    async def generate_application_report(application: ApplicationTracking) -> Dict:
        # Generate a detailed report for an application
        # For now, commented out in the MVP.

        return {}
    """
