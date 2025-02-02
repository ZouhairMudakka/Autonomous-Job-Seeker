"""
Analytics Dashboard Component

This component provides a comprehensive visualization of job market analytics,
including trends, skills analysis, salary distributions, and geographic insights.

Features:
- Real-time metrics visualization with automatic updates
- Interactive charts using Matplotlib integration
- Multi-tab interface for different analytics views
- Customizable filters for skills and geographic analysis
- Responsive layout with dynamic resizing
- Thread-safe updates for asynchronous data processing

Usage Example:
    root = tk.Tk()
    metrics = JobMarketMetrics(
        total_jobs=150,
        total_applications=75,
        success_rate=0.45,
        avg_response_time=24.5,
        skills_demand={'Python': 85, 'SQL': 65},
        salary_ranges={'Junior': [50000, 75000], 'Senior': [90000, 120000]},
        geographic_distribution={'New York': 45, 'SF': 35},
        timestamp=datetime.now()
    )
    dashboard = AnalyticsDashboard(root)
    dashboard.pack(fill=tk.BOTH, expand=True)
    dashboard.update_metrics(metrics)

Thread Safety Note:
    All UI updates should be performed on the main thread. Use the provided
    schedule_ui_update method for updates from async contexts or other threads.
"""

import tkinter as tk
from tkinter import ttk, Entry, StringVar
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from threading import Lock
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

@dataclass
class JobMarketMetrics:
    """Data structure for job market analytics information.
    
    Attributes:
        total_jobs: Total number of jobs processed
        total_applications: Total number of applications submitted
        success_rate: Application success rate (0-1)
        avg_response_time: Average employer response time in hours
        skills_demand: Dictionary mapping skills to their demand score
        salary_ranges: Dictionary mapping job levels to salary ranges
        geographic_distribution: Dictionary mapping locations to job counts
        timestamp: When the metrics were collected
    """
    total_jobs: int
    total_applications: int
    success_rate: float
    avg_response_time: float
    skills_demand: Dict[str, float]
    salary_ranges: Dict[str, List[float]]
    geographic_distribution: Dict[str, int]
    timestamp: datetime

