"""
Job Matching Utility Functions

This module will contain utilities for job matching and scoring, currently located in model_utils.py.
Will be split from model_utils.py as the codebase grows beyond MVP stage.

Future functionality:
- Job-profile match scoring
- Skills compatibility analysis
- Experience level matching
- Location and work mode compatibility
- Salary range validation
"""

from typing import Dict
from utils.telemetry import TelemetryManager

class JobMatcher:
    def __init__(self, settings: Dict):
        self.settings = settings
        self.telemetry = TelemetryManager(settings)

    async def calculate_match_score(self, job_posting, user_profile):
        match_score = await self._compute_match_score(job_posting, user_profile)
        
        await self.telemetry.track_job_match(
            job_id=job_posting.id,
            match_score=match_score,
            criteria={
                'skills_match': self.skills_match_score,
                'experience_match': self.experience_match_score,
                'location_match': self.location_match_score,
                'requirements_match': self.requirements_match_score
            }
        )
        
        return match_score

# TODO: Move JobMatchUtils class from model_utils.py here when splitting utilities 