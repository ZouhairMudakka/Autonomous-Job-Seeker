# AI Browser Job Workflow

An intelligent multi-agent system that automates professional job search and application processes on LinkedIn while maintaining compliance with platform terms of service.

## Overview
This system uses multiple specialized AI agents to:
- Search and analyze job postings
- Match job requirements with user qualifications
- Automate application form filling
- Track application status and interactions
- Handle authentication and security
- Manage rate limits and platform compliance

## Project Structure

### AI Agents (`agents/`)
- `credentials_agent.py`: CAPTCHA handling and authentication management
  - 2captcha integration
  - Manual CAPTCHA fallback
  - Future login flow support
- `form_filler_agent.py`: Intelligent form completion
- `general_agent.py`: Common browser automation functions
- `linkedin_agent.py`: LinkedIn-specific operations
- `tracker_agent.py`: Application status tracking
- `cv_parser_agent.py`: (Planned) Resume parsing and data extraction
- `user_profile_agent.py`: (Planned) User data management

### Core Components
- `utils/`: (Planned) Shared utilities
  - Random delays
  - Date formatting
  - String operations
  - Custom exceptions
- `orchestrator/`: Workflow management
  - `controller.py`: Main workflow orchestration
  - `task_manager.py`: Task queuing and execution
- `storage/`: Data persistence
  - `csv_storage.py`: CSV data management
  - `logs_manager.py`: Logging functionality
  - `database_manager.py`: (Planned) Structured data storage
  - `json_storage.py`: (Planned) JSON-based storage

### Workflow Management (`orchestrator/`)
- `controller.py`: Main workflow orchestration
- `task_manager.py`: Task queuing and execution management

### Data Management (`storage/`)
- `csv_storage.py`: Application data and results management
- `logs_manager.py`: Activity logging and analytics

### User Interface (`ui/`)
- `cli.py`: Command-line interface
- `extension/`: Browser extension for real-time control and monitoring

### Configuration (`config/`)
- `settings.py`: System configuration and parameters

## Features

### Core Functionality
- Job Search Automation
  - Customizable search criteria
  - Keyword and skill matching
  - Location-based filtering
  - Seniority level targeting
  - Industry and company type filtering

- Application Processing
  - Resume and cover letter customization
  - Form auto-completion
  - Document upload handling
  - Follow-up tracking
  - Application status monitoring

- Profile Optimization
  - Keyword optimization
  - Skills matching
  - Experience highlighting
  - Profile visibility management

### Advanced Features
- AI-Powered Analysis
  - Job requirement analysis
  - Qualification matching
  - Success probability scoring
  - Automated customization suggestions

- Application Management
  - Status tracking dashboard
  - Application history
  - Interview scheduling
  - Follow-up reminders
  - Analytics and insights

### Security & Compliance
- Secure credential storage
- Rate limiting and throttling
- Platform compliance monitoring
- Error recovery and resilience
- CAPTCHA detection and handling

### User Interfaces
- Command-line interface (CLI)
- Browser extension dashboard
- Real-time monitoring
- Application analytics

## Requirements

### Core Dependencies
- Python 3.8+
- Selenium 4.11.2
- Playwright 1.49.0
- pandas 2.1.0
- python-dotenv 1.0.0
- Pillow 10.0.0 (CAPTCHA processing)
- pydantic 2.10.4 (Data validation)
- LangChain 0.3.14+ (AI integration)
- requests 2.31.0
- beautifulsoup4 4.12.2
- linkedin-api 2.0.0
- pytest 7.4.0
- logging 0.4.9.6
- httpx 0.27.2+
- posthog 3.7.0+

### Optional Dependencies
- tokencost (Token tracking)
- hatch (Build tool)
- pytest-asyncio (Async testing)

## MVP Status
Current implementation focuses on:
- CAPTCHA handling (2captcha + manual fallback)
- Basic browser automation
- LinkedIn job search
- Form filling assistance

Planned extensions:
- Automated CV parsing
- User profile management
- Enhanced data storage
- Unified utilities
- Platform-specific login flows

## Setup
1. Clone the repository
2. Install dependencies: 
   ```bash
   pip install -r requirements.txt
   pip install "pydantic[email]"    # Required for email validation
   playwright install               # Install browser binaries
   ```
3. Copy `.env.example` to `.env` and configure:
   - TWO_CAPTCHA_API_KEY (optional)
   - LinkedIn credentials (for future automated login)
   - Other platform settings
4. Run the application: `python main.py`

## Usage
1. Start the application using the CLI:
   ```bash
   python main.py
   ```
2. Use the following CLI commands:
   - `start`: Begin job search and application workflow
   - `stop`: Pause all operations
   - `status`: Check current progress and statistics
   - `config`: Update search and application preferences
   - `export`: Export application history and analytics
   - `quit`: Exit the application

3. Browser Extension:
   - Install the extension from the `ui/extension` directory
   - Monitor job search progress
   - Review application statuses
   - Adjust search parameters
   - View analytics and insights

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

### License Verification
To verify the integrity of the LICENSE file:
1. The LICENSE file should be exactly 11,357 bytes in size
2. It should contain the complete Apache License 2.0 text
3. The copyright notice should read:
   ```
   Copyright [2025] Mudakka Consulting FZ-LLC
   ```
4. You can verify the license text matches the official Apache License 2.0 by comparing with:
   https://www.apache.org/licenses/LICENSE-2.0.txt 