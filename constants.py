"""
Global Constants Module

Contains all timing constants and other global configuration values used across agents.
Serves as the single source of truth for timing configurations, DOM selectors, and
standardized log messages.
"""

class TimingConstants:
    """Timing constants for delays and timeouts. All values in milliseconds (ms)."""
    
    # Base delays - Minimal core delays
    BASE_RETRY_DELAY = 200    # 200ms (0.2s) - minimum time to retry operations
    ACTION_DELAY = 20         # 20ms (0.02s) - minimum action delay
    POLL_INTERVAL = 100       # 100ms (0.1s) - fast but not CPU intensive
    
    # Verification delays - Quick checks
    VERIFICATION_DELAY = 200        # 200ms (0.2s) - quick verification
    EXTENDED_VERIFICATION_DELAY = 500  # 500ms (0.5s) - for complex verifications
    
    # Wait periods - Reduced but maintaining rate limit compliance
    EXTENDED_WAIT_DELAY = 1000  # 1000ms (1s) - for complex operations
    RATE_LIMIT_DELAY = 1000     # 1000ms (1s) - minimum safe rate limit
    
    # Default timeouts - Balanced for reliability
    DEFAULT_TIMEOUT = 5000   # 5000ms (5s) - faster timeout for operations
    
    # Human-like delays - Maintain some human-like behavior
    HUMAN_DELAY_MIN = 100    # 100ms (0.1s) - Faster but still human-like
    HUMAN_DELAY_MAX = 300    # 300ms (0.3s) - Reduced maximum delay
    
    # Processing delays - Minimal processing times
    PDF_PAGE_PARSE_DELAY = 50     # 50ms (0.05s)
    FILE_READ_DELAY = 50          # 50ms (0.05s)
    LLM_PROCESSING_DELAY = 200    # 200ms (0.2s)
    VALIDATION_DELAY = 100        # 100ms (0.1s)

    # -------------------------------------
    # Maximum wait / timeouts - Reduced maximums
    # -------------------------------------
    MAX_WAIT_TIME = 10000        # 10000ms (10s) - reduced from 30s
    NAVIGATION_TIMEOUT = 5000    # 5000ms (5s) - faster navigation timeout
    NETWORK_IDLE_TIMEOUT = 2000  # 2000ms (2s) - faster network idle

    # -------------------------------------
    # Human-like interaction delays - Minimal but still human-like
    # -------------------------------------
    DRAG_HOLD_MIN = 100    # 100ms (0.1s) - faster drag operations
    DRAG_HOLD_MAX = 200    # 200ms (0.2s) - reduced maximum drag time

    # -------------------------------------
    # Standard operation delays - Optimized core operations
    # -------------------------------------
    PAGE_TRANSITION_DELAY = 300
    TEXT_EXTRACTION_DELAY = 200   # 200ms (0.2s) - quick text extraction
    SCREENSHOT_DELAY = 100        # 100ms (0.1s) - quick screenshots
    SCROLL_STEP_DELAY = 100       # 100ms (0.1s) - faster scrolling
    ERROR_DELAY = 200             # 200ms (0.2s) - reduced error delay

    # -------------------------------------
    # File operation delays - Minimal safe delays
    # -------------------------------------
    FILE_UPLOAD_DELAY = 200      # 200ms (0.2s) - reduced file operation delay

    # -------------------------------------
    # Retry configurations - More aggressive retry strategy
    # -------------------------------------
    MAX_RETRIES = 2              # Number of retry attempts
    RETRY_BACKOFF_FACTOR = 1.2   # Multiply delay by this factor each retry

    # -------------------------------------
    # Task Manager specific - Faster task management
    # -------------------------------------
    QUEUE_CHECK_INTERVAL = 200   # 200ms (0.2s) - faster queue checks
    TASK_TIMEOUT = 30000        # 30000ms (30s) - reduced task timeout

    # -------------------------------------
    # Form-specific - Optimized form interactions
    # -------------------------------------
    FORM_SUBMIT_DELAY = 300      # 300ms (0.3s) - faster form submission
    FORM_FIELD_DELAY = 100       # 100ms (0.1s) - faster field filling
    FORM_VALIDATION_DELAY = 200  # 200ms (0.2s) - quicker validation

    # -------------------------------------
    # LinkedIn specific - Platform-specific optimizations
    # -------------------------------------
    EASY_APPLY_MODAL_DELAY = 500    # 500ms (0.5s) - faster modal handling
    JOB_CARD_LOAD_DELAY = 500       # 500ms (0.5s) - faster card loading
    NEXT_PAGE_DELAY = 700           # 700ms (0.7s) - faster page navigation
    INFINITE_SCROLL_DELAY = 500     # 500ms (0.5s) - faster scroll handling
    PROFILE_LOAD_DELAY = 700        # 700ms (0.7s) - faster profile loading
    SEARCH_RESULTS_DELAY = 500      # 500ms (0.5s) - faster search results

    # -------------------------------------
    # Cookie and Modal handling - Quick UI interactions
    # -------------------------------------
    COOKIE_BANNER_TIMEOUT = 500     # 500ms (0.5s) - faster cookie handling
    MODAL_TRANSITION_DELAY = 200    # 200ms (0.2s) - faster modal transitions
    POPUP_CHECK_DELAY = 100         # 100ms (0.1s) - quick popup checks

    # LinkedIn search specific - Optimized search operations
    SEARCH_FIELD_DELAY = 200
    SEARCH_BUTTON_DELAY = 300    # 300ms (0.3s) - faster button click
    SEARCH_LOAD_DELAY = 500      # 500ms (0.5s) - faster search loading

