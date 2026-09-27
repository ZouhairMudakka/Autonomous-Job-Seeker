"""
File Manager Implementation
Handles file operations, particularly CV file handling and validation.
"""

import pypdf as PyPDF2
import asyncio
import inspect
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import tkinter as tk
from tkinter import filedialog

class CVFileManager:
    def __init__(self, logs_manager, settings_manager):
        """Initialize the CVFileManager."""
        self.logs_manager = logs_manager
        self.settings_manager = settings_manager
        saved_path = self.settings_manager.get_setting('cv_file_path')
        self.current_cv_path: Optional[Path] = Path(saved_path) if saved_path and Path(saved_path).is_file() else None

    def _log(self, level, message):
        """Handle the async application logger from synchronous GUI callbacks."""
        method = getattr(self.logs_manager, level)
        if inspect.iscoroutinefunction(method):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                getattr(logging.getLogger(__name__), level)(message)
            else:
                loop.create_task(method(message))
        else:
            method(message)

    def select_cv_file(self) -> Optional[Path]:
        """Handle CV file selection with file dialog."""
        try:
            file_path = filedialog.askopenfilename(
                title="Select your CV/Resume",
                filetypes=[
                    ("PDF files", "*.pdf"),
                    ("Word documents", "*.docx"),
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ]
            )

            if not file_path:
                return None

            cv_path = Path(file_path)
            if not self.validate_cv_file(cv_path):
                return None

            self.current_cv_path = cv_path
            self.settings_manager.set_setting('cv_file_path', str(cv_path))
            return cv_path

        except Exception as e:
            self._log("error", f"Error selecting CV file: {str(e)}")
            return None

    def validate_cv_file(self, file_path: Path) -> bool:
        """Validate the selected CV file."""
        try:
            # Check if file exists
            if not file_path.is_file():
                self._log("error", "Selected file does not exist")
                return False

            # Check file size (5MB limit)
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if file_path.stat().st_size > max_size:
                self._log("error", "File too large. Maximum size is 5MB")
                return False

            # Check file format
            valid_formats = {'.pdf', '.docx', '.txt'}
            if file_path.suffix.lower() not in valid_formats:
                self._log("error",
                    f"Unsupported file format. Please use: {', '.join(valid_formats)}"
                )
                return False

            # Check if file is empty
            if file_path.stat().st_size == 0:
                self._log("error", "File is empty")
                return False

            # Check if file is readable
            try:
                file_path.open('rb').close()
            except Exception:
                self._log("error", "File is not readable")
                return False

            # For PDF files, check if it's a valid PDF
            if file_path.suffix.lower() == '.pdf':
                try:
                    with open(file_path, 'rb') as f:
                        PyPDF2.PdfReader(f)
                except Exception:
                    self._log("error", "Invalid PDF file")
                    return False

            return True

        except Exception as e:
            self._log("error", f"Error validating CV file: {str(e)}")
            return False

    def get_cv_preview(self, file_path: Path, max_chars: int = 1000) -> str:
        """Get a preview of the CV content."""
        try:
            if max_chars < 1:
                raise ValueError('max_chars must be positive')
            preview_text = ""
            if file_path.suffix.lower() == '.pdf':
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    preview_text = (reader.pages[0].extract_text() or '')[:max_chars] if reader.pages else ''
            elif file_path.suffix.lower() == '.docx':
                from docx import Document
                document = Document(file_path)
                preview_text = '\n'.join(paragraph.text for paragraph in document.paragraphs)[:max_chars]
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    preview_text = f.read(max_chars)

            if len(preview_text) == max_chars:
                preview_text += "...\n(Preview truncated)"

            return preview_text

        except Exception as e:
            self._log("error", f"Error generating CV preview: {str(e)}")
            return "Error loading preview"

    def remove_cv_file(self):
        """Remove the current CV file from settings."""
        try:
            self.settings_manager.set_setting('cv_file_path', None)
            self.current_cv_path = None
            self._log("info", "CV file removed from settings")
        except Exception as e:
            self._log("error", f"Error removing CV file: {str(e)}")

    @property
    def has_cv_file(self) -> bool:
        """Check if a CV file is currently loaded."""
        return self.current_cv_path is not None and self.current_cv_path.is_file()
