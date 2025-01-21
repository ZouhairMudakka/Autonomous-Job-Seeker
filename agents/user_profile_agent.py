"""
User Profile Agent

This agent manages user profile data and preferences for job applications.
It provides a centralized way to store and retrieve user information.

Features:
- Profile data management
- Preference storage
- Data validation
- Profile versioning (future)
- CSV storage (for MVP), easy to switch to JSON or DB later
"""

import csv
import json
import os
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import asyncio
from constants import TimingConstants, Messages

class UserProfile(BaseModel):
    """User profile data structure"""
    user_id: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    location: Optional[str] = None
    current_title: Optional[str] = None
    preferred_titles: List[str] = Field(default_factory=list)
    preferred_locations: List[str] = Field(default_factory=list)
    min_salary: Optional[int] = None
    remote_preference: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Add CV-related fields
    current_cv_path: Optional[str] = None
    cv_last_updated: Optional[datetime] = None
    parsed_cv_data: Optional[dict] = None  # Store basic CV metadata

    # Additional validation can go here, or custom validators below

class UserProfileAgent:
    def __init__(self, settings: dict):
        """
        Args:
            settings (dict): e.g., {
                "profile_storage_path": "data/profiles",
                "profile_storage_format": "csv" or "json"
            }
        """
        self.settings = settings
        self.storage_path = settings.get("profile_storage_path", "data/profiles")
        self.storage_format = settings.get("profile_storage_format", "csv")
        self.default_timeout = TimingConstants.DEFAULT_TIMEOUT
        os.makedirs(self.storage_path, exist_ok=True)

    async def create_profile(self, profile_data: dict) -> UserProfile:
        """Create a new user profile and store it."""
        await asyncio.sleep(TimingConstants.ACTION_DELAY)
        profile = UserProfile(**profile_data)
        await self.validate_profile(profile)

        if self.storage_format == "csv":
            await self._save_profile_csv(profile)
        else:
            await self._save_profile_json(profile)

        await asyncio.sleep(TimingConstants.FILE_UPLOAD_DELAY)
        return profile

    async def update_profile(self, user_id: str, updates: dict) -> UserProfile:
        """Update an existing user profile."""
        await asyncio.sleep(TimingConstants.ACTION_DELAY)
        
        existing_profile = await self.get_profile(user_id)
        if not existing_profile:
            raise ValueError(f"Profile for user_id '{user_id}' not found.")

        updated_data = existing_profile.dict()
        updated_data.update(updates)
        updated_data["updated_at"] = datetime.now()

        new_profile = UserProfile(**updated_data)
        await self.validate_profile(new_profile)

        if self.storage_format == "csv":
            await self._update_profile_csv(existing_profile, new_profile)
        else:
            await self._save_profile_json(new_profile)

        await asyncio.sleep(TimingConstants.FILE_UPLOAD_DELAY)
        return new_profile

    async def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Retrieve a user profile from storage."""
        await asyncio.sleep(TimingConstants.ACTION_DELAY)
        
        profile = None
        if self.storage_format == "csv":
            profile = await self._get_profile_csv(user_id)
        else:
            profile = await self._get_profile_json(user_id)

        await asyncio.sleep(TimingConstants.TEXT_EXTRACTION_DELAY)
        return profile

    async def delete_profile(self, user_id: str) -> bool:
        """Delete user profile from storage."""
        await asyncio.sleep(TimingConstants.ACTION_DELAY)
        
        result = False
        if self.storage_format == "csv":
            result = await self._delete_profile_csv(user_id)
        else:
            result = await self._delete_profile_json(user_id)

        await asyncio.sleep(TimingConstants.FILE_UPLOAD_DELAY)
        return result

    async def validate_profile(self, profile: UserProfile) -> bool:
        """Validate profile data. Pydantic checks email format, etc."""
        # You could add additional logic here if needed.
        # If invalid, raise ValidationError or return False.
        return True

    async def update_cv_info(self, user_id: str, cv_path: str, cv_data: dict) -> UserProfile:
        """Update user profile with CV information."""
        await asyncio.sleep(TimingConstants.ACTION_DELAY)
        
        profile = await self.get_profile(user_id)
        if not profile:
            raise ValueError(f"Profile for user_id '{user_id}' not found.")

        updates = {
            'current_cv_path': str(cv_path),
            'cv_last_updated': datetime.now(),
            'parsed_cv_data': {
                'filename': cv_data.get('filename'),
                'skills': cv_data.get('skills', []),
                'last_parsed': datetime.now().isoformat()
            }
        }

        return await self.update_profile(user_id, updates)

    # -------------------------------------------------------------------------
    # CSV Storage Methods
    # -------------------------------------------------------------------------
    async def _save_profile_csv(self, profile: UserProfile):
        """Append a new profile to CSV file."""
        await asyncio.sleep(TimingConstants.ACTION_DELAY)
        
        csv_file_path = os.path.join(self.storage_path, "profiles.csv")
        file_exists = os.path.isfile(csv_file_path)
        header = list(profile.dict().keys())

        async with asyncio.Lock():
            with open(csv_file_path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=header)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(profile.dict())
                
        await asyncio.sleep(TimingConstants.FILE_UPLOAD_DELAY)

    async def _get_profile_csv(self, user_id: str) -> Optional[UserProfile]:
        await asyncio.sleep(TimingConstants.ACTION_DELAY)
        
        csv_file_path = os.path.join(self.storage_path, "profiles.csv")
        if not os.path.isfile(csv_file_path):
            return None

        async with asyncio.Lock():
            with open(csv_file_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["user_id"] == user_id:
                        await asyncio.sleep(TimingConstants.TEXT_EXTRACTION_DELAY)
                        return UserProfile(**row)
        return None

    async def _update_profile_csv(self, old_profile: UserProfile, new_profile: UserProfile):
        await asyncio.sleep(TimingConstants.ACTION_DELAY)
        
        csv_file_path = os.path.join(self.storage_path, "profiles.csv")
        if not os.path.isfile(csv_file_path):
            return

        profiles = []
        async with asyncio.Lock():
            with open(csv_file_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["user_id"] == old_profile.user_id:
                        profiles.append(new_profile.dict())
                    else:
                        profiles.append(row)

            header = list(new_profile.dict().keys())
            with open(csv_file_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writeheader()
                for p in profiles:
                    writer.writerow(p)
                    
        await asyncio.sleep(TimingConstants.FILE_UPLOAD_DELAY)

    async def _delete_profile_csv(self, user_id: str) -> bool:
        csv_file_path = os.path.join(self.storage_path, "profiles.csv")
        if not os.path.isfile(csv_file_path):
            return False

        found = False
        updated_profiles = []
        async with asyncio.Lock():
            with open(csv_file_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["user_id"] == user_id:
                        found = True
                        continue
                    updated_profiles.append(row)

            if found:
                header = updated_profiles[0].keys() if updated_profiles else []
                with open(csv_file_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=header)
                    writer.writeheader()
                    for p in updated_profiles:
                        writer.writerow(p)

        return found

    # -------------------------------------------------------------------------
    # JSON Storage Methods
    # -------------------------------------------------------------------------
    async def _save_profile_json(self, profile: UserProfile):
        """
        For JSON approach, we could do one file per user or a single `profiles.json`.
        Here we do one file per user for simplicity.
        """
        json_file_path = os.path.join(self.storage_path, f"{profile.user_id}.json")
        async with asyncio.Lock():
            with open(json_file_path, mode="w", encoding="utf-8") as f:
                json.dump(profile.dict(), f, indent=2, default=str)

    async def _get_profile_json(self, user_id: str) -> Optional[UserProfile]:
        json_file_path = os.path.join(self.storage_path, f"{user_id}.json")
        if not os.path.isfile(json_file_path):
            return None

        async with asyncio.Lock():
            with open(json_file_path, mode="r", encoding="utf-8") as f:
                data = json.load(f)
                return UserProfile(**data)

    async def _delete_profile_json(self, user_id: str) -> bool:
        json_file_path = os.path.join(self.storage_path, f"{user_id}.json")
        if not os.path.isfile(json_file_path):
            return False
        async with asyncio.Lock():
            os.remove(json_file_path)
        return True
