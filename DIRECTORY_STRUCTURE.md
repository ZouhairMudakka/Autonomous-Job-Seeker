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
│
├── agents/             # AI Agents implementation
│   ├── __init__.py    # Agents package initialization
│   ├── credentials_agent.py    # Handles user authentication and credentials
│   ├── form_filler_agent.py    # Automates job application form filling
│   ├── general_agent.py        # Base agent class and common functionality
│   ├── linkedin_agent.py       # LinkedIn-specific automation and interactions
│   ├── tracker_agent.py        # Tracks job application status and progress
│   └── user_profile_agent.py   # Manages user profile data and preferences
│
├── config/             # Configuration management
│   ├── __init__.py    # Configuration package initialization
│   └── settings.py    # Global application settings and constants
│
├── models/            # Data models
│   ├── __init__.py   # Models package initialization
│   ├── application_models.py  # Job application data structures
│   ├── cv_models.py          # Resume/CV data structures
│   ├── job_models.py         # Job posting data structures
│   └── user_models.py        # User profile data structures
│
├── orchestrator/       # Job workflow orchestration
│   ├── __init__.py    # Orchestrator package initialization
│   ├── controller.py  # Main workflow control and coordination
│   └── task_manager.py # Task scheduling and management
│
├── storage/           # Data storage and logging
│   ├── __init__.py   # Storage package initialization
│   ├── csv_storage.py # CSV-based data persistence
│   └── logs_manager.py # Application logging and monitoring
│
├── tests/            # Test suite
│   ├── __init__.py  # Tests package initialization
│   ├── fixtures/    # Test data and mock objects
│   ├── integration/ # End-to-end and integration tests
│   └── unit/       # Unit tests for individual components
│
└── ui/              # User interface components
    ├── __init__.py  # UI package initialization
    ├── cli.py      # Command-line interface implementation
    └── extension/  # Browser extension related files