class AnalyticsDashboard(ttk.Frame):
    """A component for visualizing job market analytics in real-time."""
    
    def __init__(self, parent, *args, **kwargs):
        """Initialize the AnalyticsDashboard.
        
        Args:
            parent: The parent widget
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
        """
        super().__init__(parent, *args, **kwargs)
        self.metrics_history: List[JobMarketMetrics] = []
        self._update_lock = Lock()  # For thread-safe updates
        self._setup_ui()
        self._setup_bindings()
        self._setup_auto_refresh()

    def _setup_ui(self):
        """Initialize the UI components with improved layout and styling."""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Overview Tab
        self.overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_frame, text="Overview")
        self._setup_overview_tab()
        
        # Skills Analysis Tab
        self.skills_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.skills_frame, text="Skills Analysis")
        self._setup_skills_tab()
        
        # Salary Analysis Tab
        self.salary_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.salary_frame, text="Salary Analysis")
        self._setup_salary_tab()
        
        # Geographic Analysis Tab
        self.geo_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.geo_frame, text="Geographic Analysis")
        self._setup_geo_tab()

    def _setup_overview_tab(self):
        """Set up the overview tab with key metrics and trend chart."""
        # Key Metrics Section
        metrics_frame = ttk.LabelFrame(self.overview_frame, text="Key Metrics")
        metrics_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.total_jobs_label = ttk.Label(metrics_frame, text="Total Jobs: 0")
        self.total_jobs_label.pack(padx=5, pady=2)
        
        self.applications_label = ttk.Label(metrics_frame, text="Applications: 0")
        self.applications_label.pack(padx=5, pady=2)
        
        self.success_rate_label = ttk.Label(metrics_frame, text="Success Rate: 0%")
        self.success_rate_label.pack(padx=5, pady=2)
        
        self.response_time_label = ttk.Label(metrics_frame, text="Avg Response: 0h")
        self.response_time_label.pack(padx=5, pady=2)
        
        # Trend Chart
        trend_frame = ttk.LabelFrame(self.overview_frame, text="Trends")
        trend_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.trend_figure = Figure(figsize=(6, 4), dpi=100)
        self.trend_canvas = FigureCanvasTkAgg(self.trend_figure, trend_frame)
        self.trend_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _setup_skills_tab(self):
        """Set up the skills analysis tab with filter and chart."""
        # Filter Section
        filter_frame = ttk.Frame(self.skills_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(filter_frame, text="Filter Skills:").pack(side=tk.LEFT, padx=5)
        self.skills_filter = StringVar()
        self.skills_entry = ttk.Entry(
            filter_frame,
            textvariable=self.skills_filter
        )
        self.skills_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Skills Chart
        self.skills_figure = Figure(figsize=(6, 4), dpi=100)
        self.skills_canvas = FigureCanvasTkAgg(self.skills_figure, self.skills_frame)
        self.skills_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _setup_salary_tab(self):
        """Set up the salary analysis tab with distribution chart."""
        self.salary_figure = Figure(figsize=(6, 4), dpi=100)
        self.salary_canvas = FigureCanvasTkAgg(self.salary_figure, self.salary_frame)
        self.salary_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _setup_geo_tab(self):
        """Set up the geographic analysis tab with region selector and chart."""
        # Region Selector
        selector_frame = ttk.Frame(self.geo_frame)
        selector_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(selector_frame, text="Region:").pack(side=tk.LEFT, padx=5)
        self.region_var = StringVar()
        self.region_combo = ttk.Combobox(
            selector_frame,
            textvariable=self.region_var,
            state="readonly"
        )
        self.region_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Geographic Chart
        self.geo_figure = Figure(figsize=(6, 4), dpi=100)
        self.geo_canvas = FigureCanvasTkAgg(self.geo_figure, self.geo_frame)
        self.geo_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _setup_bindings(self):
        """Set up event bindings for dynamic updates."""
        # Bind canvas resize events
        self.trend_canvas.get_tk_widget().bind("<Configure>", lambda e: self._update_overview())
        self.skills_canvas.get_tk_widget().bind("<Configure>", lambda e: self._update_skills_chart())
        self.salary_canvas.get_tk_widget().bind("<Configure>", lambda e: self._update_salary_chart())
        self.geo_canvas.get_tk_widget().bind("<Configure>", lambda e: self._update_geo_chart())
        
        # Bind filter and selection changes
        self.skills_filter.trace_add("write", lambda *args: self._update_skills_chart())
        self.region_var.trace_add("write", lambda *args: self._update_geo_chart())

    def _setup_auto_refresh(self):
        """Set up automatic refresh of charts."""
        self._auto_refresh()

    def _auto_refresh(self):
        """Perform automatic refresh of charts every 30 seconds."""
        self.schedule_ui_update(self._refresh_all_charts)
        self.after(30000, self._auto_refresh)  # 30 seconds

    def schedule_ui_update(self, update_func: Callable):
        """Schedule a UI update to run on the main thread.
        
        Args:
            update_func: The function to run on the main thread
        """
        self.after_idle(update_func)

    def update_metrics(self, metrics: JobMarketMetrics):
        """Update the dashboard with new metrics data.
        
        Args:
            metrics: The JobMarketMetrics instance to display
        """
        try:
            with self._update_lock:
                self.metrics_history.append(metrics)
                self.schedule_ui_update(self._refresh_all_charts)
        except Exception as e:
            logging.error(f"Error updating analytics dashboard: {e}")

    def _refresh_all_charts(self):
        """Refresh all charts and displays."""
        try:
            self._update_overview()
            self._update_skills_chart()
            self._update_salary_chart()
            self._update_geo_chart()
        except Exception as e:
            logging.error(f"Error refreshing charts: {e}")

    def _update_overview(self):
        """Update the overview tab with latest metrics."""
        if not self.metrics_history:
            return
        
        try:
            latest = self.metrics_history[-1]
            
            # Update labels
            self.total_jobs_label.config(text=f"Total Jobs: {latest.total_jobs:,}")
            self.applications_label.config(text=f"Applications: {latest.total_applications:,}")
            self.success_rate_label.config(text=f"Success Rate: {latest.success_rate:.1%}")
            self.response_time_label.config(text=f"Avg Response: {latest.avg_response_time:.1f}h")
            
            # Update trend chart
            self.trend_figure.clear()
            ax = self.trend_figure.add_subplot(111)
            
            dates = [m.timestamp for m in self.metrics_history]
            jobs = [m.total_jobs for m in self.metrics_history]
            apps = [m.total_applications for m in self.metrics_history]
            
            ax.plot(dates, jobs, 'b-', label='Jobs')
            ax.plot(dates, apps, 'g-', label='Applications')
            
            ax.set_title('Job Market Trends')
            ax.set_xlabel('Time')
            ax.set_ylabel('Count')
            ax.legend()
            ax.grid(True)
            
            self.trend_figure.tight_layout()
            self.trend_canvas.draw()
        except Exception as e:
            logging.error(f"Error updating overview: {e}")

    def _update_skills_chart(self):
        """Update the skills analysis chart with filtered data."""
        if not self.metrics_history:
            return
        
        try:
            latest = self.metrics_history[-1]
            filter_text = self.skills_filter.get().lower()
            
            # Filter skills based on search
            skills = {
                k: v for k, v in latest.skills_demand.items()
                if filter_text in k.lower()
            }
            
            if not skills:
                # Show placeholder when no skills match filter
                self.skills_figure.clear()
                ax = self.skills_figure.add_subplot(111)
                ax.text(
                    0.5, 0.5,
                    "No matching skills found",
                    ha='center',
                    va='center'
                )
            else:
                # Create horizontal bar chart
                self.skills_figure.clear()
                ax = self.skills_figure.add_subplot(111)
                
                y_pos = np.arange(len(skills))
                ax.barh(y_pos, list(skills.values()))
                ax.set_yticks(y_pos)
                ax.set_yticklabels(list(skills.keys()))
                
                ax.set_title('Skills Demand Analysis')
                ax.set_xlabel('Demand Score')
                
            self.skills_figure.tight_layout()
            self.skills_canvas.draw()
        except Exception as e:
            logging.error(f"Error updating skills chart: {e}")

    def _update_salary_chart(self):
        """Update the salary analysis chart."""
        if not self.metrics_history:
            return
        
        try:
            latest = self.metrics_history[-1]
            
            self.salary_figure.clear()
            ax = self.salary_figure.add_subplot(111)
            
            positions = list(latest.salary_ranges.keys())
            mins = [r[0] for r in latest.salary_ranges.values()]
            maxs = [r[1] for r in latest.salary_ranges.values()]
            
            x = np.arange(len(positions))
            width = 0.35
            
            ax.bar(x - width/2, mins, width, label='Minimum')
            ax.bar(x + width/2, maxs, width, label='Maximum')
            
            ax.set_title('Salary Ranges by Position')
            ax.set_xticks(x)
            ax.set_xticklabels(positions)
            ax.set_ylabel('Salary ($)')
            ax.legend()
            
            # Format y-axis as currency
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda x, p: f'${x:,.0f}')
            )
            
            self.salary_figure.tight_layout()
            self.salary_canvas.draw()
        except Exception as e:
            logging.error(f"Error updating salary chart: {e}")

    def _update_geo_chart(self):
        """Update the geographic analysis chart."""
        if not self.metrics_history:
            return
        
        try:
            latest = self.metrics_history[-1]
            
            # Update region combobox if needed
            regions = list(latest.geographic_distribution.keys())
            if self.region_combo['values'] != regions:
                self.region_combo['values'] = regions
                if regions and not self.region_var.get():
                    self.region_var.set(regions[0])
            
            self.geo_figure.clear()
            ax = self.geo_figure.add_subplot(111)
            
            selected_region = self.region_var.get()
            data = latest.geographic_distribution
            
            if selected_region:
                # Show detailed view for selected region
                nearby_regions = {
                    k: v for k, v in data.items()
                    if k == selected_region or v > data.get(selected_region, 0) * 0.5
                }
                
                sizes = list(nearby_regions.values())
                labels = list(nearby_regions.keys())
                
                ax.pie(
                    sizes,
                    labels=labels,
                    autopct='%1.1f%%',
                    startangle=90
                )
                ax.set_title(f'Job Distribution - {selected_region} Region')
            else:
                ax.text(
                    0.5, 0.5,
                    "Select a region to view distribution",
                    ha='center',
                    va='center'
                )
            
            self.geo_figure.tight_layout()
            self.geo_canvas.draw()
        except Exception as e:
            logging.error(f"Error updating geographic chart: {e}")

    def clear(self):
        """Clear all analytics data and reset the display."""
        try:
            with self._update_lock:
                self.metrics_history.clear()
                self.schedule_ui_update(self._clear_display)
        except Exception as e:
            logging.error(f"Error clearing analytics dashboard: {e}")

    def _clear_display(self):
        """Clear all display elements (internal)."""
        # Clear labels
        self.total_jobs_label.config(text="Total Jobs: 0")
        self.applications_label.config(text="Applications: 0")
        self.success_rate_label.config(text="Success Rate: 0%")
        self.response_time_label.config(text="Avg Response: 0h")
        
        # Clear charts
        for fig in [self.trend_figure, self.skills_figure,
                   self.salary_figure, self.geo_figure]:
            fig.clear()
            fig.canvas.draw() 