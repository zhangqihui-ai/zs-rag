## ADDED Requirements

### Requirement: Per-Session Chat Configuration
The system SHALL allow users to define and store a configuration specific to each chat session, including `knowledge_base_ids`, `model_provider`, `model_name`, `temperature`, `max_tokens`, and `top_p`.

#### Scenario: Real-time Configuration Save
- **WHEN** a user adjusts the temperature slider in the right-side configuration panel
- **THEN** the frontend automatically triggers a save to the backend for the current session configuration.

#### Scenario: Selecting Knowledge Bases
- **WHEN** a user selects one or more knowledge bases in the configuration panel
- **THEN** the subsequent chat queries for this session MUST use these selected knowledge bases as the RAG context.

#### Scenario: Changing Models
- **WHEN** a user selects a different model (e.g., switches from DeepSeek to Kimi)
- **THEN** the system MUST use the newly selected model for the next prompt in this session.