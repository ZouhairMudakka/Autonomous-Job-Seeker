"""
Profile Manager Component

This component provides a comprehensive interface for managing job application profiles,
including version control, document management, and skill tracking.

Features:
- Profile version management with creation and deletion
- Document handling for resumes and cover letters
- Dynamic skill matrix management
- File format validation and size checks
- Thread-safe updates for asynchronous operations
- Responsive layout with automatic widget management

Usage Example:
    root = tk.Tk()
    version = ProfileVersion(
        version_id="v1.0",
        timestamp=datetime.now(),
        resume_path=Path("path/to/resume.pdf"),
        cover_letter_path=Path("path/to/cover.pdf"),
        skills=["Python", "SQL", "Machine Learning"],
        metadata={
            "target_role": "Data Scientist",
            "experience_level": "Senior"
        }
    )
    manager = ProfileManagerView(root)
    manager.pack(fill=tk.BOTH, expand=True)
    manager.add_version(version)

Thread Safety Note:
    All UI updates should be performed on the main thread. Use the provided
    schedule_ui_update method for updates from async contexts or other threads.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import logging
from threading import Lock
import os

# Maximum file size for documents (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Supported file formats
SUPPORTED_FORMATS = {
    'resume': ['.pdf', '.doc', '.docx'],
    'cover_letter': ['.pdf', '.doc', '.docx', '.txt']
}

@dataclass
class ProfileVersion:
    """Data structure for profile version information.
    
    Attributes:
        version_id: Unique identifier for the version
        timestamp: When the version was created/modified
        resume_path: Path to the resume document
        cover_letter_path: Optional path to cover letter
        skills: List of skills associated with this version
        metadata: Additional version-specific information
    """
    version_id: str
    timestamp: datetime
    resume_path: Path
    cover_letter_path: Optional[Path]
    skills: List[str]
    metadata: Dict[str, Any]

class ProfileManagerView(ttk.Frame):
    """A component for managing job application profiles and versions."""
    
    def __init__(self, parent, *args, **kwargs):
        """Initialize the ProfileManagerView.
        
        Args:
            parent: The parent widget
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
        """
        super().__init__(parent, *args, **kwargs)
        self._versions: Dict[str, ProfileVersion] = {}
        self._version_order: List[str] = []  # Maintain version order
        self._update_lock = Lock()  # For thread-safe updates
        self._setup_ui()
        self._setup_bindings()

    def _setup_ui(self):
        """Initialize the UI components with improved layout and styling."""
        # Version Management Section
        version_frame = ttk.LabelFrame(self, text="Profile Versions")
        version_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Version List with scrollbar
        list_container = ttk.Frame(version_frame)
        list_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.version_scroll = ttk.Scrollbar(list_container)
        self.version_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.version_list = tk.Listbox(
            list_container,
            yscrollcommand=self.version_scroll.set,
            selectmode=tk.SINGLE,
            height=6
        )
        self.version_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.version_scroll.config(command=self.version_list.yview)
        
        # Version Control Buttons
        button_frame = ttk.Frame(version_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            button_frame,
            text="New Version",
            command=self._create_new_version
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            button_frame,
            text="Delete Version",
            command=self._delete_version
        ).pack(side=tk.LEFT, padx=2)
        
        # Document Management Section
        doc_frame = ttk.LabelFrame(self, text="Documents")
        doc_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Resume Selection
        resume_frame = ttk.Frame(doc_frame)
        resume_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(resume_frame, text="Resume:").pack(side=tk.LEFT)
        self.resume_path_var = tk.StringVar()
        ttk.Entry(
            resume_frame,
            textvariable=self.resume_path_var,
            state="readonly"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        ttk.Button(
            resume_frame,
            text="Browse",
            command=lambda: self._select_file('resume')
        ).pack(side=tk.RIGHT)
        
        # Cover Letter Selection
        cover_frame = ttk.Frame(doc_frame)
        cover_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(cover_frame, text="Cover Letter:").pack(side=tk.LEFT)
        self.cover_path_var = tk.StringVar()
        ttk.Entry(
            cover_frame,
            textvariable=self.cover_path_var,
            state="readonly"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        ttk.Button(
            cover_frame,
            text="Browse",
            command=lambda: self._select_file('cover_letter')
        ).pack(side=tk.RIGHT)
        
        # Skills Management Section
        skills_frame = ttk.LabelFrame(self, text="Skills Matrix")
        skills_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Skills List with scrollbar
        skills_container = ttk.Frame(skills_frame)
        skills_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.skills_scroll = ttk.Scrollbar(skills_container)
        self.skills_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.skills_list = tk.Listbox(
            skills_container,
            yscrollcommand=self.skills_scroll.set,
            selectmode=tk.MULTIPLE,
            height=6
        )
        self.skills_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.skills_scroll.config(command=self.skills_list.yview)
        
        # Skills Control
        skills_control = ttk.Frame(skills_frame)
        skills_control.pack(fill=tk.X, padx=5, pady=5)
        
        self.skill_entry = ttk.Entry(skills_control)
        self.skill_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        ttk.Button(
            skills_control,
            text="Add Skill",
            command=self._add_skill
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            skills_control,
            text="Remove Selected",
            command=self._remove_selected_skills
        ).pack(side=tk.LEFT, padx=2)
        
        # Status Bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(
            self,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_bar.pack(fill=tk.X, padx=5, pady=2)

    def _setup_bindings(self):
        """Set up event bindings for dynamic updates."""
        self.version_list.bind('<<ListboxSelect>>', self._on_version_selected)
        self.skill_entry.bind('<Return>', lambda e: self._add_skill())

    def schedule_ui_update(self, update_func: Callable):
        """Schedule a UI update to run on the main thread.
        
        Args:
            update_func: The function to run on the main thread
        """
        self.after_idle(update_func)

    def _validate_file(self, file_path: str, file_type: str) -> bool:
        """Validate file format and size.
        
        Args:
            file_path: Path to the file to validate
            file_type: Type of file ('resume' or 'cover_letter')
            
        Returns:
            bool: Whether the file is valid
        """
        if not os.path.exists(file_path):
            self._show_status(f"Error: File does not exist: {file_path}")
            return False
        
        # Check file size
        if os.path.getsize(file_path) > MAX_FILE_SIZE:
            self._show_status(f"Error: File size exceeds {MAX_FILE_SIZE/1024/1024:.1f}MB limit")
            return False
        
        # Check file format
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_FORMATS[file_type]:
            self._show_status(
                f"Error: Unsupported file format. Supported formats: "
                f"{', '.join(SUPPORTED_FORMATS[file_type])}"
            )
            return False
        
        return True

    def _select_file(self, file_type: str):
        """Handle file selection for resume or cover letter.
        
        Args:
            file_type: Type of file to select ('resume' or 'cover_letter')
        """
        formats = SUPPORTED_FORMATS[file_type]
        filetypes = [(f.upper(), f"*{f}") for f in formats]
        filetypes.append(("All Files", "*.*"))
        
        file_path = filedialog.askopenfilename(
            title=f"Select {file_type.replace('_', ' ').title()}",
            filetypes=filetypes
        )
        
        if file_path and self._validate_file(file_path, file_type):
            if file_type == 'resume':
                self.resume_path_var.set(file_path)
            else:
                self.cover_path_var.set(file_path)
            self._update_current_version()

    def _create_new_version(self):
        """Create a new profile version."""
        try:
            with self._update_lock:
                # Generate version ID
                version_id = f"v{len(self._versions) + 1}"
                
                # Create new version
                version = ProfileVersion(
                    version_id=version_id,
                    timestamp=datetime.now(),
                    resume_path=Path(self.resume_path_var.get()) if self.resume_path_var.get() else None,
                    cover_letter_path=Path(self.cover_path_var.get()) if self.cover_path_var.get() else None,
                    skills=[],
                    metadata={}
                )
                
                self._versions[version_id] = version
                self._version_order.append(version_id)
                self.schedule_ui_update(self._update_version_list)
                self._show_status(f"Created new version: {version_id}")
        except Exception as e:
            logging.error(f"Error creating new version: {e}")
            self._show_status("Error creating new version")

    def _delete_version(self):
        """Delete the selected profile version."""
        selection = self.version_list.curselection()
        if not selection:
            self._show_status("Please select a version to delete")
            return
        
        version_id = self._version_order[selection[0]]
        
        if messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete version {version_id}?"
        ):
            try:
                with self._update_lock:
                    del self._versions[version_id]
                    self._version_order.remove(version_id)
                    self.schedule_ui_update(self._update_version_list)
                    self._show_status(f"Deleted version: {version_id}")
            except Exception as e:
                logging.error(f"Error deleting version: {e}")
                self._show_status("Error deleting version")

    def _update_version_list(self):
        """Update the version list display."""
        self.version_list.delete(0, tk.END)
        for version_id in self._version_order:
            version = self._versions[version_id]
            self.version_list.insert(
                tk.END,
                f"{version_id} - {version.timestamp.strftime('%Y-%m-%d %H:%M')}"
            )

    def _on_version_selected(self, event):
        """Handle version selection changes."""
        selection = self.version_list.curselection()
        if not selection:
            return
        
        try:
            version_id = self._version_order[selection[0]]
            version = self._versions[version_id]
            
            # Update document paths
            self.resume_path_var.set(str(version.resume_path) if version.resume_path else "")
            self.cover_path_var.set(str(version.cover_letter_path) if version.cover_letter_path else "")
            
            # Update skills list
            self.skills_list.delete(0, tk.END)
            for skill in version.skills:
                self.skills_list.insert(tk.END, skill)
        except Exception as e:
            logging.error(f"Error updating version display: {e}")
            self._show_status("Error displaying version")

    def _add_skill(self):
        """Add a new skill to the current version."""
        skill = self.skill_entry.get().strip()
        if not skill:
            return
        
        selection = self.version_list.curselection()
        if not selection:
            self._show_status("Please select a version first")
            return
        
        try:
            version_id = self._version_order[selection[0]]
            version = self._versions[version_id]
            
            if skill not in version.skills:
                version.skills.append(skill)
                self.skills_list.insert(tk.END, skill)
                self.skill_entry.delete(0, tk.END)
                self._show_status(f"Added skill: {skill}")
        except Exception as e:
            logging.error(f"Error adding skill: {e}")
            self._show_status("Error adding skill")

    def _remove_selected_skills(self):
        """Remove selected skills from the current version."""
        selection = self.version_list.curselection()
        if not selection:
            self._show_status("Please select a version first")
            return
        
        skill_selection = self.skills_list.curselection()
        if not skill_selection:
            self._show_status("Please select skills to remove")
            return
        
        try:
            version_id = self._version_order[selection[0]]
            version = self._versions[version_id]
            
            # Remove skills in reverse order to maintain correct indices
            for index in reversed(skill_selection):
                skill = self.skills_list.get(index)
                version.skills.remove(skill)
                self.skills_list.delete(index)
            
            self._show_status("Removed selected skills")
        except Exception as e:
            logging.error(f"Error removing skills: {e}")
            self._show_status("Error removing skills")

    def _update_current_version(self):
        """Update the current version with any changes."""
        selection = self.version_list.curselection()
        if not selection:
            return
        
        try:
            version_id = self._version_order[selection[0]]
            version = self._versions[version_id]
            
            # Update paths
            resume_path = self.resume_path_var.get()
            cover_path = self.cover_path_var.get()
            
            version.resume_path = Path(resume_path) if resume_path else None
            version.cover_letter_path = Path(cover_path) if cover_path else None
            version.timestamp = datetime.now()
            
            self.schedule_ui_update(self._update_version_list)
            self._show_status("Updated version")
        except Exception as e:
            logging.error(f"Error updating version: {e}")
            self._show_status("Error updating version")

    def _show_status(self, message: str):
        """Update the status bar with a message.
        
        Args:
            message: Status message to display
        """
        self.status_var.set(message)
        # Clear status after 5 seconds
        self.after(5000, lambda: self.status_var.set(""))

    def clear(self):
        """Clear all profile data and reset the display."""
        try:
            with self._update_lock:
                self._versions.clear()
                self._version_order.clear()
                self.schedule_ui_update(self._clear_all_displays)
        except Exception as e:
            logging.error(f"Error clearing profile manager: {e}")
            self._show_status("Error clearing data")

    def _clear_all_displays(self):
        """Clear all display elements (internal)."""
        self.version_list.delete(0, tk.END)
        self.skills_list.delete(0, tk.END)
        self.resume_path_var.set("")
        self.cover_path_var.set("")
        self.skill_entry.delete(0, tk.END)
        self._show_status("Cleared all data") 