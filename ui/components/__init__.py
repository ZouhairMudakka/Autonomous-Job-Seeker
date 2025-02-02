"""
UI Components Module
Contains reusable UI components for the LinkedIn Automation Tool.
"""

from .job_processing import JobProcessingView, JobCard
from .ai_decision import AIDecisionView, AIDecision
from .platform_manager import PlatformManagerView, PlatformConfig, PlatformStatus
from .analytics import AnalyticsDashboard, JobMarketMetrics
from .profile_manager import ProfileManagerView, ProfileVersion

__all__ = [
    # Job Processing
    'JobProcessingView',
    'JobCard',
    
    # AI Decision
    'AIDecisionView',
    'AIDecision',
    
    # Platform Management
    'PlatformManagerView',
    'PlatformConfig',
    'PlatformStatus',
    
    # Analytics
    'AnalyticsDashboard',
    'JobMarketMetrics',
    
    # Profile Management
    'ProfileManagerView',
    'ProfileVersion'
]

# Future imports for components like:
# from .job_processing import JobProcessingView
# from .analytics import AnalyticsDashboard
# etc. 