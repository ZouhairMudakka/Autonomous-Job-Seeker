"""
Global Constants Module

Contains all timing constants and other global configuration values used across agents.
Serves as the single source of truth for timing configurations, DOM selectors, and
standardized log messages.
"""

class TimingConstants:
    # -------------------------------------
    # Maximum wait / timeouts
    # -------------------------------------
    MAX_WAIT_TIME = 10000  # ms (10s) - maximum wait for any operation
    DEFAULT_TIMEOUT = 10000  # ms - default timeout for element waits
    NAVIGATION_TIMEOUT = 15000  # ms - special wait for page loads
    NETWORK_IDLE_TIMEOUT = 10000   # ms - wait for network activity to settle

    # -------------------------------------
    # Human-like interaction delays
    # -------------------------------------
    HUMAN_DELAY_MIN = 0.3  # s - minimum delay for human-like interactions
    HUMAN_DELAY_MAX = 1.0  # s - maximum delay for human-like interactions
    DRAG_HOLD_MIN = 0.5    # s - minimum time to hold during drag operations
    DRAG_HOLD_MAX = 1.0    # s - maximum time to hold during drag operations

    # -------------------------------------
    # Standard operation delays
    # -------------------------------------
    POLL_INTERVAL = 0.5       # s - interval for checking conditions or queues
    ACTION_DELAY = 2.0        # s - delay for major actions (clicks, submissions)
    PAGE_TRANSITION_DELAY = 3.0  # s - delay for page transitions/navigation
    TEXT_EXTRACTION_DELAY = 1.0  # s - delay after text extraction operations
    SCREENSHOT_DELAY = 1.0    # s - delay before taking screenshots
    SCROLL_STEP_DELAY = 0.5   # s - delay between scroll steps
    ERROR_DELAY = 3.0         # s - delay used after errors occur

    # -------------------------------------
    # Retry configurations
    # -------------------------------------
    MAX_RETRIES = 3                # maximum number of retry attempts
    BASE_RETRY_DELAY = 2.0         # s - base delay for exponential backoff
    RETRY_BACKOFF_FACTOR = 2       # multiply delay by this factor each retry

    # -------------------------------------
    # Task Manager specific
    # -------------------------------------
    QUEUE_CHECK_INTERVAL = 0.5  # s - how often to check the task queue
    TASK_TIMEOUT = 300.0       # s - maximum time to wait for a task to complete

    # -------------------------------------
    # Form-specific
    # -------------------------------------
    FORM_SUBMIT_DELAY = 2.0  # s - delay after form submission
    FORM_FIELD_DELAY = 0.5   # s - delay between filling form fields
    FORM_VALIDATION_DELAY = 1.0  # s - delay to wait for form validation
    FILE_UPLOAD_DELAY = 3.0   # s - delay after file upload operations

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
    MODAL_TRANSITION_DELAY = 1.0    # s - wait for modal animations
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
    PAUSE_MESSAGE = "Pausing operations..."
    RESUME_MESSAGE = "Resuming operations..."
    TIMEOUT_MESSAGE = "Operation timed out after {} seconds."
    RETRY_MESSAGE = "Attempt {}/{} failed: {}"
    SUCCESS_MESSAGE = "Operation completed successfully."
    # If you want standard text for errors, logs, etc.:
    CAPTCHA_MESSAGE = "Captcha encountered, manual solve needed."
    LOGOUT_MESSAGE = "User is logged out, re-login required."

    # Add these missing messages
    SEARCH_ERROR = "Failed to perform job search: {}"
    FORM_ERROR = "Form submission failed: {}"
    NETWORK_ERROR = "Network connection issue: {}"
    ELEMENT_NOT_FOUND = "Element not found: {}"
    TASK_CREATED = "Created new task: {}"
    TASK_COMPLETED = "Task completed successfully: {}"
    TASK_FAILED = "Task failed: {}"
