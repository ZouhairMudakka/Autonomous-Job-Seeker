"""
Test suite for UI components.
Tests the functionality of all UI components in the application.
"""

import pytest
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from ui.components import (
    JobProcessingView, JobCard,
    AIDecisionView, AIDecision,
    PlatformManagerView, PlatformConfig, PlatformStatus,
    AnalyticsDashboard, JobMarketMetrics,
    ProfileManagerView, ProfileVersion
)

# Fixtures
@pytest.fixture
def root():
    """Create a root window for testing."""
    window = tk.Tk()
    yield window
    window.destroy()

@pytest.fixture
def job_processing(root):
    """Create a JobProcessingView instance."""
    view = JobProcessingView(root)
    return view

@pytest.fixture
def ai_decision(root):
    """Create an AIDecisionView instance."""
    view = AIDecisionView(root)
    return view

@pytest.fixture
def platform_manager(root):
    """Create a PlatformManagerView instance."""
    view = PlatformManagerView(root)
    return view

@pytest.fixture
def analytics_dashboard(root):
    """Create an AnalyticsDashboard instance."""
    view = AnalyticsDashboard(root)
    return view

@pytest.fixture
def profile_manager(root):
    """Create a ProfileManagerView instance."""
    view = ProfileManagerView(root)
    return view

# Test JobProcessingView
def test_job_processing_creation(job_processing):
    """Test JobProcessingView initialization."""
    assert job_processing.winfo_exists()
    assert len(job_processing.job_queue) == 0
    assert job_processing.current_job is None

def test_job_processing_update(job_processing):
    """Test updating current job."""
    job = JobCard(
        job_id="test1",
        title="Software Engineer",
        company="Test Corp",
        match_score=0.85,
        status="processing",
        timestamp=datetime.now(),
        details={}
    )
    job_processing.update_current_job(job)
    assert job_processing.current_job == job

# Test AIDecisionView
def test_ai_decision_creation(ai_decision):
    """Test AIDecisionView initialization."""
    assert ai_decision.winfo_exists()
    assert len(ai_decision.decision_history) == 0
    assert ai_decision.current_decision is None

def test_ai_decision_update(ai_decision):
    """Test updating AI decision."""
    decision = AIDecision(
        decision_id="d1",
        confidence_score=0.9,
        reasoning="Test reasoning",
        strategy="Test strategy",
        fallback_triggers=["trigger1", "trigger2"],
        timestamp=datetime.now(),
        metadata={}
    )
    ai_decision.update_decision(decision)
    assert ai_decision.current_decision == decision
    assert len(ai_decision.decision_history) == 1

# Test PlatformManagerView
def test_platform_manager_creation(platform_manager):
    """Test PlatformManagerView initialization."""
    assert platform_manager.winfo_exists()
    assert len(platform_manager.platforms) == 0

def test_platform_manager_add_platform(platform_manager):
    """Test adding a platform."""
    config = PlatformConfig(
        platform_id="p1",
        name="Test Platform",
        enabled=True,
        credentials={},
        settings={},
        last_sync=datetime.now()
    )
    platform_manager.add_platform(config)
    assert "p1" in platform_manager.platforms

# Test AnalyticsDashboard
def test_analytics_dashboard_creation(analytics_dashboard):
    """Test AnalyticsDashboard initialization."""
    assert analytics_dashboard.winfo_exists()
    assert len(analytics_dashboard.metrics_history) == 0

def test_analytics_dashboard_update(analytics_dashboard):
    """Test updating analytics metrics."""
    metrics = JobMarketMetrics(
        timestamp=datetime.now(),
        total_jobs=100,
        applications_sent=50,
        success_rate=0.75,
        avg_response_time=timedelta(days=2),
        skill_demand={"Python": 30, "Java": 20},
        salary_ranges={"Junior": [50000, 60000], "Senior": [90000, 120000]},
        locations={"North America": 60, "Europe": 40}
    )
    analytics_dashboard.update_metrics(metrics)
    assert len(analytics_dashboard.metrics_history) == 1

# Test ProfileManagerView
def test_profile_manager_creation(profile_manager):
    """Test ProfileManagerView initialization."""
    assert profile_manager.winfo_exists()
    assert len(profile_manager.profile_versions) == 0
    assert profile_manager.current_version is None

def test_profile_manager_version_creation(profile_manager):
    """Test creating a new profile version."""
    profile_manager._create_new_version()
    assert len(profile_manager.profile_versions) == 1
    assert profile_manager.current_version is not None

# Integration Tests
def test_component_interaction(root):
    """Test interaction between components."""
    # Create all components
    job_view = JobProcessingView(root)
    ai_view = AIDecisionView(root)
    platform_view = PlatformManagerView(root)
    
    # Test job processing triggering AI decision
    job = JobCard(
        job_id="test1",
        title="Software Engineer",
        company="Test Corp",
        match_score=0.85,
        status="processing",
        timestamp=datetime.now(),
        details={}
    )
    job_view.update_current_job(job)
    
    decision = AIDecision(
        decision_id="d1",
        confidence_score=job.match_score,
        reasoning=f"Processing job at {job.company}",
        strategy="Standard application",
        fallback_triggers=[],
        timestamp=datetime.now(),
        metadata={"job_id": job.job_id}
    )
    ai_view.update_decision(decision)
    
    # Verify interaction results
    assert job_view.current_job.job_id == "test1"
    assert ai_view.current_decision.metadata["job_id"] == "test1" 