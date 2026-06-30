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
  agentic_conversation_total: number
  classic_conversation_total: number
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

export interface DashboardKbUsageItem {
  kb_id: number
  kb_name: string
  conversation_bind_count: number
  recall_count: number
}

export interface DashboardFileExtItem {
  file_ext: string
  count: number
}

export interface DashboardKnowledgeUsageStats {
  top_knowledge_bases: DashboardKbUsageItem[]
  file_ext_distribution: DashboardFileExtItem[]
}

export interface DashboardDocumentPipelineStats {
  parsing: number
  indexed: number
  failed: number
}

export interface DashboardAuditItem {
  id: number
  action: string
  resource_type: string
  resource_id: string | null
  username: string | null
  message: string | null
  created_at: string
}

export interface DashboardOverview {
  space_id: number
  space_name: string
  knowledge: DashboardKnowledgeStats
  retrieval: DashboardRetrievalStats
  chat: DashboardChatStats
  models: DashboardModelStats
  users: DashboardUserStats
  knowledge_usage: DashboardKnowledgeUsageStats
  document_pipeline: DashboardDocumentPipelineStats
  recent_audit: DashboardAuditItem[]
}

export type DashboardUsageRange = '24h' | '7d' | '30d'
export type DashboardUsageMetric = 'model_calls' | 'tokens' | 'chat_api'

export interface DashboardUsagePoint {
  t: string
  v: number
}

export interface DashboardUsageSeries {
  key: string
  label: string
  points: DashboardUsagePoint[]
}

export interface DashboardUsage {
  space_id: number
  space_name: string
  range: DashboardUsageRange
  metric: DashboardUsageMetric
  series: DashboardUsageSeries[]
  total: number
}

export async function getDashboardOverview() {
  return http.get<DashboardOverview>('/enterprise-spaces/dashboard')
}

export async function getDashboardUsage(params: { range: DashboardUsageRange; metric: DashboardUsageMetric }) {
  return http.get<DashboardUsage>('/enterprise-spaces/dashboard/usage', { params })
}

export interface DashboardChatTopItem {
  conversation_id: string
  title: string
  session_count: number
  message_count: number
}

export interface DashboardChatTop {
  space_id: number
  space_name: string
  range: DashboardUsageRange
  items: DashboardChatTopItem[]
}

export async function getDashboardChatTop(params: { range: DashboardUsageRange }) {
  return http.get<DashboardChatTop>('/enterprise-spaces/dashboard/chat-top', { params })
}
