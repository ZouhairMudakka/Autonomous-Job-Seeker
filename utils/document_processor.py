"""
Document Processing Utility

Handles various document formats:
- PDF (resumes, CVs)
- DOCX (future)
- TXT (future)

Features:
- Text extraction
- Basic parsing
- Future: structured data extraction
"""

import PyPDF2
from pathlib import Path
from typing import Optional

from storage.logs_manager import LogsManager

class DocumentProcessor:
    def __init__(self, settings: dict, logs_manager: LogsManager):
        """
        Initialize with application settings.
        
        Args:
            settings (dict): Application settings containing paths and configurations
            logs_manager (LogsManager): Instance of LogsManager for async logging
        """
        self.settings = settings
        self.data_dir = Path(settings.get('data_dir', './data'))
        self.parsed_cvs = {}  # Cache for parsed CVs
        self.logs_manager = logs_manager

    async def extract_text_from_pdf(self, pdf_path: str | Path) -> Optional[str]:
        """
        Extract text content from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            str: Extracted text or None if extraction failed
        """
        try:
            await self.logs_manager.debug(f"Starting text extraction from PDF: {pdf_path}")
            text = ""
            with open(pdf_path, 'rb') as f:
                await self.logs_manager.debug(f"Successfully opened PDF file: {pdf_path}")
                pdf_reader = PyPDF2.PdfReader(f)
                total_pages = len(pdf_reader.pages)
                await self.logs_manager.debug(f"PDF has {total_pages} pages")
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    await self.logs_manager.debug(f"Processing page {page_num}/{total_pages}")
                    page_text = page.extract_text() or ""
                    text += page_text
            
            if text:
                text_length = len(text.strip())
                await self.logs_manager.debug(f"Successfully extracted {text_length} characters from PDF: {pdf_path}")
                return text.strip()
            else:
                await self.logs_manager.warning(f"No text content found in PDF: {pdf_path}")
                return None
            
        except Exception as e:
            await self.logs_manager.error(f"Error extracting text from PDF {pdf_path}: {str(e)}")
            return None

    async def process_cv(self, cv_path: str | Path) -> dict:
        """
        Process a CV/resume and extract structured information.
        
        Args:
            cv_path: Path to the CV file (PDF)
            
        Returns:
            dict: Structured CV data or empty dict if processing failed
        """
        try:
            await self.logs_manager.info(f"Starting CV processing: {cv_path}")
            text = await self.extract_text_from_pdf(cv_path)
            if not text:
                await self.logs_manager.warning(f"No text content extracted from CV: {cv_path}")
                return {}
            
            await self.logs_manager.debug(f"Building structured data for CV: {cv_path}")    
            # For MVP, just return the raw text
            result = {
                'raw_text': text,
                'filename': Path(cv_path).name,
                # Future: Add more structured fields
                # 'skills': extract_skills(text),
                # 'experience': extract_experience(text),
                # 'education': extract_education(text),
            }
            
            await self.logs_manager.info(f"Successfully processed CV: {cv_path}")
            await self.logs_manager.debug(f"CV data size: {len(text)} characters")
            return result
            
        except Exception as e:
            await self.logs_manager.error(f"Error processing CV {cv_path}: {str(e)}")
            return {}

    async def prepare_cv_for_upload(self, cv_path: str | Path) -> tuple[Path, dict]:
        """
        Prepare CV for both parsing and form upload.
        Returns tuple of (verified_path, parsed_data).
        """
        cv_path = Path(cv_path)
        await self.logs_manager.info(f"Preparing CV for upload: {cv_path}")
        
        if not cv_path.exists():
            await self.logs_manager.error(f"CV file not found: {cv_path}")
            raise FileNotFoundError(f"CV not found: {cv_path}")
            
        await self.logs_manager.debug(f"CV file size: {cv_path.stat().st_size} bytes")
            
        # Parse if not already cached
        if cv_path not in self.parsed_cvs:
            await self.logs_manager.debug(f"CV not in cache, parsing: {cv_path}")
            parsed_data = await self.process_cv(cv_path)
            if parsed_data:
                self.parsed_cvs[cv_path] = parsed_data
                await self.logs_manager.debug(f"Successfully cached parsed CV: {cv_path}")
                await self.logs_manager.debug(f"Cache size: {len(self.parsed_cvs)} CVs")
            else:
                await self.logs_manager.error(f"Failed to parse CV: {cv_path}")
                raise ValueError(f"Failed to parse CV: {cv_path}")
        else:
            await self.logs_manager.debug(f"Using cached CV data for: {cv_path}")
                
        return cv_path, self.parsed_cvs[cv_path]

    async def get_parsed_cv(self, cv_path: str | Path) -> Optional[dict]:
        """Get cached parsed CV data if available."""
        path = Path(cv_path)
        result = self.parsed_cvs.get(path)
        if result:
            await self.logs_manager.debug(f"Retrieved cached CV data for: {path}")
            await self.logs_manager.debug(f"Cached data size: {len(result.get('raw_text', ''))} characters")
        else:
            await self.logs_manager.debug(f"No cached CV data found for: {path}")
        return result

    # Future methods:
    # def extract_skills(self, text: str) -> list[str]: ...
    # def extract_experience(self, text: str) -> list[dict]: ...
    # def extract_education(self, text: str) -> list[dict]: ... 