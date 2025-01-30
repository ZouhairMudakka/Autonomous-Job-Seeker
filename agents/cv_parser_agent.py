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
from storage.logs_manager import LogsManager


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
    def __init__(self, settings: dict, logs_manager: LogsManager):
        """
        Args:
            settings (dict): Configuration dictionary containing parsing settings
            logs_manager (LogsManager): Instance of LogsManager for async logging
        """
        self.settings = settings
        self.logs_manager = logs_manager
        self.supported_formats = settings.get("supported_formats", [".pdf", ".docx", ".txt"])
        self.use_llm = settings.get("use_llm", False)
        self.data_dir = Path(settings.get("data_dir", "./data"))
        self.parsed_cvs = {}  # Cache for parsed CVs
        
        # Log initialization
        asyncio.create_task(self.logs_manager.info(
            f"Initialized CVParserAgent with supported formats: {self.supported_formats}"
        ))

    async def prepare_cv(self, file_path: str | Path) -> Tuple[Path, CVData]:
        """
        Prepare CV for both parsing and form upload.
        Returns tuple of (verified_path, parsed_data).
        """
        cv_path = Path(file_path)
        await self.logs_manager.info(f"Preparing CV from path: {cv_path}")
        
        if not cv_path.exists():
            await self.logs_manager.error(f"CV file not found: {cv_path}")
            raise FileNotFoundError(f"CV not found: {cv_path}")
            
        # Parse if not already cached
        if cv_path not in self.parsed_cvs:
            await self.logs_manager.debug(f"CV not in cache, parsing: {cv_path}")
            cv_data = await self.parse_cv(cv_path)
            if cv_data:
                self.parsed_cvs[cv_path] = cv_data
                await self.logs_manager.info(f"Successfully parsed and cached CV: {cv_path}")
            else:
                await self.logs_manager.error(f"Failed to parse CV: {cv_path}")
                raise ValueError(f"Failed to parse CV: {cv_path}")
                
        return cv_path, self.parsed_cvs[cv_path]

    async def parse_cv(self, file_path: str | Path) -> CVData:
        """Parse the CV file and extract structured data."""
        path = Path(file_path)
        await self.logs_manager.info(f"Starting CV parsing for: {path}")
        
        if not path.exists():
            await self.logs_manager.error(f"CV file not found: {file_path}")
            raise FileNotFoundError(f"CV file not found: {file_path}")

        if path.suffix not in self.supported_formats:
            await self.logs_manager.error(f"Unsupported file format: {path.suffix}")
            raise ValueError(f"Unsupported file format: {path.suffix}")

        # Extract raw text
        await self.logs_manager.debug(f"Extracting text from {path}")
        raw_text = await self.extract_text(file_path)

        # Create basic CV data with raw text and filename
        cv_data = CVData(
            raw_text=raw_text,
            filename=path.name
        )

        # If LLM is enabled, enhance the parsing
        if self.use_llm:
            await self.logs_manager.info("Using LLM for enhanced parsing")
            enhanced_data = await self._parse_with_llm(raw_text)
            cv_data = CVData(**{**cv_data.dict(), **enhanced_data.dict()})
            await self.logs_manager.info("LLM parsing completed successfully")

        await self.logs_manager.info(f"Successfully parsed CV: {path}")
        return cv_data

    async def extract_text(self, file_path: str | Path) -> str:
        """Extract raw text from the CV."""
        path = Path(file_path)
        await self.logs_manager.info(f"Extracting text from {path}")
        
        try:
            if path.suffix == ".pdf":
                return await self._extract_text_pdf(file_path)
            elif path.suffix == ".docx":
                await self.logs_manager.warning("DOCX parsing not yet implemented")
                return ""
            elif path.suffix == ".txt":
                return await self._extract_text_txt(file_path)
            else:
                await self.logs_manager.error(f"Unsupported file format for text extraction: {path.suffix}")
                return ""
        except Exception as e:
            await self.logs_manager.error(f"Error extracting text from {path}: {str(e)}")
            raise

    async def _extract_text_pdf(self, file_path: str) -> str:
        """Extract text from a PDF file (synchronously, but wrapped in async)."""
        await self.logs_manager.debug(f"Starting PDF text extraction: {file_path}")
        text_content = ""
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                total_pages = len(reader.pages)
                await self.logs_manager.debug(f"Processing {total_pages} pages from PDF")
                
                for page_num, page in enumerate(reader.pages, 1):
                    await self.logs_manager.debug(f"Extracting text from page {page_num}/{total_pages}")
                    text_content += page.extract_text() or ""
                    await asyncio.sleep(TimingConstants.PDF_PAGE_PARSE_DELAY)
                    
            await self.logs_manager.info(f"Successfully extracted text from PDF: {file_path}")
            return text_content
        except Exception as e:
            await self.logs_manager.error(f"Error extracting PDF text from {file_path}: {str(e)}")
            raise

    async def _extract_text_txt(self, file_path: str) -> str:
        """Extract text from a .txt file asynchronously."""
        await self.logs_manager.debug(f"Starting TXT file extraction: {file_path}")
        try:
            content = ""
            async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
                content = await f.read()
                await asyncio.sleep(TimingConstants.FILE_READ_DELAY)
            await self.logs_manager.info(f"Successfully extracted text from TXT file: {file_path}")
            return content
        except Exception as e:
            await self.logs_manager.error(f"Error reading TXT file {file_path}: {str(e)}")
            raise

    async def _parse_with_llm(self, raw_text: str) -> CVData:
        """
        Example placeholder for future LLM-based parsing.
        You might pass the raw_text to a GPT-like model, ask it to extract fields,
        then return a CVData object.
        """
        await self.logs_manager.debug("Starting LLM-based parsing")
        await asyncio.sleep(TimingConstants.LLM_PROCESSING_DELAY)
        
        # Pseudocode:
        # prompt = f"Extract name, email, phone, address, etc. from this text: {raw_text}"
        # response = SomeLLM.call(prompt)
        # parse JSON / do parsing
        # return CVData(...)
        await self.logs_manager.warning("LLM parsing is a placeholder - returning empty CVData")
        return CVData()

    def _basic_parse(self, raw_text: str) -> CVData:
        """
        A minimal parse function without LLM. Could do basic regex or placeholder.
        For now, returns an empty CVData object or a few hardcoded fields.
        """
        # Since this is a synchronous method and is internal, we'll keep it without logging
        # TODO: Implement regex or partial logic here if needed.
        return CVData()

    async def validate_data(self, cv_data: CVData) -> bool:
        """
        Validate extracted CV data (e.g., check email format, phone length).
        Currently just returns True.
        """
        await self.logs_manager.debug(f"Validating CV data for {cv_data.filename}")
        await asyncio.sleep(TimingConstants.VALIDATION_DELAY)
        
        # You could leverage pydantic's built-in validators or custom checks here.
        await self.logs_manager.info(f"Validation completed for {cv_data.filename}")
        return True

    def get_cached_cv(self, cv_path: str | Path) -> Optional[CVData]:
        """Get cached parsed CV data if available."""
        path = Path(cv_path)
        # Since this is a simple sync getter, we'll keep it without logging
        return self.parsed_cvs.get(path)

    async def validate_for_upload(self, cv_path: Path) -> bool:
        """
        Validate CV file for upload (size, format, etc.).
        Returns True if valid for upload.
        """
        await self.logs_manager.info(f"Validating CV for upload: {cv_path}")
        try:
            if not cv_path.exists():
                await self.logs_manager.error(f"CV file does not exist: {cv_path}")
                return False
                
            # Check file size (e.g., < 5MB)
            max_size = 5 * 1024 * 1024  # 5MB
            file_size = cv_path.stat().st_size
            if file_size > max_size:
                await self.logs_manager.warning(
                    f"CV file too large: {file_size/1024/1024:.2f}MB (max: {max_size/1024/1024}MB)"
                )
                return False
                
            # Check format
            if cv_path.suffix.lower() not in self.supported_formats:
                await self.logs_manager.error(
                    f"Unsupported format: {cv_path.suffix} (supported: {self.supported_formats})"
                )
                return False
            
            await self.logs_manager.info(f"CV file {cv_path} is valid for upload")
            return True
            
        except Exception as e:
            await self.logs_manager.error(f"Error validating CV for upload: {str(e)}")
            return False
