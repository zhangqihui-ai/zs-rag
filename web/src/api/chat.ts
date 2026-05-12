import { http } from '../lib/http'

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
  /** 与知识检索多库一致：合并后 Top K；各库内先放大候选再全局排序 */
  retrieval_top_k?: number
  temperature?: number
  max_tokens?: number
  top_p?: number
  system_prompt?: string | null
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
  temperature: number
  max_tokens: number
  top_p: number
  system_prompt?: string | null
}

/** 助手消息保存的知识库引文（与正文中的 [1]、[2] 角标对应） */
export interface ChatCitation {
  ref: number
  document_name: string
  page_no: number | null
  knowledge_base_id?: number
  chunk_id?: number
  document_id?: number
  chunk_index?: number
  score?: number
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'system' | 'user' | 'assistant'
  content: string
  created_at: string
  citations?: ChatCitation[]
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
