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

class DocumentProcessor:
    def __init__(self, settings: dict):
        """
        Initialize with application settings.
        
        Args:
            settings (dict): Application settings containing paths and configurations
        """
        self.settings = settings
        self.data_dir = Path(settings.get('data_dir', './data'))
        self.parsed_cvs = {}  # Cache for parsed CVs

    def extract_text_from_pdf(self, pdf_path: str | Path) -> Optional[str]:
        """
        Extract text content from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            str: Extracted text or None if extraction failed
        """
        try:
            text = ""
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text() or ""
            return text.strip() if text else None
            
        except Exception as e:
            print(f"[DocumentProcessor] Error extracting text from PDF: {e}")
            return None

    def process_cv(self, cv_path: str | Path) -> dict:
        """
        Process a CV/resume and extract structured information.
        
        Args:
            cv_path: Path to the CV file (PDF)
            
        Returns:
            dict: Structured CV data or empty dict if processing failed
        """
        try:
            text = self.extract_text_from_pdf(cv_path)
            if not text:
                return {}
                
            # For MVP, just return the raw text
            return {
                'raw_text': text,
                'filename': Path(cv_path).name,
                # Future: Add more structured fields
                # 'skills': extract_skills(text),
                # 'experience': extract_experience(text),
                # 'education': extract_education(text),
            }
            
        except Exception as e:
            print(f"[DocumentProcessor] Error processing CV: {e}")
            return {}

    async def prepare_cv_for_upload(self, cv_path: str | Path) -> tuple[Path, dict]:
        """
        Prepare CV for both parsing and form upload.
        Returns tuple of (verified_path, parsed_data).
        """
        cv_path = Path(cv_path)
        if not cv_path.exists():
            raise FileNotFoundError(f"CV not found: {cv_path}")
            
        # Parse if not already cached
        if cv_path not in self.parsed_cvs:
            parsed_data = self.process_cv(cv_path)
            if parsed_data:
                self.parsed_cvs[cv_path] = parsed_data
            else:
                raise ValueError(f"Failed to parse CV: {cv_path}")
                
        return cv_path, self.parsed_cvs[cv_path]

    def get_parsed_cv(self, cv_path: str | Path) -> Optional[dict]:
        """Get cached parsed CV data if available."""
        return self.parsed_cvs.get(Path(cv_path))

    # Future methods:
    # def extract_skills(self, text: str) -> list[str]: ...
    # def extract_experience(self, text: str) -> list[dict]: ...
    # def extract_education(self, text: str) -> list[dict]: ... 