class Selectors:
    """
    Common selectors used across different agents.
    Helps maintain consistency and makes updates easier.
    """
    # LinkedIn selectors
    LINKEDIN_JOBS_TAB = 'a[data-control-name="nav_jobs"]'
    LINKEDIN_EASY_APPLY_BUTTON = 'button.jobs-apply-button'
    LINKEDIN_JOB_CARD = 'li.jobs-search-results__list-item'
    LINKEDIN_NEXT_BUTTON = 'button[aria-label="Next"]'

    # Captcha example (if needed)
    LINKEDIN_CAPTCHA_IMAGE = 'img.captcha__image'

    # Form selectors
    FORM_SUBMIT_BUTTON = 'button[type="submit"]'
    FORM_NEXT_BUTTON = 'button[aria-label="Continue to next step"]'
    FORM_FILE_UPLOAD = 'input[type="file"]'

    # Optional extra: If you frequently find yourself referencing login or cookie banners:
    COOKIES_ACCEPT_BUTTON = 'button#accept-cookies'

    # Application form selectors
    APPLICATION_FORM = "form[data-test='application-form']"  # Update with actual selector
    CV_UPLOAD_INPUT = "input[type='file'][accept='.pdf,.doc,.docx']"  # Update with actual selector
    COVER_LETTER_INPUT = "textarea[aria-label='Cover letter']"  # Update with actual selector
    SUBMIT_APPLICATION = "button[type='submit']"  # Update with actual selector

    # Add these missing LinkedIn selectors
    LINKEDIN_SEARCH_TITLE = 'input[aria-label="Search by title..."]'
    LINKEDIN_SEARCH_LOCATION = 'input[aria-label="City, state, or zip code"]'
    LINKEDIN_SEARCH_BUTTON = 'button[type="submit"]'
    LINKEDIN_JOBS_CONTAINER = '.jobs-search-results-list'
    
    # Add form handling selectors
    LINKEDIN_FORM_ERROR = '.artdeco-inline-feedback--error'
    LINKEDIN_FORM_SUCCESS = '.artdeco-inline-feedback--success'
    LINKEDIN_MODAL_CLOSE = 'button[aria-label="Dismiss"]'

class Messages:
    """
    Standard messages used across agents for consistent logging.
    """
    # Session messages
    PAUSE_MESSAGE = "Pausing operations..."
    RESUME_MESSAGE = "Resuming operations..."
    
    # Operation status
    TIMEOUT_MESSAGE = "Operation timed out after {} seconds."
    RETRY_MESSAGE = "Attempt {}/{} failed: {}"
    SUCCESS_MESSAGE = "Operation completed successfully."
    
    # Authentication/Security
    CAPTCHA_MESSAGE = "Captcha encountered, manual solve needed."
    LOGOUT_MESSAGE = "User is logged out, re-login required."
    
    # Error messages
    SEARCH_ERROR = "Failed to perform job search: {}"
    FORM_ERROR = "Form submission failed: {}"
    NETWORK_ERROR = "Network connection issue: {}"
    ELEMENT_NOT_FOUND = "Element not found: {}"
    
    # Task management
    TASK_CREATED = "Created new task: {}"
    TASK_COMPLETED = "Task completed successfully: {}"
    TASK_FAILED = "Task failed: {}"
    
    # Plan execution
    PLAN_STARTED = "Starting execution of master plan: {}"
    PLAN_MODIFIED = "Plan modified due to conditions: {}"
    PLAN_COMPLETED = "Master plan completed successfully"
    PLAN_FAILED = "Master plan failed: {}"
    
    # Rate limiting
    RATE_LIMIT_DETECTED = "Rate limiting detected, adding delays"
    RATE_LIMIT_RESOLVED = "Rate limiting condition resolved"
    
    # State management
    STATE_SAVED = "Session state saved successfully"
    STATE_RESTORED = "Session state restored successfully"
    STATE_INVALID = "Invalid session state: {}"

class DebugTimingConstants:
    """Constants for debug timing and logging."""
    
    # Debug log formats
    SLEEP_START_FORMAT = "[DEBUG] About to sleep for {seconds} seconds. Reason: {reason}"
    SLEEP_END_FORMAT = "[DEBUG] Finished sleeping. Duration was {duration:.2f} seconds."
    
    # Debug timing flags
    ENABLE_DEBUG_TIMING = True  # Master switch for debug timing
    LOG_ALL_WAITS = True       # Log all wait operations
    LOG_LONG_WAITS = True      # Log only waits over threshold
    LONG_WAIT_THRESHOLD = 1.0  # Threshold in seconds for long wait logging

class DebugSleepHelper:
    """Helper class for debug timing functionality."""
    
    @staticmethod
    def format_sleep_start(seconds: float, reason: str = "") -> str:
        """Format the sleep start debug message."""
        return DebugTimingConstants.SLEEP_START_FORMAT.format(
            seconds=seconds,
            reason=reason
        )
    
    @staticmethod
    def format_sleep_end(duration: float) -> str:
        """Format the sleep end debug message."""
        return DebugTimingConstants.SLEEP_END_FORMAT.format(
            duration=duration
        )
    
    @staticmethod
    def should_log_wait(duration: float) -> bool:
        """Determine if a wait should be logged based on settings."""
        if not DebugTimingConstants.ENABLE_DEBUG_TIMING:
            return False
        if DebugTimingConstants.LOG_ALL_WAITS:
            return True
        if (DebugTimingConstants.LOG_LONG_WAITS and 
            duration >= DebugTimingConstants.LONG_WAIT_THRESHOLD):
            return True
        return False
