import axios from 'axios'

import { http, longRequestTimeoutMs } from '../lib/http'
import { getKnowledgeBaseErrorMessage } from './knowledge-base'

export interface GraphStats {
  node_total: number
  edge_total: number
}

export interface GraphSubgraphStats {
  node_shown: number
  edge_shown: number
  node_total: number
  edge_total: number
}

export interface GraphSubgraphNode {
  id: string
  label: string
  entity_type: string | null
  degree?: number
  properties?: Record<string, unknown>
}

/** @deprecated 使用 GraphSubgraphNode */
export type GraphNodeItem = GraphSubgraphNode

export interface GraphSubgraphEdge {
  source: string
  target: string
  label?: string | null
  properties?: Record<string, unknown>
}

/** @deprecated 使用 GraphSubgraphEdge */
export type GraphEdgeItem = GraphSubgraphEdge

export interface GraphSubgraphResponse {
  nodes: GraphSubgraphNode[]
  edges: GraphSubgraphEdge[]
  stats: GraphSubgraphStats
}

export interface GraphNodeDetail {
  id: string
  /** 展示名称（后端可能返回 label 或 name） */
  label?: string
  name?: string
  entity_type: string | null
  degree?: number
  description: string | null
  file_path: string | null
  source_id: string | null
  created_at: string | null
  tag?: string | null
  tags?: string[] | null
  properties?: Record<string, unknown>
  document_id?: number | null
}

export interface GraphSubgraphParams {
  label?: string
  limit?: number
  depth?: number
}

interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
}

const isEnvelope = <T>(value: unknown): value is ApiEnvelope<T> => {
  return Boolean(value) && typeof value === 'object' && 'code' in (value as Record<string, unknown>) && 'data' in (value as Record<string, unknown>)
}

const unwrap = async <T>(request: Promise<{ data: T | ApiEnvelope<T> }>): Promise<T> => {
  const response = await request
  return isEnvelope<T>(response.data) ? response.data.data : (response.data as T)
}

export const getGraphErrorMessage = (error: unknown, fallback = '图谱操作失败') =>
  getKnowledgeBaseErrorMessage(error, fallback)

export type LightRagQueryMode = 'naive' | 'local' | 'global' | 'hybrid' | 'mix'

export interface GraphSearchRequest {
  query: string
  mode?: LightRagQueryMode
  top_k?: number
  include_references?: boolean
}

export interface GraphSearchCitation {
  ref: number
  document_name: string
  document_id?: number | null
  file_path?: string | null
  chunk_id?: string | null
  knowledge_base_id: number
}

export interface GraphSearchResponse {
  query: string
  mode: string
  answer_context: string
  chunks: Record<string, unknown>[]
  entities: Record<string, unknown>[]
  relationships: Record<string, unknown>[]
  citations: GraphSearchCitation[]
  metadata?: Record<string, unknown> | null
}

export function graphSearch(kbId: number, payload: GraphSearchRequest) {
  return unwrap<GraphSearchResponse>(
    http.post(`/knowledge-bases/${kbId}/graph-search`, payload, { timeout: longRequestTimeoutMs }),
  )
}

export function getGraphStats(kbId: number) {
  return unwrap<GraphStats>(
    http.get(`/knowledge-bases/${kbId}/graph/stats`, { timeout: longRequestTimeoutMs }),
  )
}

export function getGraphSubgraph(kbId: number, params: GraphSubgraphParams = {}) {
  return unwrap<GraphSubgraphResponse>(
    http.get(`/knowledge-bases/${kbId}/graph/subgraph`, { params, timeout: longRequestTimeoutMs }),
  )
}

export function getGraphNode(kbId: number, entityId: string) {
  return unwrap<GraphNodeDetail>(http.get(`/knowledge-bases/${kbId}/graph/nodes/${encodeURIComponent(entityId)}`))
}

export async function exportGraph(kbId: number, params: GraphSubgraphParams = {}): Promise<Blob> {
  try {
    const { data } = await http.get(`/knowledge-bases/${kbId}/graph/export`, {
      params,
      responseType: 'blob',
    })
    if (data instanceof Blob) {
      return data
    }
  } catch (error) {
    if (!axios.isAxiosError(error)) {
      throw error
    }
  }
  const payload = await getGraphSubgraph(kbId, params)
  return new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
}

export const graphKnowledgeBaseApi = {
  stats: getGraphStats,
  subgraph: getGraphSubgraph,
  nodeDetail: getGraphNode,
  exportJson: exportGraph,
}

export function graphNodeDisplayName(detail: GraphNodeDetail): string {
  return (detail.name || detail.label || detail.id).trim() || detail.id
}
