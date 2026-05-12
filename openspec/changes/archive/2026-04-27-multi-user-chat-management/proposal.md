## Why

The current dialogue functionality lacks multi-user state isolation, configuration options, and a robust management interface. To make the platform a fully-featured RAG system, users need to create and manage their own chats, configure models and parameters, and connect to specific knowledge bases, all while maintaining isolation within their enterprise space.

## What Changes

- Add a new 3-column layout for the chat page (Session List, Chat Area, Configuration Panel).
- Introduce multi-user chat sessions, isolated by user but visible within the enterprise space.
- Add real-time configuration options per chat (Knowledge Base selection, Model selection, parameters like temperature, max_tokens, top-p).
- Expose RESTful APIs and WebSocket endpoints for chat interaction.
- Provide embeddable code generation for third-party integration.

## Capabilities

### New Capabilities
- `multi-user-chat`: Ability for users to create and manage multiple chat sessions within their enterprise space.
- `chat-configuration`: Granular control over chat settings (models, parameters, knowledge bases).
- `chat-integration-api`: REST and WebSocket APIs for chat, along with embeddable UI options.

### Modified Capabilities


## Impact

- **Database**: New tables for `ChatSession`, `ChatMessage`, and `ChatConfiguration`.
- **Backend**: New API routes for chat management, WebSocket handlers for real-time messaging.
- **Frontend**: Major refactor of the Chat view to support the 3-column layout and state management for active sessions and configurations.