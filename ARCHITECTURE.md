# Application Architecture

## Agent Interaction Flow

```mermaid
flowchart LR

    %% Top-level - Testing sync workflow
    %% Added this comment to trigger sync
    Controller(( Controller ))
    TaskManager(( TaskManager ))

    %% Agents
    LinkedInAgent[(LinkedInAgent)]
    AINavigator[(AI Navigator)]
    CredentialsAgent[(CredentialsAgent)]
    FormFillerAgent[(FormFillerAgent)]
    CVParserAgent[(CVParserAgent)]
    GeneralAgent[(GeneralAgent)]
    TrackerAgent[(TrackerAgent)]
    UserProfileAgent[(UserProfileAgent)]

    %% Controller coordinates everything
    Controller -- Schedules Tasks --> TaskManager
    Controller -- "Use domain logic" --> LinkedInAgent
    Controller -- "Call sub-agents on demand" --> CredentialsAgent
    Controller -- "Log steps" --> TrackerAgent

    %% TaskManager can call tasks that eventually go to LinkedInAgent or other agents
    TaskManager -- "Async tasks" --> LinkedInAgent
    TaskManager -- "Async tasks" --> CredentialsAgent
    TaskManager -- "Async tasks" --> FormFillerAgent

    %% LinkedInAgent can call sub-agents
    LinkedInAgent -- "Handle login/captcha" --> CredentialsAgent
    LinkedInAgent -- "Form filling" --> FormFillerAgent
    LinkedInAgent -- "Parse CV if needed" --> CVParserAgent
    LinkedInAgent -- "Generic DOM steps" --> GeneralAgent
    LinkedInAgent -- "Confidence-based nav?" --> AINavigator

    %% Logging is usually done by everyone -> TrackerAgent
    LinkedInAgent -- "Log outcomes" --> TrackerAgent
    CredentialsAgent -- "Log captcha events" --> TrackerAgent
    FormFillerAgent -- "Log fill steps" --> TrackerAgent

    %% UserProfileAgent is mostly a data store
    Controller -- "Manage user preferences" --> UserProfileAgent
    LinkedInAgent -- "Read user preferences" --> UserProfileAgent
```

## Sequence Flow Example

```mermaid
sequenceDiagram
    autonumber
    participant UI as User/CLI
    participant C as Controller
    participant T as TaskManager
    participant LA as LinkedInAgent
    participant CA as CredentialsAgent
    participant FF as FormFillerAgent
    participant TK as TrackerAgent

    UI->>C: "Run LinkedIn Flow (job_title, location)"
    note over C: Possibly read user_profile info or <br> do an AI Master-Plan
    C->>T: create/run task (search_jobs_and_apply)
    T->>LA: search_jobs_and_apply(job_title, location)

    LA->>TK: log "Starting job search"
    LA->>CA: (if captcha or login needed) handle_captcha/login
    CA->>TK: log "captcha solved / login complete"
    LA->>FF: fill forms for "Easy Apply"
    FF->>TK: log "Form fields filled"
    LA->>TK: log "Job applied or skipped"
    T->>C: job_search_and_apply done
    C->>TK: log_activity "Flow success"
    note over C: Then more flows or end_session
```

## Entry Points and User Interaction Flow

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant Main as main.py
    participant Mode as Mode Selector
    participant Auto as Automatic Mode
    participant CLI as Full Control Mode
    participant GUI as GUI Mode
    participant C as Controller
    participant B as Browser Setup

    User->>Main: Start Application
    Main->>B: Initialize Browser
    B-->>Main: Browser & Page Ready

    Main->>Mode: Display Mode Selection
    note over Mode: 1) Automatic Mode<br/>2) Full Control Mode<br/>3) GUI Mode<br/>4) Exit

    alt Automatic Mode
        Mode->>Auto: run_automatic_mode()
        Auto->>C: run_linkedin_flow(job_title, location)
        C-->>Auto: Flow Complete
        Auto-->>Mode: Return to Mode Selection
    else Full Control Mode
        Mode->>CLI: run_full_control_mode()
        note over CLI: Interactive CLI session<br/>User types commands
        CLI->>C: Various Controller Commands
        C-->>CLI: Command Results
        CLI-->>Mode: Return to Mode Selection
    else GUI Mode
        Mode->>GUI: run_gui_mode()
        note over GUI: MinimalGUI window<br/>Start/Resume/Pause/Stop
        GUI->>C: Controller Actions
        C-->>GUI: Action Results
        GUI-->>Mode: Return to Mode Selection
    else Exit
        Mode->>Main: Cleanup and Exit
    end

    Main->>C: end_session()
    Main->>B: Cleanup Browser
```

## Architecture Notes

### Key Components

1. **Controller**: Central orchestrator that manages the overall flow
2. **TaskManager**: Handles async task scheduling and execution
3. **Agents**: Specialized components for specific tasks
   - LinkedInAgent: LinkedIn-specific automation
   - AINavigator: Confidence-based navigation
   - CredentialsAgent: Authentication and CAPTCHA handling
   - FormFillerAgent: Form automation
   - CVParserAgent: Resume parsing
   - GeneralAgent: Common functionality
   - TrackerAgent: Logging and monitoring
   - UserProfileAgent: User data management

### Flow Description

1. The Controller initiates all major operations
2. TaskManager handles async execution of tasks
3. LinkedInAgent coordinates most LinkedIn-specific operations
4. Other agents provide specialized functionality
5. All significant events are logged via TrackerAgent

### Design Principles

1. Separation of concerns
2. Async-first architecture
3. Centralized logging
4. Modular agent system
5. Fallback mechanisms 