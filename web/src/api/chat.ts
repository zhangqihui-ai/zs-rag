import { http } from '../lib/http'

export type RagMode = 'classic' | 'agentic'

export interface AgentTraceEvent {
  step: string
  elapsed_ms?: number | null
  decision?: string | null
  reason?: string | null
  query?: string | null
  total?: number | null
  iteration?: number | null
  relevant_count?: number | null
  from?: string | null
  to?: string | null
  citation_count?: number | null
  answer_chars?: number | null
  confidence?: string | null
  route_pass?: number | null
  pre_retrieve_total?: number | null
  kb_context_chars?: number | null
}

/** 对话（1 个 chat 下多个 session） */
export interface ChatConversation {
  id: string
  user_id: number
  enterprise_space_id: number
  title: string
  created_at: string
  updated_at: string
  model_id?: number | null
  model_provider?: string | null
  model_name?: string | null
  knowledge_base_ids?: number[]
  show_citations?: boolean
  retrieval_top_k?: number
  lightrag_query_mode?: 'naive' | 'local' | 'global' | 'hybrid' | 'mix'
  lightrag_chunk_top_k?: number | null
  temperature?: number
  max_tokens?: number
  top_p?: number
  temperature_enabled?: boolean
  max_tokens_enabled?: boolean
  top_p_enabled?: boolean
  system_prompt?: string | null
  max_history_messages?: number
  max_history_tokens?: number | null
  refine_multiturn?: boolean
  opening_greeting?: string | null
  empty_response?: string | null
  suggest_next_questions_enabled?: boolean
  suggest_next_questions_model_id?: number | null
  suggest_next_questions_prompt_mode?: 'system' | 'custom'
  suggest_next_questions_custom_prompt?: string | null
  rag_mode?: RagMode
  agentic_max_iterations?: number
  agentic_min_relevant_docs?: number
}

export interface ChatSession {
  id: string
  chat_id: string
  user_id: number
  enterprise_space_id: number
  title: string
  created_at: string
  updated_at: string
}

export interface ChatConfiguration {
  id: string
  chat_id: string
  model_id?: number | null
  model_provider?: string
  model_name?: string
  knowledge_base_ids: number[]
  show_citations?: boolean
  /** 与知识检索多库一致：合并后 Top K；各库内先放大候选再全局排序 */
  retrieval_top_k?: number
  lightrag_query_mode?: 'naive' | 'local' | 'global' | 'hybrid' | 'mix'
  lightrag_chunk_top_k?: number | null
  temperature: number
  max_tokens: number
  top_p: number
  temperature_enabled?: boolean
  max_tokens_enabled?: boolean
  top_p_enabled?: boolean
  system_prompt?: string | null
  max_history_messages?: number
  max_history_tokens?: number | null
  refine_multiturn?: boolean
  opening_greeting?: string | null
  empty_response?: string | null
  suggest_next_questions_enabled?: boolean
  suggest_next_questions_model_id?: number | null
  suggest_next_questions_prompt_mode?: 'system' | 'custom'
  suggest_next_questions_custom_prompt?: string | null
  rag_mode?: RagMode
  agentic_max_iterations?: number
  agentic_min_relevant_docs?: number
}

/** 助手消息保存的知识库引文（与正文中的 [1]、[2] 角标对应） */
export interface ChatCitation {
  ref: number
  document_name: string
  page_no: number | null
  knowledge_base_id?: number
  chunk_id?: number | string
  document_id?: number
  chunk_index?: number
  score?: number
  /** 检索来源：graph=图谱检索(LightRAG)，vector=向量/经典检索 */
  source?: 'graph' | 'vector' | string
  /** 图谱库引用随附的切片正文（其 chunk_id 为 LightRAG 内部 ID，无法 getChunk） */
  content?: string | null
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'system' | 'user' | 'assistant'
  content: string
  created_at: string
  citations?: ChatCitation[]
  agent_trace?: AgentTraceEvent[]
}

/** 对话（chat）CRUD 与下辖会话列表：/api/v1/chats */
export const chatResourceApi = {
  list(skip = 0, limit = 100) {
    return http.get<ChatConversation[]>('/api/v1/chats', { params: { skip, limit } })
  },
  create(title: string, configuration?: Partial<ChatConfiguration>) {
    const body: { title: string; configuration?: Partial<ChatConfiguration> } = { title }
    if (configuration != null && Object.keys(configuration).length > 0) {
      body.configuration = configuration
    }
    return http.post<ChatConversation>('/api/v1/chats', body)
  },
  get(chatId: string) {
    return http.get<ChatConversation>(`/api/v1/chats/${chatId}`)
  },
  update(chatId: string, title: string) {
    return http.put<ChatConversation>(`/api/v1/chats/${chatId}`, { title })
  },
  delete(chatId: string) {
    return http.delete(`/api/v1/chats/${chatId}`)
  },
  listSessions(chatId: string) {
    return http.get<ChatSession[]>(`/api/v1/chats/${chatId}/sessions`)
  },
  createSession(chatId: string, title: string) {
    return http.post<ChatSession>(`/api/v1/chats/${chatId}/sessions`, { title })
  },
}

/** @deprecated 使用 chatResourceApi */
export const conversationApi = chatResourceApi

/** 会话级：/api/v1/chats/sessions/{session_id}/... */
export const chatApi = {
  getSession(sessionId: string) {
    return http.get<ChatSession>(`/api/v1/chats/sessions/${sessionId}`)
  },
  updateSession(sessionId: string, title: string) {
    return http.put<ChatSession>(`/api/v1/chats/sessions/${sessionId}`, { title })
  },
  deleteSession(sessionId: string) {
    return http.delete(`/api/v1/chats/sessions/${sessionId}`)
  },

  getConfiguration(sessionId: string) {
    return http.get<ChatConfiguration>(`/api/v1/chats/sessions/${sessionId}/config`)
  },
  updateConfiguration(sessionId: string, configuration: Partial<ChatConfiguration>) {
    return http.put<ChatConfiguration>(`/api/v1/chats/sessions/${sessionId}/config`, configuration)
  },

  getMessages(sessionId: string, skip = 0, limit = 100) {
    return http.get<ChatMessage[]>(`/api/v1/chats/sessions/${sessionId}/messages`, {
      params: { skip, limit },
    })
  },

  streamPath(sessionId: string) {
    return `/api/v1/chats/sessions/${sessionId}/stream`
  },
}

/** 嵌入对话用 API Key（Bearer）；可按 conversation_id 绑定对话 */
export interface ChatEmbedApiKeyMeta {
  id: number
  key_prefix: string
  created_at: string
  conversation_id?: string | null
}

export interface ChatEmbedApiKeyCreateResponse {
  created: boolean
  api_key?: string | null
  keys: ChatEmbedApiKeyMeta[]
  message?: string | null
}

export interface ChatEmbedApiKeyEnsurePayload {
  regenerate?: boolean
  conversation_id?: string | null
  issue_new_for_share?: boolean
}

export const chatEmbedApiKeyApi = {
  ensureOrCreate(payload: ChatEmbedApiKeyEnsurePayload = {}) {
    return http.post<ChatEmbedApiKeyCreateResponse>('/api/v1/chats/embed-api-keys', payload)
  },
  list() {
    return http.get<ChatEmbedApiKeyMeta[]>('/api/v1/chats/embed-api-keys')
  },
  revoke(keyId: number) {
    return http.delete(`/api/v1/chats/embed-api-keys/${keyId}`)
  },
}
