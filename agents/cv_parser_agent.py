"""
CV Parser Agent

This agent is responsible for parsing user resumes/CVs and extracting structured data
for use in automated job applications. It supports:
- PDF parsing (initially)
- Future: .docx, Google Docs
- Optional LLM-based field extraction
"""

import os
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import PyPDF2
from pydantic import BaseModel, Field
import aiofiles
from constants import TimingConstants, Messages


class CVData(BaseModel):
    """Data structure for parsed CV information."""
    raw_text: str = ""  # Added to store original text
    filename: str = ""   # Added to store original filename
    name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    education: List[str] = Field(default_factory=list)
    experience: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)


class CVParserAgent:
    def __init__(self, settings: dict):
        """
        Args:
            settings (dict): Configuration dictionary containing parsing settings
        """
        self.settings = settings
        self.supported_formats = settings.get("supported_formats", [".pdf", ".docx", ".txt"])
        self.use_llm = settings.get("use_llm", False)
        self.data_dir = Path(settings.get("data_dir", "./data"))
        self.parsed_cvs = {}  # Cache for parsed CVs

    async def prepare_cv(self, file_path: str | Path) -> Tuple[Path, CVData]:
        """
        Prepare CV for both parsing and form upload.
        Returns tuple of (verified_path, parsed_data).
        """
        cv_path = Path(file_path)
        if not cv_path.exists():
            raise FileNotFoundError(f"CV not found: {cv_path}")
            
        # Parse if not already cached
        if cv_path not in self.parsed_cvs:
            cv_data = await self.parse_cv(cv_path)
            if cv_data:
                self.parsed_cvs[cv_path] = cv_data
            else:
                raise ValueError(f"Failed to parse CV: {cv_path}")
                
        return cv_path, self.parsed_cvs[cv_path]

    async def parse_cv(self, file_path: str | Path) -> CVData:
        """Parse the CV file and extract structured data."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CV file not found: {file_path}")

        if path.suffix not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {path.suffix}")

        # Extract raw text
        raw_text = await self.extract_text(file_path)

        # Create basic CV data with raw text and filename
        cv_data = CVData(
            raw_text=raw_text,
            filename=path.name
        )

        # If LLM is enabled, enhance the parsing
        if self.use_llm:
            enhanced_data = await self._parse_with_llm(raw_text)
            cv_data = CVData(**{**cv_data.dict(), **enhanced_data.dict()})

        return cv_data

    async def extract_text(self, file_path: str | Path) -> str:
        """Extract raw text from the CV."""
        path = Path(file_path)
        if path.suffix == ".pdf":
            return await self._extract_text_pdf(file_path)
        elif path.suffix == ".docx":
            # Placeholder for future docx parsing
            return ""
        elif path.suffix == ".txt":
            return await self._extract_text_txt(file_path)
        else:
            return ""

    async def _extract_text_pdf(self, file_path: str) -> str:
        """Extract text from a PDF file (synchronously, but wrapped in async)."""
        text_content = ""
        # No true async method for PyPDF2, but we can simulate with an executor if needed.
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text_content += page.extract_text() or ""
                await asyncio.sleep(TimingConstants.PDF_PAGE_PARSE_DELAY)  # Add delay between pages
        return text_content

    async def _extract_text_txt(self, file_path: str) -> str:
        """Extract text from a .txt file asynchronously."""
        content = ""
        async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
            content = await f.read()
            await asyncio.sleep(TimingConstants.FILE_READ_DELAY)  # Add delay after reading
        return content

    async def _parse_with_llm(self, raw_text: str) -> CVData:
        """
        Example placeholder for future LLM-based parsing.
        You might pass the raw_text to a GPT-like model, ask it to extract fields,
        then return a CVData object.
        """
        # Add delay before LLM processing
        await asyncio.sleep(TimingConstants.LLM_PROCESSING_DELAY)
        
        # Pseudocode:
        # prompt = f"Extract name, email, phone, address, etc. from this text: {raw_text}"
        # response = SomeLLM.call(prompt)
        # parse JSON / do parsing
        # return CVData(...)
        return CVData()

    def _basic_parse(self, raw_text: str) -> CVData:
        """
        A minimal parse function without LLM. Could do basic regex or placeholder.
        For now, returns an empty CVData object or a few hardcoded fields.
        """
        # TODO: Implement regex or partial logic here if needed.
        return CVData()


    async def validate_data(self, cv_data: CVData) -> bool:
        """
        Validate extracted CV data (e.g., check email format, phone length).
        Currently just returns True.
        """
        # Add delay for validation
        await asyncio.sleep(TimingConstants.VALIDATION_DELAY)
        
        # You could leverage pydantic's built-in validators or custom checks here.
        return True

    def get_cached_cv(self, cv_path: str | Path) -> Optional[CVData]:
        """Get cached parsed CV data if available."""
        return self.parsed_cvs.get(Path(cv_path))

    async def validate_for_upload(self, cv_path: Path) -> bool:
        """
        Validate CV file for upload (size, format, etc.).
        Returns True if valid for upload.
        """
        try:
            if not cv_path.exists():
                return False
                
            # Check file size (e.g., < 5MB)
            max_size = 5 * 1024 * 1024  # 5MB
            if cv_path.stat().st_size > max_size:
                return False
                
            # Check format
            if cv_path.suffix.lower() not in self.supported_formats:
                return False
                
            return True
            
        except Exception as e:
            print(f"[CVParserAgent] Error validating CV for upload: {e}")
            return False
