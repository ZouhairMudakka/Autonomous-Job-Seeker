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
├── constants.py         # Global constants and configuration
├── __init__.py         # Root package initialization
│
├── agents/             # AI Agents implementation
│   ├── __init__.py    # Agents package initialization
│   ├── ai_navigator.py # AI-driven navigation with confidence scoring
│   ├── credentials_agent.py    # Handles user authentication and credentials
│   ├── cv_parser_agent.py     # CV parsing and extraction
│   ├── form_filler_agent.py    # Automates job application form filling
│   ├── general_agent.py        # Base agent class and common functionality
│   ├── linkedin_agent.py       # LinkedIn-specific automation and interactions
│   ├── tracker_agent.py        # Tracks application status and progress
│   └── user_profile_agent.py   # Manages user profile data
│
├── config/             # Configuration management
│   ├── __init__.py
│   └── settings.py     # Application settings and configuration
│
├── locators/           # Element selectors and locators
│   └── linkedin_locators.py  # LinkedIn-specific selectors
│
├── models/             # Data models and schemas
│   ├── __init__.py
│   ├── application_models.py  # Job application data models
│   ├── cv_models.py          # CV/Resume data models
│   ├── job_models.py         # Job posting data models
│   └── user_models.py        # User profile data models
│
├── orchestrator/       # Task orchestration and control
│   ├── __init__.py
│   ├── controller.py   # Main application controller
│   └── task_manager.py # Task scheduling and management
│
├── storage/           # Data persistence and logging
│   ├── __init__.py
│   ├── csv_storage.py  # CSV-based data storage
│   ├── learning_pipeline.py  # AI learning data pipeline
│   └── logs_manager.py # Logging configuration and management
│
├── tests/             # Test suite
│   ├── __init__.py
│   ├── conftest.py    # Test configuration
│   ├── test_dom_features.py  # DOM functionality tests
│   ├── integration/   # Integration tests
│   │   ├── __init__.py
│   │   └── test_controller.py
│   └── unit/         # Unit tests
│       ├── __init__.py
│       ├── test_csv_storage.py
│       └── test_linkedin_agent.py
│
├── ui/               # User interface components
│   ├── __init__.py
│   ├── cli.py       # Command-line interface
│   ├── minimal_gui.py # Basic GUI implementation
│   └── extension/   # Chrome extension
│       ├── background.js
│       ├── content_script.js
│       ├── options.html
│       ├── options.js
│       ├── popup.html
│       └── popup.js
│
└── utils/            # Utility functions and helpers
    ├── __init__.py
    ├── application_utils.py  # Application-specific utilities
    ├── browser_setup.py     # Browser initialization
    ├── confidence_scorer.py # Confidence scoring utilities
    ├── cv_utils.py         # CV processing utilities
    ├── data_export_utils.py # Data export functions
    ├── document_processor.py # Document handling
    ├── job_match_utils.py   # Job matching algorithms
    ├── model_utils.py       # Model helper functions
    ├── regex_utils.py       # Regular expression utilities
    ├── telemetry.py        # Telemetry collection
    ├── telemetry_viewer.py # Telemetry visualization
    ├── text_cleaning.py    # Text processing utilities
    ├── universal_model.py  # Universal data model utilities
    └── dom/              # DOM interaction and management
        ├── __init__.py
        ├── build_dom_tree.js  # DOM tree construction
        ├── dom_history.py    # DOM state tracking
        ├── dom_models.py     # DOM element models
        └── dom_service.py    # DOM interaction service

