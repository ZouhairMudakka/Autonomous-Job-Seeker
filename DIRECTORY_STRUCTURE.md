# Project Directory Structure

```
AI Browser Job Workflow/
├── .env                    # Environment variables and API keys configuration
├── .env.example           # Template showing required environment variables
├── .gitignore            # Specifies which files Git should ignore
├── LICENSE               # Project license information
├── README.md            # Project overview and setup instructions
├── DIRECTORY_STRUCTURE.md # Documentation of project structure
├── main.py              # Main application entry point and initialization
├── requirements.txt     # Python package dependencies and versions
├── ROADMAP.md           # Project development roadmap and milestones
│
├── agents/             # AI Agents implementation
│   ├── __init__.py    # Agents package initialization
│   ├── credentials_agent.py    # Handles user authentication and credentials
│   ├── form_filler_agent.py    # Automates job application form filling
│   ├── general_agent.py        # Base agent class and common functionality
│   ├── linkedin_agent.py       # LinkedIn-specific automation and interactions
│   ├── tracker_agent.py        # Tracks job application status and progress
│   └── user_profile_agent.py   # Manages user profile data and preferences
│   └── ai_navigator.py         # AI-driven navigation with confidence scoring
│
├── config/             # Configuration management
│   ├── __init__.py    # Package exports and load_settings function
│   └── settings.py    # Browser config, env vars, directory setup, validation
│
├── models/            # Data models and validation
│   ├── __init__.py   # Exports CVData, UserProfile, JobPosting, ApplicationStatus
│   ├── application_models.py  # Application lifecycle and status tracking
│   ├── cv_models.py          # CV/Resume data: personal info, experience, education
│   ├── job_models.py         # Job details, company info, matching scores
│   └── user_models.py        # User info and job preferences
│
├── orchestrator/       # Job workflow orchestration
│   ├── __init__.py    # Orchestrator package initialization
│   ├── controller.py  # Main workflow control and coordination
│   └── task_manager.py # Task scheduling and management
│
├── storage/           # Data storage and logging
│   ├── __init__.py   # Storage package initialization
│   ├── csv_storage.py # CSV-based data persistence
│   ├── logs_manager.py # Application logging and monitoring
│   └── learning_pipeline.py # AI learning and performance tracking
│
├── tests/            # Test suite
│   ├── __init__.py  # Tests package initialization
│   ├── fixtures/    # Test data and mock objects
│   ├── integration/ # End-to-end and integration tests
│   └── unit/       # Unit tests for individual components
│
├── utils/             # Utility functions and helpers
│   ├── __init__.py   # Package initialization
│   ├── application_utils.py  # Application tracking utilities
│   ├── browser_setup.py     # Browser initialization and configuration
│   ├── confidence_scorer.py # AI confidence scoring and threshold management
│   ├── cv_utils.py          # CV/Resume data processing
│   ├── data_export_utils.py # Data export and reporting
│   ├── document_processor.py # PDF/DOCX/TXT processing
│   ├── job_match_utils.py   # Job matching and scoring
│   ├── model_utils.py       # Model serialization/deserialization
│   ├── regex_utils.py       # Regex patterns and text extraction
│   ├── telemetry.py        # System telemetry and performance tracking
│   ├── telemetry_viewer.py # Interactive telemetry visualization + GPT analysis
│   └── text_cleaning.py     # Text normalization and cleaning
│
├── data/                # Data storage and persistence
│   ├── activity_log.csv      # Automation activity logging
│   ├── telemetry/            # Telemetry data storage
│   │   ├── events/          # Telemetry event logs
│   │   └── metrics/         # Performance metrics
│   └── cookies/             # Browser cookie storage
│       ├── browser_cookies.json  # Saved browser cookies
│       └── cookies.json         # Application cookies
│
└── ui/              # User interface components
    ├── __init__.py  # UI package initialization
    ├── cli.py      # Command-line interface implementation
    ├── minimal_gui.py        # Simple desktop GUI implementation
    └── extension/  # Browser extension related files
        ├── manifest.json # Extension configuration
        ├── background.js # Background processes
        ├── content.js   # Content scripts for page interaction
        ├── linkedin_automation_host.json  # Native messaging config
        ├── options.html          # Settings page HTML
        ├── options.js            # Settings page logic
        ├── popup.html           # Extension popup HTML
        └── popup.js             # Extension popup logic

