## 1. Backend Core & Database

- [x] 1.1 Update SQLAlchemy models to include `ChatSession`, `ChatConfiguration`, and `ChatMessage`
- [x] 1.2 Generate and apply Alembic migrations for new chat tables
- [x] 1.3 Create CRUD services for chat sessions ensuring `enterprise_space` and `user_id` filtering
- [x] 1.4 Create CRUD services for chat configurations linked to sessions

## 2. Backend API & WebSockets

- [x] 2.1 Implement RESTful router endpoints for `/api/v1/chats` (Create, List, Delete, Rename)
- [x] 2.2 Implement RESTful router endpoints for `/api/v1/chats/{id}/config` (Get, Update)
- [x] 2.3 Implement WebSocket handler at `/ws/v1/chats/{id}` for real-time messaging and LLM streaming
- [x] 2.4 Integrate selected model provider and knowledge base context into the WebSocket LLM chain

## 3. Frontend State & Services

- [x] 3.1 Create frontend API service functions for chat REST endpoints
- [x] 3.2 Create `useChatStore` in Pinia to manage active session, session list, and configurations
- [x] 3.3 Implement WebSocket client utility for handling real-time token streaming and reconnections

## 4. Frontend UI Layout & Components

- [x] 4.1 Refactor Chat view to a 3-column layout (Left Sidebar, Middle Chat, Right Config)
- [x] 4.2 Implement Left Sidebar component: Session list, New Chat button, rename/delete actions
- [x] 4.3 Implement Right Config component: Model selector, Knowledge Base selector, parameter sliders (temp, max_tokens, etc.)
- [x] 4.4 Implement Middle Chat component: Message history display, input area, auto-scroll logic
- [x] 4.5 Connect UI components to `useChatStore` and API services

## 5. Integration & Polish

- [x] 5.1 Ensure real-time saving of configuration changes works seamlessly
- [x] 5.2 Test WebSocket streaming with a real LLM backend and RAG context
- [x] 5.3 Write unit tests for new backend API endpoints
- [x] 5.4 Document the RESTful API and WebSocket connection details for third-party integration
