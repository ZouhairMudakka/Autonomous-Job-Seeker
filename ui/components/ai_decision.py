"""
AI Decision Visualization Component

This component provides a real-time visualization of AI decision-making processes,
including confidence scores, strategies, reasoning, and fallback triggers.

Features:
- Dynamic confidence score visualization with color-coded feedback
- Real-time strategy and reasoning display
- Fallback trigger monitoring
- Thread-safe updates for asynchronous operations
- Responsive layout with automatic resizing

Usage Example:
    root = tk.Tk()
    decision_view = AIDecisionView(root)
    decision_view.pack(fill=tk.BOTH, expand=True)
    
    # Update with new decision
    decision = AIDecision(
        confidence_score=0.85,
        strategy="semantic_matching",
        reasoning="High keyword match with required skills",
        fallback_triggers=["low_experience_match"],
        timestamp=datetime.now(),
        metadata={"source": "job_matcher_v2"}
    )
    decision_view.update_decision(decision)

Thread Safety Note:
    All UI updates should be performed on the main thread. Use the provided
    schedule_ui_update method for updates from async contexts or other threads.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from threading import Lock

# AI Decision Activity Types and Styling
AI_ACTIVITY_TYPES = {
    "AI_THINKING": {"color": "#9C27B0", "icon": "🤔", "tag": "AI_THINKING"},
    "AI_DECISION": {"color": "#4CAF50", "icon": "✅", "tag": "AI_DECISION"},
    "AI_ANALYSIS": {"color": "#FF9800", "icon": "🔍", "tag": "AI_ANALYSIS"},
    "AI_GENERATION": {"color": "#E91E63", "icon": "✨", "tag": "AI_GENERATION"}
}

# Filter Categories
AI_FILTER_CATEGORIES = {
    "ALL": list(AI_ACTIVITY_TYPES.keys()),
    "AI Core": list(AI_ACTIVITY_TYPES.keys()),
    "Success Only": ["AI_DECISION"],
    "Analysis Only": ["AI_ANALYSIS", "AI_THINKING"],
    "Generation Only": ["AI_GENERATION"]
}

def get_activity_color(activity_type: str) -> str:
    """Get the color associated with an activity type."""
    return AI_ACTIVITY_TYPES.get(activity_type, {}).get("color", "#9E9E9E")

def get_activity_icon(activity_type: str) -> str:
    """Get the icon associated with an activity type."""
    return AI_ACTIVITY_TYPES.get(activity_type, {}).get("icon", "⚙️")

def get_tag_indicators(tag: str) -> List[str]:
    """Get indicators that suggest a line belongs to a particular tag."""
    activity = AI_ACTIVITY_TYPES.get(tag, {})
    return [
        activity.get("icon", ""),
        f"[{tag}]",
        activity.get("color", "")
    ]

@dataclass
class AIDecision:
    """Data structure for AI decision information.
    
    Attributes:
        confidence_score: Float between 0 and 1 indicating decision confidence
        strategy: Current strategy being applied
        reasoning: Detailed explanation of the decision
        fallback_triggers: List of conditions that might trigger fallback strategies
        timestamp: When the decision was made
        metadata: Additional context and decision-related data
    """
    confidence_score: float
    strategy: str
    reasoning: str
    fallback_triggers: List[str]
    timestamp: datetime
    metadata: Dict[str, Any]  # Using Any from typing for better type safety

class AIDecisionView(ttk.Frame):
    """A component for visualizing AI decision-making processes in real-time."""
    
    def __init__(self, parent, *args, **kwargs):
        """Initialize the AIDecisionView.
        
        Args:
            parent: The parent widget
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
        """
        super().__init__(parent, *args, **kwargs)
        self.current_decision: Optional[AIDecision] = None
        self._update_lock = Lock()  # For thread-safe updates
        self._setup_ui()
        self._setup_bindings()

    def _setup_ui(self):
        """Initialize the UI components with improved layout and styling."""
        # Confidence Score Section
        self.confidence_frame = ttk.LabelFrame(self, text="Confidence Score")
        self.confidence_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.confidence_canvas = tk.Canvas(
            self.confidence_frame,
            height=50,
            bg=self.confidence_frame.cget('background')
        )
        self.confidence_canvas.pack(fill=tk.X, padx=5, pady=5)
        
        # Strategy Section
        self.strategy_frame = ttk.LabelFrame(self, text="Current Strategy")
        self.strategy_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.strategy_label = ttk.Label(
            self.strategy_frame,
            text="No active strategy",
            wraplength=300
        )
        self.strategy_label.pack(padx=5, pady=5)
        
        # Reasoning Section
        self.reasoning_frame = ttk.LabelFrame(self, text="Decision Reasoning")
        self.reasoning_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.reasoning_text = scrolledtext.ScrolledText(
            self.reasoning_frame,
            wrap=tk.WORD,
            height=6,
            width=50
        )
        self.reasoning_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Setup text tags for styling
        self._setup_text_tags()
        
        # Fallback Triggers Section
        self.triggers_frame = ttk.LabelFrame(self, text="Fallback Triggers")
        self.triggers_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.triggers_list = tk.Listbox(
            self.triggers_frame,
            height=4,
            selectmode=tk.BROWSE
        )
        self.triggers_list.pack(fill=tk.X, padx=5, pady=5)

    def _setup_bindings(self):
        """Set up event bindings for dynamic updates."""
        self.confidence_canvas.bind("<Configure>", self._on_canvas_resize)
        self.triggers_list.bind('<<ListboxSelect>>', self._on_trigger_selection)

    def schedule_ui_update(self, update_func: Callable):
        """Schedule a UI update to run on the main thread.
        
        Args:
            update_func: The function to run on the main thread
        """
        self.after_idle(update_func)

    def update_decision(self, decision: AIDecision):
        """Update the displayed decision information.
        
        Args:
            decision: The AIDecision instance to display
        """
        try:
            with self._update_lock:
                self.current_decision = decision
                self.schedule_ui_update(lambda: self._update_decision_display(decision))
        except Exception as e:
            logging.error(f"Error updating AI decision: {e}")

    def _update_decision_display(self, decision: AIDecision):
        """Update all UI elements with new decision data (internal).
        
        Args:
            decision: The AIDecision instance to display
        """
        try:
            self._update_confidence_display(decision.confidence_score)
            self.strategy_label.config(
                text=f"Strategy: {decision.strategy}\n"
                     f"Updated: {decision.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.reasoning_text.delete('1.0', tk.END)
            self.reasoning_text.insert('1.0', decision.reasoning)
            self._update_triggers_display(decision.fallback_triggers)
        except Exception as e:
            logging.error(f"Error updating decision display: {e}")

    def _update_confidence_display(self, score: float):
        """Update the confidence score visualization.
        
        Args:
            score: The confidence score value between 0 and 1
        """
        # Validate and clamp score
        score = max(0.0, min(1.0, score))
        
        self.confidence_canvas.delete("all")
        width = self.confidence_canvas.winfo_width()
        height = self.confidence_canvas.winfo_height()
        
        if width <= 1 or height <= 1:  # Skip if canvas not properly sized
            return
        
        # Draw background
        self.confidence_canvas.create_rectangle(
            0, 0, width, height,
            fill=self.confidence_frame.cget('background'),
            width=0
        )
        
        # Draw confidence bar
        bar_width = width * score
        bar_color = (
            "#2ECC71" if score >= 0.7 else  # Green
            "#F1C40F" if score >= 0.4 else  # Yellow
            "#E74C3C"                       # Red
        )
        
        # Draw bar with gradient effect
        self.confidence_canvas.create_rectangle(
            2, height/4,
            bar_width - 2, height*3/4,
            fill=bar_color,
            width=1,
            outline="#95A5A6"  # Subtle gray outline
        )
        
        # Draw confidence text
        self.confidence_canvas.create_text(
            width/2, height/2,
            text=f"Confidence: {score:.1%}",
            anchor="center",
            fill="#2C3E50",  # Dark blue-gray text
            font=('TkDefaultFont', 10, 'bold')
        )

    def _update_triggers_display(self, triggers: List[str]):
        """Update the fallback triggers display.
        
        Args:
            triggers: List of fallback trigger strings
        """
        self.triggers_list.delete(0, tk.END)
        for trigger in triggers:
            self.triggers_list.insert(tk.END, trigger)

    def _on_canvas_resize(self, event):
        """Handle canvas resize events."""
        if self.current_decision:
            self._update_confidence_display(self.current_decision.confidence_score)

    def _on_trigger_selection(self, event):
        """Handle trigger selection events."""
        selection = self.triggers_list.curselection()
        if selection and self.current_decision:
            index = selection[0]
            trigger = self.triggers_list.get(index)
            # Emit selection event for external handling
            self.event_generate("<<TriggerSelected>>")

    def clear(self):
        """Clear all decision data and reset the display."""
        try:
            with self._update_lock:
                self.current_decision = None
                self.schedule_ui_update(self._clear_display)
        except Exception as e:
            logging.error(f"Error clearing AI decision view: {e}")

    def _clear_display(self):
        """Clear all display elements (internal)."""
        self.strategy_label.config(text="No active strategy")
        self.reasoning_text.delete('1.0', tk.END)
        self.triggers_list.delete(0, tk.END)
        self._update_confidence_display(0.0)

    def get_selected_trigger(self) -> Optional[str]:
        """Get the currently selected fallback trigger.
        
        Returns:
            The selected trigger string or None if nothing is selected
        """
        selection = self.triggers_list.curselection()
        if selection:
            return self.triggers_list.get(selection[0])
        return None

    def apply_activity_filter(self, filter_type: str = "ALL", search_term: str = "") -> None:
        """Filter the displayed AI decisions based on type and search term.
        
        Args:
            filter_type: The type of AI activities to show (from AI_FILTER_CATEGORIES)
            search_term: Optional search term to further filter the content
        """
        try:
            if not hasattr(self, '_activity_content'):
                return

            # Get active tags for the filter type
            active_tags = AI_FILTER_CATEGORIES.get(filter_type, AI_FILTER_CATEGORIES["ALL"])
            
            # Clear current display
            self.reasoning_text.config(state=tk.NORMAL)
            self.reasoning_text.delete(1.0, tk.END)
            
            # Filter and display content
            lines = self._activity_content.splitlines()
            for line in lines:
                if not line.strip():
                    continue
                    
                # Check search term
                if search_term and search_term.lower() not in line.lower():
                    continue
                    
                # Check if line matches selected type
                if filter_type != "ALL":
                    matches_type = False
                    for tag in active_tags:
                        if any(indicator in line for indicator in get_tag_indicators(tag)):
                            matches_type = True
                            break
                    if not matches_type:
                        continue
                        
                self._insert_line_with_tags(line)
                
        except Exception as e:
            logging.error(f"Error applying AI decision filter: {str(e)}")

    def _insert_line_with_tags(self, line: str) -> None:
        """Insert a line with appropriate styling based on AI activity type.
        
        Args:
            line: The line of text to insert
        """
        try:
            # First insert timestamp if present
            if line.startswith("["):
                timestamp_end = line.find("]") + 1
                if timestamp_end > 0:
                    self.reasoning_text.insert(tk.END, line[:timestamp_end], "timestamp")
                    line = line[timestamp_end:]
            
            # Check content against all AI activity types
            for activity_type, activity_info in AI_ACTIVITY_TYPES.items():
                indicators = get_tag_indicators(activity_type)
                for indicator in indicators:
                    if indicator in line:
                        self.reasoning_text.insert(tk.END, line + "\n", activity_type)
                        return
            
            # If no specific tag found, insert without tag
            self.reasoning_text.insert(tk.END, line + "\n")
            
        except Exception as e:
            logging.error(f"Error inserting line with tags: {str(e)}")

    def _setup_text_tags(self) -> None:
        """Configure text tags for different AI activity types."""
        # Add timestamp tag
        self.reasoning_text.tag_configure("timestamp", foreground="#666666")
        
        # Add tags for each AI activity type
        for activity_type, info in AI_ACTIVITY_TYPES.items():
            self.reasoning_text.tag_configure(
                activity_type,
                foreground=info["color"],
                font=('TkDefaultFont', 10, 'bold')
            )

    def store_activity_content(self, content: str) -> None:
        """Store activity content for filtering.
        
        Args:
            content: The full activity content to store
        """
        self._activity_content = content 