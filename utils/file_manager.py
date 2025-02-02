"""
File Manager Implementation
Handles file operations, particularly CV file handling and validation.
"""

import PyPDF2
from pathlib import Path
from typing import Optional, Dict, Any
import tkinter as tk
from tkinter import filedialog

class CVFileManager:
    def __init__(self, logs_manager, settings_manager):
        """Initialize the CVFileManager."""
        self.logs_manager = logs_manager
        self.settings_manager = settings_manager
        self.current_cv_path: Optional[Path] = None

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
            self.logs_manager.error(f"Error selecting CV file: {str(e)}")
            return None

    def validate_cv_file(self, file_path: Path) -> bool:
        """Validate the selected CV file."""
        try:
            # Check if file exists
            if not file_path.exists():
                self.logs_manager.error("Selected file does not exist")
                return False
                
            # Check file size (5MB limit)
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if file_path.stat().st_size > max_size:
                self.logs_manager.error("File too large. Maximum size is 5MB")
                return False
                
            # Check file format
            valid_formats = {'.pdf', '.docx', '.txt'}
            if file_path.suffix.lower() not in valid_formats:
                self.logs_manager.error(
                    f"Unsupported file format. Please use: {', '.join(valid_formats)}"
                )
                return False
                
            # Check if file is empty
            if file_path.stat().st_size == 0:
                self.logs_manager.error("File is empty")
                return False
                
            # Check if file is readable
            try:
                file_path.open('rb').close()
            except Exception:
                self.logs_manager.error("File is not readable")
                return False
                
            # For PDF files, check if it's a valid PDF
            if file_path.suffix.lower() == '.pdf':
                try:
                    with open(file_path, 'rb') as f:
                        PyPDF2.PdfReader(f)
                except Exception:
                    self.logs_manager.error("Invalid PDF file")
                    return False
                    
            return True
            
        except Exception as e:
            self.logs_manager.error(f"Error validating CV file: {str(e)}")
            return False

    def get_cv_preview(self, file_path: Path, max_chars: int = 1000) -> str:
        """Get a preview of the CV content."""
        try:
            preview_text = ""
            if file_path.suffix.lower() == '.pdf':
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    preview_text = reader.pages[0].extract_text()[:max_chars]
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    preview_text = f.read(max_chars)
            
            if len(preview_text) == max_chars:
                preview_text += "...\n(Preview truncated)"
                
            return preview_text
            
        except Exception as e:
            self.logs_manager.error(f"Error generating CV preview: {str(e)}")
            return "Error loading preview"

    def remove_cv_file(self):
        """Remove the current CV file from settings."""
        try:
            self.settings_manager.set_setting('cv_file_path', None)
            self.current_cv_path = None
            self.logs_manager.info("CV file removed from settings")
        except Exception as e:
            self.logs_manager.error(f"Error removing CV file: {str(e)}")

    @property
    def has_cv_file(self) -> bool:
        """Check if a CV file is currently loaded."""
        return self.current_cv_path is not None 