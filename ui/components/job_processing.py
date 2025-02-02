"""
Job Processing View Component
Handles the display and management of real-time job processing information.

This component provides a real-time view of job processing status, including:
- Current job being processed
- Job queue visualization
- Match score display with dynamic updates

Thread Safety Note:
    All UI updates should be performed on the main thread. Use the provided
    schedule_ui_update method for updates from async contexts or other threads.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from threading import Lock

@dataclass
class JobCard:
    """Data structure for job information."""
    job_id: str
    title: str
    company: str
    match_score: float
    status: str
    timestamp: datetime
    details: Dict[str, Any]  # Using Any from typing for better type safety

class JobProcessingView(ttk.Frame):
    """A component for displaying real-time job processing information."""
    
    def __init__(self, parent, *args, **kwargs):
        """Initialize the JobProcessingView.
        
        Args:
            parent: The parent widget
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
        """
        super().__init__(parent, *args, **kwargs)
        self.job_queue: List[JobCard] = []
        self.current_job: Optional[JobCard] = None
        self._update_lock = Lock()  # For thread-safe updates
        self._setup_ui()
        self._setup_bindings()

    def _setup_ui(self):
        """Initialize the UI components with improved layout and styling."""
        # Current Job Section
        self.current_job_frame = ttk.LabelFrame(self, text="Current Job")
        self.current_job_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.current_job_info = ttk.Label(
            self.current_job_frame,
            text="No job being processed",
            wraplength=300  # Prevent text from extending too far
        )
        self.current_job_info.pack(padx=5, pady=5)
        
        # Job Queue Section with improved scrolling
        self.queue_frame = ttk.LabelFrame(self, text="Job Queue")
        self.queue_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Queue List with scrollbar in a container frame
        queue_container = ttk.Frame(self.queue_frame)
        queue_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.queue_scroll = ttk.Scrollbar(queue_container)
        self.queue_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.queue_list = tk.Listbox(
            queue_container,
            yscrollcommand=self.queue_scroll.set,
            height=10,
            selectmode=tk.SINGLE,
            activestyle='dotbox'
        )
        self.queue_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.queue_scroll.config(command=self.queue_list.yview)
        
        # Match Score Section with dynamic updates
        self.score_frame = ttk.LabelFrame(self, text="Match Score")
        self.score_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.score_canvas = tk.Canvas(
            self.score_frame,
            height=50,
            bg=self.score_frame.cget('background')  # Match parent background
        )
        self.score_canvas.pack(fill=tk.X, padx=5, pady=5)

    def _setup_bindings(self):
        """Set up event bindings for dynamic updates."""
        # Bind canvas resize event
        self.score_canvas.bind("<Configure>", self._on_canvas_resize)
        
        # Bind queue selection event
        self.queue_list.bind('<<ListboxSelect>>', self._on_queue_selection)

    def schedule_ui_update(self, update_func: Callable):
        """Schedule a UI update to run on the main thread.
        
        Args:
            update_func: The function to run on the main thread
        """
        self.after_idle(update_func)

    def update_current_job(self, job: JobCard):
        """Update the currently processing job.
        
        Args:
            job: The JobCard instance to display
        """
        try:
            with self._update_lock:
                self.current_job = job
                self.schedule_ui_update(lambda: self._update_current_job_display(job))
        except Exception as e:
            logging.error(f"Error updating current job: {e}")

    def _update_current_job_display(self, job: JobCard):
        """Update the current job display (internal).
        
        Args:
            job: The JobCard instance to display
        """
        self.current_job_info.config(
            text=f"Processing: {job.title} at {job.company}\n"
                f"Match Score: {job.match_score:.2f}\n"
                f"Status: {job.status}"
        )
        self._update_score_display(job.match_score)

    def add_to_queue(self, job: JobCard):
        """Add a job to the processing queue.
        
        Args:
            job: The JobCard instance to add
        """
        try:
            with self._update_lock:
                self.job_queue.append(job)
                self.schedule_ui_update(self._update_queue_display)
        except Exception as e:
            logging.error(f"Error adding job to queue: {e}")

    def remove_from_queue(self, job_id: str):
        """Remove a job from the queue.
        
        Args:
            job_id: The ID of the job to remove
        """
        try:
            with self._update_lock:
                self.job_queue = [j for j in self.job_queue if j.job_id != job_id]
                self.schedule_ui_update(self._update_queue_display)
        except Exception as e:
            logging.error(f"Error removing job from queue: {e}")

    def _update_queue_display(self):
        """Update the queue listbox display."""
        self.queue_list.delete(0, tk.END)
        for job in self.job_queue:
            self.queue_list.insert(
                tk.END, 
                f"{job.title} - {job.company} (Score: {job.match_score:.2f})"
            )

    def _update_score_display(self, score: float):
        """Update the match score visualization.
        
        Args:
            score: The score value between 0 and 1
        """
        # Validate and clamp score
        score = max(0.0, min(1.0, score))
        
        self.score_canvas.delete("all")
        width = self.score_canvas.winfo_width()
        height = self.score_canvas.winfo_height()
        
        if width <= 1 or height <= 1:  # Skip if canvas not properly sized
            return
        
        # Draw background
        self.score_canvas.create_rectangle(
            0, 0, width, height,
            fill=self.score_frame.cget('background'),
            width=0
        )
        
        # Draw score bar
        bar_width = width * score
        bar_color = (
            "green" if score >= 0.7 else
            "yellow" if score >= 0.4 else
            "red"
        )
        
        self.score_canvas.create_rectangle(
            2, height/4,  # Add small margin
            bar_width - 2, height*3/4,
            fill=bar_color,
            width=1,
            outline="gray"
        )
        
        # Draw score text
        self.score_canvas.create_text(
            width/2, height/2,
            text=f"Match Score: {score:.1%}",
            anchor="center",
            fill="black"
        )

    def _on_canvas_resize(self, event):
        """Handle canvas resize events."""
        if self.current_job:
            self._update_score_display(self.current_job.match_score)

    def _on_queue_selection(self, event):
        """Handle queue selection events."""
        selection = self.queue_list.curselection()
        if selection and self.job_queue:
            index = selection[0]
            if 0 <= index < len(self.job_queue):
                job = self.job_queue[index]
                # Emit selection event or update display as needed
                self.event_generate("<<JobSelected>>")

    def clear(self):
        """Clear all job data and reset the display."""
        try:
            with self._update_lock:
                self.job_queue.clear()
                self.current_job = None
                self.schedule_ui_update(self._clear_display)
        except Exception as e:
            logging.error(f"Error clearing job processing view: {e}")

    def _clear_display(self):
        """Clear all display elements (internal)."""
        self.current_job_info.config(text="No job being processed")
        self.queue_list.delete(0, tk.END)
        self._update_score_display(0.0)

    def get_selected_job(self) -> Optional[JobCard]:
        """Get the currently selected job from the queue.
        
        Returns:
            The selected JobCard or None if nothing is selected
        """
        selection = self.queue_list.curselection()
        if selection and self.job_queue:
            index = selection[0]
            if 0 <= index < len(self.job_queue):
                return self.job_queue[index]
        return None 