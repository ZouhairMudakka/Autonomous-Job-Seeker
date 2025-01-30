"""
Text Cleaning Utilities (MVP)

This module provides utilities for cleaning and standardizing text data,
particularly for CV parsing and form filling operations.

Features (MVP):
- Whitespace normalization
- HTML tag removal
- Basic extraction of email, phone, and URLs

Future Expansions:
------------------
- Synergy with regex_utils.py if you want a single source of truth for phone/email patterns.
- More sophisticated HTML cleaning (strip scripts/styles).
- Handling multiple date formats in `standardize_dates()`.
- Multi-lingual or locale-specific text normalization.
"""

import re
from typing import Optional, List
import asyncio
from storage.logs_manager import LogsManager

# If you want to unify patterns, you could import RegexUtils from regex_utils
# and call RegexUtils().extract_emails(...) or similar. For the MVP, we keep local patterns.

class TextCleaner:
    """
    Provides straightforward text cleaning/extraction methods.
    In future expansions, you might unify or reference regex_utils to avoid duplication.
    """

    def __init__(self, logs_manager: LogsManager):
        """Initialize with a LogsManager instance for async logging."""
        self.logs_manager = logs_manager

    async def normalize_whitespace(self, text: str) -> str:
        """
        Standardize whitespace in text by splitting on any whitespace 
        and rejoining with a single space.
        e.g., multiple spaces, tabs, newlines -> single space
        """
        await self.logs_manager.debug(f"Normalizing whitespace for text of length {len(text)}")
        result = ' '.join(text.split())
        await self.logs_manager.debug(f"Whitespace normalization complete. New length: {len(result)}")
        return result

    async def clean_html(self, text: str) -> str:
        """
        Remove HTML tags from text (MVP approach).
        Future expansions might handle advanced cases or keep certain tags.
        """
        await self.logs_manager.debug(f"Cleaning HTML from text of length {len(text)}")
        html_pattern = r'<[^>]+>'
        result = re.sub(html_pattern, '', text)
        await self.logs_manager.debug(f"HTML cleaning complete. New length: {len(result)}")
        return result

    # -------------------------------------------------------------------------
    # Basic Extraction (duplicating some logic from regex_utils for MVP)
    # -------------------------------------------------------------------------
    async def extract_email(self, text: str) -> Optional[str]:
        """
        Extract the first email address from text.
        For multiple addresses, consider using re.findall or referencing regex_utils.
        """
        await self.logs_manager.debug("Attempting to extract email address")
        email_pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
        match = re.search(email_pattern, text)
        if match:
            email = match.group(0)
            await self.logs_manager.debug(f"Successfully extracted email: {email}")
            return email
        await self.logs_manager.debug("No email address found in text")
        return None

    async def extract_phone(self, text: str) -> Optional[str]:
        """
        Extract the first phone number from text (MVP approach).
        Future expansions might handle multiple matches, international formats, etc.
        If you want a single source of truth, unify with regex_utils patterns.
        """
        await self.logs_manager.debug("Attempting to extract phone number")
        phone_pattern = (
            r'(?:\+?\d{1,4}[.\-\s]?)?'
            r'(?:\(?\d{3}\)?[.\-\s]?\d{3}[.\-\s]?\d{4})'
        )
        match = re.search(phone_pattern, text)
        if match:
            phone = match.group(0)
            await self.logs_manager.debug(f"Successfully extracted phone number: {phone}")
            return phone
        await self.logs_manager.debug("No phone number found in text")
        return None

    async def extract_urls(self, text: str) -> List[str]:
        """
        Extract all URLs from the text.
        For advanced scenarios (e.g. capturing ftp://, etc.), unify with regex_utils or expand pattern.
        """
        await self.logs_manager.debug("Attempting to extract URLs")
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+' 
        urls = re.findall(url_pattern, text)
        await self.logs_manager.debug(f"Found {len(urls)} URLs in text")
        return urls

    async def standardize_dates(self, text: str) -> str:
        """
        Placeholder for date format standardization.
        Future expansions might parse mm/dd/yyyy vs. dd/mm/yyyy and unify them.
        """
        await self.logs_manager.debug("Date standardization requested (currently a no-op)")
        return text
