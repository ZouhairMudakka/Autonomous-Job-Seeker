"""Validated user profiles with lossless CSV and atomic JSON persistence."""

import ast
import csv
from datetime import datetime
import json
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from storage.file_utils import atomic_text_writer, file_lock, safe_child
from storage.logs_manager import LogsManager


class UserProfile(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    location: Optional[str] = None
    current_title: Optional[str] = None
    preferred_titles: List[str] = Field(default_factory=list)
    preferred_locations: List[str] = Field(default_factory=list)
    min_salary: Optional[int] = Field(default=None, ge=0)
    remote_preference: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    current_cv_path: Optional[str] = None
    cv_last_updated: Optional[datetime] = None
    parsed_cv_data: Optional[dict] = None


class UserProfileAgent:
    def __init__(self, settings: dict, logs_manager: LogsManager):
        self.settings = settings
        data_dir = Path(settings.get('system', {}).get('data_dir', settings.get('data_dir', 'data')))
        self.storage_path = Path(settings.get('profile_storage_path', data_dir / 'profiles'))
        self.storage_format = settings.get('profile_storage_format', 'csv').lower()
        if self.storage_format not in {'csv', 'json'}:
            raise ValueError('profile_storage_format must be csv or json')
        self.logs_manager = logs_manager
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._lock = file_lock(self.storage_path / 'profiles')

    def _json_path(self, user_id):
        # Validate the ID itself as well as the final filename (e.g. empty IDs).
        safe_child(self.storage_path, user_id)
        return safe_child(self.storage_path, f'{user_id}.json')

    @property
    def _csv_path(self):
        return safe_child(self.storage_path, 'profiles.csv')

    @staticmethod
    def _encode_profile(profile):
        data = profile.model_dump(mode='json')
        for key, value in data.items():
            if isinstance(value, (list, dict)):
                data[key] = json.dumps(value, ensure_ascii=False)
        return data

    @staticmethod
    def _decode_profile(row):
        data = dict(row)
        for key in ('preferred_titles', 'preferred_locations', 'parsed_cv_data'):
            value = data.get(key)
            if value:
                try:
                    data[key] = json.loads(value)
                except json.JSONDecodeError:
                    # Read CSVs produced by the old writer without using eval.
                    data[key] = ast.literal_eval(value)
            elif key == 'parsed_cv_data':
                data[key] = None
            else:
                data[key] = []
        for key, field in UserProfile.model_fields.items():
            if data.get(key) == '' and field.default is None:
                data[key] = None
        return UserProfile(**data)

    def _read_csv(self):
        if not self._csv_path.exists() or self._csv_path.stat().st_size == 0:
            return []
        with self._csv_path.open(encoding='utf-8', newline='') as stream:
            return [self._decode_profile(row) for row in csv.DictReader(stream)]

    def _write_csv(self, profiles):
        with atomic_text_writer(self._csv_path, newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(UserProfile.model_fields))
            writer.writeheader()
            writer.writerows(self._encode_profile(profile) for profile in profiles)

    def _get(self, user_id):
        path = self._json_path(user_id)
        if self.storage_format == 'csv':
            return next((p for p in self._read_csv() if p.user_id == user_id), None)
        if not path.exists():
            return None
        with path.open(encoding='utf-8') as stream:
            return UserProfile(**json.load(stream))

    def _save(self, profile):
        path = self._json_path(profile.user_id)
        if self.storage_format == 'csv':
            profiles = [p for p in self._read_csv() if p.user_id != profile.user_id]
            profiles.append(profile)
            self._write_csv(profiles)
        else:
            with atomic_text_writer(path) as stream:
                stream.write(profile.model_dump_json(indent=2))

    async def create_profile(self, profile_data: dict) -> UserProfile:
        profile = UserProfile(**profile_data)
        with self._lock:
            if self._get(profile.user_id) is not None:
                raise ValueError('A profile with this user_id already exists')
            self._save(profile)
        await self.logs_manager.info('Created user profile')
        return profile

    async def update_profile(self, user_id: str, updates: dict) -> UserProfile:
        if 'user_id' in updates and updates['user_id'] != user_id:
            raise ValueError('user_id cannot be changed')
        with self._lock:
            existing = self._get(user_id)
            if existing is None:
                raise ValueError('Profile not found')
            data = existing.model_dump()
            data.update(updates)
            data['created_at'] = existing.created_at
            data['updated_at'] = datetime.now()
            profile = UserProfile(**data)
            self._save(profile)
        await self.logs_manager.info('Updated user profile')
        return profile

    async def get_profile(self, user_id: str) -> Optional[UserProfile]:
        with self._lock:
            return self._get(user_id)

    async def delete_profile(self, user_id: str) -> bool:
        with self._lock:
            path = self._json_path(user_id)
            if self.storage_format == 'csv':
                profiles = self._read_csv()
                remaining = [p for p in profiles if p.user_id != user_id]
                if len(remaining) == len(profiles):
                    return False
                self._write_csv(remaining)
            else:
                if not path.exists():
                    return False
                path.unlink()
        await self.logs_manager.info('Deleted user profile')
        return True

    async def validate_profile(self, profile: UserProfile) -> bool:
        self._json_path(profile.user_id)
        UserProfile.model_validate(profile.model_dump())
        return True

    async def update_cv_info(self, user_id: str, cv_path: str, cv_data: dict) -> UserProfile:
        return await self.update_profile(user_id, {
            'current_cv_path': str(cv_path),
            'cv_last_updated': datetime.now(),
            'parsed_cv_data': {
                'filename': cv_data.get('filename'),
                'skills': cv_data.get('skills', []),
                'last_parsed': datetime.now().isoformat(),
            },
        })
