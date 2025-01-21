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

# If you want to unify patterns, you could import RegexUtils from regex_utils
# and call RegexUtils().extract_emails(...) or similar. For the MVP, we keep local patterns.

class TextCleaner:
    """
    Provides straightforward text cleaning/extraction methods.
    In future expansions, you might unify or reference regex_utils to avoid duplication.
    """

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """
        Standardize whitespace in text by splitting on any whitespace 
        and rejoining with a single space.
        e.g., multiple spaces, tabs, newlines -> single space
        """
        return ' '.join(text.split())

    @staticmethod
    def clean_html(text: str) -> str:
        """
        Remove HTML tags from text (MVP approach).
        Future expansions might handle advanced cases or keep certain tags.
        """
        html_pattern = r'<[^>]+>'
        return re.sub(html_pattern, '', text)

    # -------------------------------------------------------------------------
    # Basic Extraction (duplicating some logic from regex_utils for MVP)
    # -------------------------------------------------------------------------
    @staticmethod
    def extract_email(text: str) -> Optional[str]:
        """
        Extract the first email address from text.
        For multiple addresses, consider using re.findall or referencing regex_utils.
        """
        email_pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
        match = re.search(email_pattern, text)
        return match.group(0) if match else None

    @staticmethod
    def extract_phone(text: str) -> Optional[str]:
        """
        Extract the first phone number from text (MVP approach).
        Future expansions might handle multiple matches, international formats, etc.
        If you want a single source of truth, unify with regex_utils patterns.
        """
        phone_pattern = (
            r'(?:\+?\d{1,4}[.\-\s]?)?'
            r'(?:\(?\d{3}\)?[.\-\s]?\d{3}[.\-\s]?\d{4})'
        )
        match = re.search(phone_pattern, text)
        return match.group(0) if match else None

    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """
        Extract all URLs from the text.
        For advanced scenarios (e.g. capturing ftp://, etc.), unify with regex_utils or expand pattern.
        """
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+' 
        return re.findall(url_pattern, text)

    @staticmethod
    def standardize_dates(text: str) -> str:
        """
        Placeholder for date format standardization.
        Future expansions might parse mm/dd/yyyy vs. dd/mm/yyyy and unify them.
        """
        # For MVP, return text unchanged.
        return text
