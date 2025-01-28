# Application Architecture

## Agent Interaction Flow

```mermaid
flowchart LR

    %% Top-level
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