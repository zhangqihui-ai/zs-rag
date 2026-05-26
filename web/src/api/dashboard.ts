import { http } from '../lib/http'

export interface DashboardKnowledgeStats {
  total: number
  active: number
  vector: number
  graph: number
  document_total: number
  indexed_document_total: number
  chunk_total: number
  storage_bytes: number
}

export interface DashboardRetrievalStats {
  ready_knowledge_base_total: number
  indexed_document_total: number
  chunk_total: number
}

export interface DashboardChatStats {
  conversation_total: number
  session_total: number
  message_total: number
}

export interface DashboardModelStats {
  provider_total: number
  model_total: number
  enabled_model_total: number
  llm_total: number
  embedding_total: number
}

export interface DashboardUserStats {
  member_total: number
}

export interface DashboardOverview {
  space_id: number
  space_name: string
  knowledge: DashboardKnowledgeStats
  retrieval: DashboardRetrievalStats
  chat: DashboardChatStats
  models: DashboardModelStats
  users: DashboardUserStats
}

export async function getDashboardOverview() {
  return http.get<DashboardOverview>('/enterprise-spaces/dashboard')
}
