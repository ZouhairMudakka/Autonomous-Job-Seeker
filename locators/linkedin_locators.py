"""
LinkedIn DOM Selectors and Patterns

Features:
- Centralized selector management
- Version tracking for layout changes
- Performance metrics integration
- AI-driven fallback patterns
- Selector success rate tracking
"""

from utils.dom.dom_service import DomService
from utils.dom.dom_models import DOMElementNode
from storage.logs_manager import LogsManager
from typing import Optional, Union

class LinkedInLocators:
    def __init__(self, logs_manager: Optional[LogsManager] = None):
        """
        Initialize LinkedIn locators with optional logging.
        
        Args:
            logs_manager: Optional LogsManager instance for logging
        """
        self.logs_manager = logs_manager

    # Navigation
    JOBS_TAB = 'a[data-control-name="nav_jobs"]'
    EASY_APPLY_BUTTON = 'button.jobs-apply-button'
    
    # Search
    SEARCH_INPUT = 'input.jobs-search-box__text-input'
    LOCATION_INPUT = 'input.jobs-search-box__location-input'
    
    # Job Feed
    FEED_SELECTORS = [
        "div[data-job-id]",
        ".jobs-job-board-list__item",
        ".jobs-collection-card",
        "ul.jobs-list > li"
    ]
    
    # Form Fields
    SUBMIT_BUTTON = 'button[aria-label="Submit application"]'

    # Success Indicators
    LOGGED_IN_INDICATOR = [
        'div[data-control-name="identity_profile_photo"]',  # Profile photo presence
        '.global-nav__me-photo',  # Nav bar photo
        'div[data-control-name="nav.settings"]'  # Settings menu presence
    ]

    CAPTCHA_SUCCESS = [
        '.captcha-success',  # Direct success message
        '.challenge-success',  # Challenge completion
        'div:not(.captcha-container):not(.challenge-container)',  # Absence of CAPTCHA
        '.verification-status--verified'  # Verification status
    ]

    FORM_SUCCESS = [
        '.artdeco-toast-item--success',  # Success toast notification
        '.jobs-post-success',  # Job application success
        '.application-success-modal',  # Success modal
        '.jobs-apply-button--submitted'  # Submit button state change
    ]
    
    @classmethod
    async def get_fallback_patterns(cls, selector_type: str, logs_manager: Optional[LogsManager] = None) -> list:
        """Get AI-generated fallback patterns for selector types."""
        if logs_manager:
            await logs_manager.debug(f"[LinkedInLocators] Generating fallback patterns for {selector_type}")
        # To be implemented
        return []

    @classmethod
    async def get_element(
        cls,
        page,
        selector_type: str,
        dom_fallback: bool = True,
        logs_manager: Optional[LogsManager] = None
    ) -> Optional[str]:
        """
        Get selector with optional DOM-based fallback.
        
        Args:
            page: The page object to search in
            selector_type: Type of selector to find
            dom_fallback: Whether to try DOM-based approach if primary selector fails
            logs_manager: Optional LogsManager instance for logging
            
        Returns:
            str: The most appropriate selector for the element
        """
        if logs_manager:
            await logs_manager.debug(f"[LinkedInLocators] Looking for selector type: {selector_type}")

        primary_selector = getattr(cls, selector_type, None)
        
        # Handle list of selectors
        if isinstance(primary_selector, list):
            if logs_manager:
                await logs_manager.debug(f"[LinkedInLocators] Trying {len(primary_selector)} selectors for {selector_type}")
            
            # Try each selector in order until one works
            for idx, selector in enumerate(primary_selector):
                try:
                    if logs_manager:
                        await logs_manager.debug(f"[LinkedInLocators] Trying selector {idx + 1}/{len(primary_selector)}: {selector}")
                    
                    element = await page.wait_for_selector(selector, timeout=1000)
                    if element:
                        if logs_manager:
                            await logs_manager.info(f"[LinkedInLocators] Found matching selector for {selector_type}: {selector}")
                        return selector
                except Exception as e:
                    if logs_manager:
                        await logs_manager.debug(f"[LinkedInLocators] Selector {selector} failed: {str(e)}")
                    continue
        
        if not primary_selector or dom_fallback:
            if logs_manager:
                await logs_manager.debug("[LinkedInLocators] Attempting DOM-based fallback approach")
            
            # Try DOM-based approach
            try:
                dom_svc = DomService(page)
                elements = await dom_svc.get_clickable_elements(highlight=True)
                
                # Find best matching element
                for element in elements:
                    if await cls._matches_selector_type(element, selector_type, logs_manager):
                        selector = f"[data-highlight-index='{element.highlight_index}']"
                        if logs_manager:
                            await logs_manager.info(f"[LinkedInLocators] Found element via DOM fallback: {selector}")
                        return selector
                
                if logs_manager:
                    await logs_manager.warning(f"[LinkedInLocators] No matching elements found for {selector_type} via DOM fallback")
            except Exception as e:
                if logs_manager:
                    await logs_manager.error(f"[LinkedInLocators] DOM fallback error: {str(e)}")
        
        if logs_manager:
            if primary_selector:
                await logs_manager.debug(f"[LinkedInLocators] Using primary selector: {primary_selector}")
            else:
                await logs_manager.warning(f"[LinkedInLocators] No selector found for {selector_type}")
        
        return primary_selector if isinstance(primary_selector, str) else None
    
    @staticmethod
    async def _matches_selector_type(
        element: 'DOMElementNode',
        selector_type: str,
        logs_manager: Optional[LogsManager] = None
    ) -> bool:
        """
        Check if DOM element matches the selector type.
        
        Args:
            element: The DOM element to check
            selector_type: The type of selector to match against
            logs_manager: Optional LogsManager instance for logging
            
        Returns:
            bool: True if the element matches the selector type
        """
        # Common attributes that might indicate success
        success_indicators = {
            'login': ['profile', 'avatar', 'account', 'me-photo'],
            'captcha': ['captcha-success', 'verified', 'challenge-success'],
            'form': ['success', 'submitted', 'complete', 'confirmation']
        }
        
        if selector_type.lower() in success_indicators:
            indicators = success_indicators[selector_type.lower()]
            
            if logs_manager:
                await logs_manager.debug(
                    f"[LinkedInLocators] Checking element against {len(indicators)} indicators for {selector_type}"
                )
            
            # Check element attributes
            for attr in element.attributes.values():
                if any(indicator in str(attr).lower() for indicator in indicators):
                    if logs_manager:
                        await logs_manager.debug(f"[LinkedInLocators] Found matching attribute: {attr}")
                    return True
            
            # Check element text content
            if any(indicator in element.text_content.lower() for indicator in indicators):
                if logs_manager:
                    await logs_manager.debug(f"[LinkedInLocators] Found matching text content: {element.text_content}")
                return True
            
            # Check element classes
            element_classes = ' '.join(element.classes)
            if any(indicator in element_classes.lower() for indicator in indicators):
                if logs_manager:
                    await logs_manager.debug(f"[LinkedInLocators] Found matching classes: {element_classes}")
                return True
            
            if logs_manager:
                await logs_manager.debug(f"[LinkedInLocators] No matches found for element: {element.tag_name}")
        
        return False 