## Context

The current chat interface needs to be refactored to support a multi-user environment where each user can create and manage their own isolated chat sessions within the overarching context of an "enterprise space." Furthermore, the chat interface needs robust configuration options (models, parameters, knowledge bases) available in real-time during a session. A 3-column layout is required to accommodate session management, the chat itself, and configuration settings cleanly.

## Goals / Non-Goals

**Goals:**
- Implement a 3-column UI layout (Session List, Chat Area, Config Panel).
- Allow users to create, delete, and rename their own chat sessions.
- Isolate chat state per session.
- Enable dynamic configuration of chat parameters (knowledge base, model, temp, max_tokens, etc.) that save and apply in real-time.
- Expose RESTful and WebSocket APIs for chatting and management.
- Ensure all data is strictly isolated by `enterprise_space`.

**Non-Goals:**
- Complex multi-agent orchestration within a single chat session.
- Cross-enterprise space chat sharing.

## Decisions

- **UI Layout**: Use a CSS Grid or Flexbox-based 3-column layout. The left column (Session List) and right column (Config Panel) will be collapsible to maximize the central chat area when needed.
- **Database Schema**: 
  - `ChatSession`: `id`, `user_id`, `enterprise_space`, `title`, `created_at`, `updated_at`.
  - `ChatConfiguration`: `id`, `session_id`, `model_provider`, `model_name`, `knowledge_base_ids` (JSON/Array), `temperature`, `max_tokens`, `top_p`.
  - `ChatMessage`: `id`, `session_id`, `role` (user/assistant/system), `content`, `created_at`.
- **API Design**: 
  - REST endpoints for CRUD on sessions and configurations (`/api/v1/chats`, `/api/v1/chats/{id}/config`).
  - WebSocket endpoint (`/ws/v1/chats/{id}`) for real-time streaming of LLM responses to provide a smooth UX.
- **State Management (Frontend)**: Pinia stores for `useChatStore` to manage active session, message history, and active configuration. This ensures that switching sessions updates the entire view seamlessly.

## Risks / Trade-offs

- **Risk**: WebSocket connections may drop or scale poorly under high load.
  - **Mitigation**: Implement robust reconnection logic on the frontend and consider using Redis pub/sub if scaling the backend across multiple workers in the future (though for V0, in-memory or standard ASGI WebSockets are sufficient).
- **Risk**: Large message histories loading slowly.
  - **Mitigation**: Implement pagination/cursor-based loading for messages within a session.