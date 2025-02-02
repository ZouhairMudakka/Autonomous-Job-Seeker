"""
Base agent class demonstrating proper debug sleep usage.
"""

from typing import Optional
from ..constants import TimingConstants
from ..debug_sleep import debug_sleep
from ..storage.logs_manager import LogsManager

class BaseAgent:
    """Base agent class with debug sleep integration."""
    
    def __init__(self, logs_manager: Optional[LogsManager] = None):
        """Initialize base agent with optional logs manager."""
        self.logs_manager = logs_manager
    
    async def wait_for_element(self, selector: str, timeout: float = TimingConstants.DEFAULT_TIMEOUT) -> None:
        """Example method showing how to use debug sleep for element waiting."""
        await debug_sleep.sleep(
            TimingConstants.POLL_INTERVAL / 1000,  # Convert ms to seconds
            f"Polling for element: {selector}"
        )
    
    async def perform_action(self, action_name: str) -> None:
        """Example method showing how to use debug sleep for action delays."""
        # Pre-action delay
        await debug_sleep.sleep(
            TimingConstants.ACTION_DELAY / 1000,
            f"Pre-action delay for: {action_name}"
        )
        
        # Simulate action
        print(f"Performing action: {action_name}")
        
        # Post-action delay
        await debug_sleep.sleep(
            TimingConstants.ACTION_DELAY / 1000,
            f"Post-action delay for: {action_name}"
        )
    
    async def handle_rate_limit(self) -> None:
        """Example method showing how to use debug sleep for rate limiting."""
        await debug_sleep.sleep(
            TimingConstants.RATE_LIMIT_DELAY / 1000,
            "Rate limit cooldown"
        )
    
    async def transition_page(self, page_name: str) -> None:
        """Example method showing how to use debug sleep for page transitions."""
        await debug_sleep.sleep(
            TimingConstants.PAGE_TRANSITION_DELAY / 1000,
            f"Transitioning to page: {page_name}"
        )
    
    async def process_form(self, form_name: str) -> None:
        """Example method showing how to use debug sleep for form processing."""
        # Pre-form delay
        await debug_sleep.sleep(
            TimingConstants.FORM_FIELD_DELAY,
            f"Starting form processing: {form_name}"
        )
        
        # Simulate form field filling
        print(f"Filling form: {form_name}")
        
        # Inter-field delay
        await debug_sleep.sleep(
            TimingConstants.FORM_FIELD_DELAY,
            f"Moving to next field in form: {form_name}"
        )
        
        # Form submission delay
        await debug_sleep.sleep(
            TimingConstants.FORM_SUBMIT_DELAY,
            f"Submitting form: {form_name}"
        ) 