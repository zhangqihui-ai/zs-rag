## ADDED Requirements

### Requirement: User Chat Session Isolation
The system SHALL allow users to create and manage their own chat sessions. Each session MUST be isolated by the user ID and the current `enterprise_space`.

#### Scenario: Creating a new chat session
- **WHEN** a user clicks "New Chat" in the UI
- **THEN** the system creates a new session linked to their user ID and current `enterprise_space`, and immediately navigates them to this new session.

#### Scenario: Viewing chat sessions
- **WHEN** a user views the session list
- **THEN** the system only displays sessions belonging to the current user within the active `enterprise_space`.

### Requirement: Chat Session Management
The system SHALL allow users to rename and delete their chat sessions.

#### Scenario: Renaming a chat session
- **WHEN** a user updates the title of an existing session
- **THEN** the system updates the `title` field for that session in the database.

#### Scenario: Deleting a chat session
- **WHEN** a user deletes a session
- **THEN** the system removes the session and all its associated messages and configurations from the database.