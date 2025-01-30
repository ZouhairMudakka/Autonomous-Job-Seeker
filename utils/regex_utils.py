"""
Regex Pattern Utilities (MVP + Comprehensive Notes)

This module provides common regex patterns and utilities for text extraction
and validation, particularly in the job-search domain. We keep it synchronous
for simplicity (regex is generally CPU-bound and doesn't benefit much from async).

Comprehensive Approach for MVP:
- We define flexible patterns for email, phone, URLs, and salary range.
- We note expansions for multiple currencies (USD, EUR, AED, etc.) and experience parsing.
- We handle possible placeholders for "negotiable" or "per hour" salaries.
- We allow phone formats with optional country codes.

Future Expansions:
------------------
1) Use advanced libraries (e.g. `phonenumbers`) for truly robust phone detection.
2) Parse multi-currency explicitly (AED, USD, EUR, GBP, etc.) and handle hourly vs. monthly vs. annual.
3) Parse "negotiable" or "no info" salaries.
4) More sophisticated experience detection (like "3+ yrs", "3-5 years", "2 yrs of experience", etc.).
5) Possibly convert extracted text (like "50k", "AED 30,000 monthly") into structured data (min=..., max=..., period=...).

"""

import re
from typing import Optional, Dict, List, Pattern
from datetime import datetime
from storage.logs_manager import LogsManager

class RegexPatterns:
    """
    Holds commonly used regex patterns for MVP job-search functionality, 
    with expansions for multi-currency salaries, phone variations, etc.
    """

    # Basic Patterns
    EMAIL = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    URL = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'

    # Phone Patterns
    # Allow optional country code like +971 or +1, etc., 
    # then any of these formats: (xxx) xxx-xxxx or xxx-xxx-xxxx, etc.
    # MVP note: This won't be perfect for all countries but is broad enough to catch many formats.
    PHONE = (
        r'(?:\+?\d{1,4}[.\-\s]?)?'   # optional country code
        r'(?:\(?\d{3}\)?[.\-\s]?\d{3}[.\-\s]?\d{4})'  # typical US-like pattern
    )

    # Date Patterns
    # e.g. 1/2/2023 or 12-31-23, allowing either dash or slash
    # In expansions we can handle dd-mm-yyyy vs mm-dd-yyyy, partial years, etc.
    DATE = r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}'

    # Experience Patterns
    # Covering "3 years", "3+ yrs", "3 - 5 years", "10yrs", etc.
    # Future expansions might parse them into numeric ranges.
    EXPERIENCE = (
        r'\d+\+?\s*(?:yrs?|years?)'
        r'(?:\s*-\s*\d+\+?\s*(?:yrs?|years?))?'
    )

    # Salary / Currency Patterns
    # We'll try to handle:
    #  - optional currency symbol or code (e.g. $, USD, AED)
    #  - an amount (1,000 or 1000 or 1k)
    #  - optional range with dash
    #  - optional 'monthly', 'yearly', 'per hour', 'hr', etc.
    # This is not bulletproof, but broad enough for an MVP.
    # We'll also note expansions for "negotiable" or "no info".
    SALARY = (
        r'(?:\$|USD|AED|EUR|GBP)?\s*'
        r'\d{1,3}(?:,\d{3})*'
        r'(?:k)?'
        r'(?:\s*-\s*(?:\$|USD|AED|EUR|GBP)?\s*\d{1,3}(?:,\d{3})*(?:k)?)?'
        r'(?:\s*(?:monthly|yearly|per\s*hour|hr))?'
    )

    @classmethod
    async def compile_patterns(cls, logs_manager: LogsManager) -> Dict[str, Pattern]:
        """
        Compile uppercase string attributes into compiled regex patterns for faster matching.
        """
        await logs_manager.debug("Compiling regex patterns")
        pat_dict = {}
        for name, value in vars(cls).items():
            if name.isupper() and isinstance(value, str):
                try:
                    pat_dict[name] = re.compile(value, re.IGNORECASE)
                    await logs_manager.debug(f"Successfully compiled pattern: {name}")
                except re.error as e:
                    await logs_manager.error(f"Failed to compile pattern {name}: {str(e)}")
                    raise
        await logs_manager.info(f"Compiled {len(pat_dict)} regex patterns")
        return pat_dict


