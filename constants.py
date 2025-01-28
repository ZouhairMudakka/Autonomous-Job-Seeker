"""
Global Constants Module

Contains all timing constants and other global configuration values used across agents.
Serves as the single source of truth for timing configurations, DOM selectors, and
standardized log messages.
"""

class TimingConstants:
    """Timing constants for delays and timeouts."""
    
    # Base delays
    BASE_RETRY_DELAY = 2000  # 2 seconds
    ACTION_DELAY = 1000  # 1 second
    POLL_INTERVAL = 2000     # 2 seconds in ms
    
    # Verification delays
    VERIFICATION_DELAY = 1000      # 1 second
    EXTENDED_VERIFICATION_DELAY = 3000  # 3 seconds
    
    # Wait periods
    EXTENDED_WAIT_DELAY = 10000  # 10 seconds
    RATE_LIMIT_DELAY = 5000  # 5 seconds
    
    # Default timeouts
    DEFAULT_TIMEOUT = 30000  # 30 seconds
    
    # Human-like delays
    HUMAN_DELAY_MIN = 0.5
    HUMAN_DELAY_MAX = 2.0
    
    # Processing delays
    PDF_PAGE_PARSE_DELAY = 100    # 0.1 seconds
    FILE_READ_DELAY = 100         # 0.1 seconds
    LLM_PROCESSING_DELAY = 1000   # 1 second
    VALIDATION_DELAY = 500        # 0.5 seconds

    # -------------------------------------
    # Maximum wait / timeouts
    # -------------------------------------
    MAX_WAIT_TIME = 60000  # 1 minute
    NAVIGATION_TIMEOUT = 15000  # ms - special wait for page loads
    NETWORK_IDLE_TIMEOUT = 10000   # ms - wait for network activity to settle

    # -------------------------------------
    # Human-like interaction delays
    # -------------------------------------
    DRAG_HOLD_MIN = 0.5    # s - minimum time to hold during drag operations
    DRAG_HOLD_MAX = 1.0    # s - maximum time to hold during drag operations

    # -------------------------------------
    # Standard operation delays
    # -------------------------------------
    PAGE_TRANSITION_DELAY = 2000  # 2 seconds
    TEXT_EXTRACTION_DELAY = 1000  # 1 second
    SCREENSHOT_DELAY = 500  # 0.5 seconds
    SCROLL_STEP_DELAY = 0.5   # s - delay between scroll steps
    ERROR_DELAY = 3000  # 3 seconds

    # -------------------------------------
    # Retry configurations
    # -------------------------------------
    MAX_RETRIES = 3                # maximum number of retry attempts
    RETRY_BACKOFF_FACTOR = 2       # multiply delay by this factor each retry

    # -------------------------------------
    # Task Manager specific
    # -------------------------------------
    QUEUE_CHECK_INTERVAL = 1000  # 1 second
    TASK_TIMEOUT = 300000  # 5 minutes

    # -------------------------------------
    # Form-specific
    # -------------------------------------
    FORM_SUBMIT_DELAY = 2.0  # s - delay after form submission
    FORM_FIELD_DELAY = 0.5   # s - delay between filling form fields
    FORM_VALIDATION_DELAY = 1.0  # s - delay to wait for form validation
    FILE_UPLOAD_DELAY = 2000  # 2 seconds

    # -------------------------------------
    # LinkedIn specific
    # -------------------------------------
    EASY_APPLY_MODAL_DELAY = 2.0   # s - wait for Easy Apply modal to appear
    JOB_CARD_LOAD_DELAY = 2.0      # s - wait for job details to load
    NEXT_PAGE_DELAY = 3.0          # s - wait after clicking next page
    INFINITE_SCROLL_DELAY = 2.0    # s - wait after scroll for content to load
    PROFILE_LOAD_DELAY = 3.0       # s - wait for profile content to load
    SEARCH_RESULTS_DELAY = 2.0     # s - wait for search results to update

    # -------------------------------------
    # Cookie and Modal handling
    # -------------------------------------
    COOKIE_BANNER_TIMEOUT = 3000    # ms - time to wait for cookie banner
    MODAL_TRANSITION_DELAY = 1000  # 1 second
    POPUP_CHECK_DELAY = 0.5         # s - interval to check for popups

    # Add these missing constants used in LinkedInAgent
    SEARCH_FIELD_DELAY = 1.0    # s - delay between search field interactions
    SEARCH_BUTTON_DELAY = 2.0   # s - delay after clicking search button
    SEARCH_LOAD_DELAY = 3.0     # s - wait for search results to load initially

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