class RegexUtils:
    """
    Provides utilities for performing regex-based extraction and validation
    with the compiled patterns from RegexPatterns.
    """

    def __init__(self, logs_manager: LogsManager):
        """
        Pre-compile patterns once for repeated usage.
        """
        self.logs_manager = logs_manager
        self.patterns = None  # Will be set in initialize()

    async def initialize(self):
        """
        Initialize the regex patterns asynchronously.
        """
        await self.logs_manager.info("Initializing RegexUtils")
        self.patterns = await RegexPatterns.compile_patterns(self.logs_manager)

    async def extract_all(self, text: str) -> Dict[str, List[str]]:
        """
        Extract all pattern matches from text, returning a dict of pattern_name -> list of matches.
        """
        await self.logs_manager.debug("Starting pattern extraction from text")
        results = {}
        for pat_name, compiled_pat in self.patterns.items():
            try:
                matches = compiled_pat.findall(text)
                results[pat_name] = matches
                await self.logs_manager.debug(f"Found {len(matches)} matches for pattern {pat_name}")
            except Exception as e:
                await self.logs_manager.error(f"Error extracting {pat_name} patterns: {str(e)}")
                raise
        
        await self.logs_manager.info(f"Completed pattern extraction with {sum(len(m) for m in results.values())} total matches")
        return results

    async def validate_email(self, email: str) -> bool:
        """
        Strictly validate an email string via the EMAIL pattern.
        """
        await self.logs_manager.debug(f"Validating email: {email}")
        pat = self.patterns.get("EMAIL")
        if not pat:
            await self.logs_manager.error("EMAIL pattern not found")
            return False
        is_valid = bool(pat.fullmatch(email))
        await self.logs_manager.info(f"Email validation result: {is_valid}")
        return is_valid

    async def validate_phone(self, phone: str) -> bool:
        """
        Validate phone number format using the PHONE pattern.
        """
        await self.logs_manager.debug(f"Validating phone number: {phone}")
        pat = self.patterns.get("PHONE")
        if not pat:
            await self.logs_manager.error("PHONE pattern not found")
            return False
        is_valid = bool(pat.fullmatch(phone))
        await self.logs_manager.info(f"Phone validation result: {is_valid}")
        return is_valid

    async def extract_experience(self, text: str) -> List[str]:
        """
        Extract experience expressions like "3+ yrs", "2-4 years", "10yrs" from text.
        """
        await self.logs_manager.debug("Extracting experience expressions from text")
        pat = self.patterns.get("EXPERIENCE")
        if not pat:
            await self.logs_manager.error("EXPERIENCE pattern not found")
            return []
        matches = pat.findall(text)
        await self.logs_manager.info(f"Found {len(matches)} experience expressions")
        return matches

    async def extract_salary(self, text: str) -> List[str]:
        """
        Extract salary references in text.
        """
        await self.logs_manager.debug("Extracting salary expressions from text")
        pat = self.patterns.get("SALARY")
        if not pat:
            await self.logs_manager.error("SALARY pattern not found")
            return []
        matches = pat.findall(text)
        await self.logs_manager.info(f"Found {len(matches)} salary expressions")
        return matches

    async def extract_dates(self, text: str) -> List[str]:
        """
        Extract date strings like 01/31/2023 or 12-20-22 from the text.
        """
        await self.logs_manager.debug("Extracting date expressions from text")
        pat = self.patterns.get("DATE")
        if not pat:
            await self.logs_manager.error("DATE pattern not found")
            return []
        matches = pat.findall(text)
        await self.logs_manager.info(f"Found {len(matches)} date expressions")
        return matches

    async def extract_urls(self, text: str) -> List[str]:
        """
        Extract URLs from text.
        """
        await self.logs_manager.debug("Extracting URLs from text")
        pat = self.patterns.get("URL")
        if not pat:
            await self.logs_manager.error("URL pattern not found")
            return []
        matches = pat.findall(text)
        await self.logs_manager.info(f"Found {len(matches)} URLs")
        return matches

    async def extract_emails(self, text: str) -> List[str]:
        """
        Extract all email addresses from text.
        """
        await self.logs_manager.debug("Extracting email addresses from text")
        pat = self.patterns.get("EMAIL")
        if not pat:
            await self.logs_manager.error("EMAIL pattern not found")
            return []
        matches = pat.findall(text)
        await self.logs_manager.info(f"Found {len(matches)} email addresses")
        return matches
