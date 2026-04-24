import axios from 'axios'

import { http, longRequestTimeoutMs } from '../lib/http'

export type RetrievalMode = 'vector' | 'keyword' | 'hybrid'

export interface KnowledgeBase {
  id: number
  enterprise_space_id: number
  name: string
  description: string | null
  status: 'active' | 'inactive' | 'deleted'
  vector_db_enabled: boolean
  graph_db_enabled: boolean
  embedding_model_id: number | null
  default_chunk_size: number
  default_chunk_overlap: number
  default_retrieval_mode: RetrievalMode
  default_top_k: number
  default_score_threshold: number | null
  config: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface KnowledgeBasePayload {
  name: string
  description?: string | null
  vector_db_enabled: boolean
  graph_db_enabled: boolean
  embedding_model_id?: number | null
  default_chunk_size: number
  default_chunk_overlap: number
  default_retrieval_mode: RetrievalMode
  default_top_k: number
  default_score_threshold?: number | null
  config?: Record<string, unknown> | null
}

export interface ParentChildPreviewChildItem {
  chunk_index: number
  content: string
  char_count: number
}

export interface ParentChildPreviewGroupItem {
  parent_index: number
  parent_preview: string
  parent_char_count: number
  children: ParentChildPreviewChildItem[]
}

export interface KnowledgeDocumentChunkingPreviewResponse {
  document_id: number
  file_name: string
  mode: string
  excerpt: string
  chunks: string[]
  total_chunks: number
  preview_chunk_count: number
  excerpt_truncated: boolean
  parent_child_groups?: ParentChildPreviewGroupItem[] | null
}

export interface KnowledgeBaseStats {
  knowledge_base_id: number
  document_total: number
  indexed_document_total: number
  chunk_total: number
  failed_document_total: number
}

export interface Neo4jConnection {
  id: number
  knowledge_base_id: number
  uri: string
  username: string
  database: string | null
  is_active: boolean
  config: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface Neo4jConnectionPayload {
  uri: string
  username: string
  password?: string | null
  database?: string | null
  config?: Record<string, unknown> | null
}

export interface ConnectionTestResult {
  success: boolean
  message: string
  response_time_ms?: number | null
}

export interface KnowledgeDocument {
  id: number
  enterprise_space_id: number
  knowledge_base_id: number
  source_type: string
  document_name: string
  file_name: string
  file_ext: string | null
  mime_type: string | null
  file_size: number | null
  storage_type: string
  parser_type: string
  chunk_size: number
  chunk_overlap: number
  status: string
  chunk_count: number
  token_count: number | null
  char_count: number | null
  error_message: string | null
  metadata: Record<string, unknown> | null
  /** 文档级分段策略覆盖；为空表示继承知识库默认 */
  chunking_config: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

/** 服务端持久化的解析/重建索引日志 */
export interface KnowledgeDocumentParseLog {
  kind: 'parse' | 'reindex' | null
  phase: 'success' | 'error' | null
  lines: { t: string; text: string }[]
  updated_at: string | null
}

export interface KnowledgeChunk {
  id: number
  chunk_uid: string
  document_id: number
  chunk_index: number
  content: string
  content_preview: string | null
  char_count: number
  token_count: number | null
  start_offset: number | null
  end_offset: number | null
  page_no: number | null
  heading_path: string | null
  vector_status: string
  vector_id: string | null
  metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface KnowledgeSearchRequest {
  query: string
  mode?: RetrievalMode
  top_k?: number
  /** 相似度下限 0~1；低于此值的块被过滤 */
  score_threshold?: number | null
  /** 混合检索：向量分支权重（0~1），全文关键词权重为 1-w；缺省后端 0.5 */
  vector_weight?: number | null
  document_ids?: number[]
}

export interface KnowledgeSearchResult {
  chunk_id: number
  chunk_uid: string
  document_id: number
  document_name: string
  chunk_index: number
  content: string
  score: number
  vector_score: number | null
  keyword_score: number | null
  metadata: Record<string, unknown> | null
  citation: {
    document_name: string
    page_no: number | null
    chunk_index: number
  }
}

export interface KnowledgeSearchResponse {
  query: string
  mode: RetrievalMode
  total: number
  results: KnowledgeSearchResult[]
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

export const getKnowledgeBaseErrorMessage = (error: unknown, fallback = '操作失败') => {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined
    const message = data?.message || data?.detail
    if (typeof message === 'string' && message.trim()) {
      return message
    }
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  return fallback
}

export const knowledgeBaseApi = {
  list() {
    return unwrap<KnowledgeBase[]>(http.get('/knowledge-bases'))
  },
  get(kbId: number) {
    return unwrap<KnowledgeBase>(http.get(`/knowledge-bases/${kbId}`))
  },
  create(payload: KnowledgeBasePayload) {
    return unwrap<KnowledgeBase>(http.post('/knowledge-bases', payload))
  },
  update(kbId: number, payload: Partial<KnowledgeBasePayload & { status: KnowledgeBase['status'] }>) {
    return unwrap<KnowledgeBase>(http.patch(`/knowledge-bases/${kbId}`, payload))
  },
  delete(kbId: number) {
    return unwrap<void>(http.delete(`/knowledge-bases/${kbId}`))
  },
  purge(kbId: number, payload: { confirm_name: string; confirm: boolean }) {
    return unwrap<void>(http.post(`/knowledge-bases/${kbId}/purge`, payload))
  },
  getStats(kbId: number) {
    return unwrap<KnowledgeBaseStats>(http.get(`/knowledge-bases/${kbId}/stats`))
  },
  getNeo4jConnection(kbId: number) {
    return unwrap<Neo4jConnection>(http.get(`/knowledge-bases/${kbId}/neo4j-connection`))
  },
  createNeo4jConnection(kbId: number, payload: Neo4jConnectionPayload) {
    return unwrap<Neo4jConnection>(http.post(`/knowledge-bases/${kbId}/neo4j-connection`, payload))
  },
  updateNeo4jConnection(kbId: number, payload: Partial<Neo4jConnectionPayload> & { is_active?: boolean }) {
    return unwrap<Neo4jConnection>(http.patch(`/knowledge-bases/${kbId}/neo4j-connection`, payload))
  },
  deleteNeo4jConnection(kbId: number) {
    return unwrap<void>(http.delete(`/knowledge-bases/${kbId}/neo4j-connection`))
  },
  testNeo4jConnection(kbId: number) {
    return unwrap<ConnectionTestResult>(http.post(`/knowledge-bases/${kbId}/neo4j-connection/test`))
  },
  listDocuments(kbId: number, params?: { status?: string; keyword?: string; page?: number; page_size?: number }) {
    return unwrap<PaginatedResponse<KnowledgeDocument>>(http.get(`/knowledge-bases/${kbId}/documents`, { params }))
  },
  uploadDocument(
    kbId: number,
    payload: {
      file: File
      chunk_size?: number | null
      chunk_overlap?: number | null
    },
  ) {
    const formData = new FormData()
    formData.append('file', payload.file)
    if (typeof payload.chunk_size === 'number') {
      formData.append('chunk_size', String(payload.chunk_size))
    }
    if (typeof payload.chunk_overlap === 'number') {
      formData.append('chunk_overlap', String(payload.chunk_overlap))
    }
    return unwrap<KnowledgeDocument>(
      http.post(`/knowledge-bases/${kbId}/documents/upload`, formData, { timeout: longRequestTimeoutMs }),
    )
  },
  /** 开始解析、分块与索引（仅待解析/失败状态） */
  parseDocument(kbId: number, documentId: number, embedding_model_id?: number | null) {
    return unwrap<KnowledgeDocument>(
      http.post(`/knowledge-bases/${kbId}/documents/${documentId}/parse`, undefined, {
        params: typeof embedding_model_id === 'number' ? { embedding_model_id } : undefined,
        timeout: longRequestTimeoutMs,
      }),
    )
  },
  getDocument(kbId: number, documentId: number) {
    return unwrap<KnowledgeDocument>(http.get(`/knowledge-bases/${kbId}/documents/${documentId}`))
  },
  updateDocumentChunkingConfig(kbId: number, documentId: number, chunking_config: Record<string, unknown> | null) {
    return unwrap<KnowledgeDocument>(
      http.patch(`/knowledge-bases/${kbId}/documents/${documentId}/chunking-config`, { chunking_config }),
    )
  },
  previewChunking(
    kbId: number,
    payload: {
      document_id: number
      chunking_config: Record<string, unknown>
      max_pages?: number
      max_chars?: number
      max_chunks?: number
    },
  ) {
    return unwrap<KnowledgeDocumentChunkingPreviewResponse>(http.post(`/knowledge-bases/${kbId}/chunking/preview`, payload))
  },
  getDocumentParseLog(kbId: number, documentId: number) {
    return unwrap<KnowledgeDocumentParseLog>(http.get(`/knowledge-bases/${kbId}/documents/${documentId}/parse-log`))
  },
  /** 获取原始文件二进制（需携带 Token，用于新窗口预览） */
  async fetchDocumentFileBlob(kbId: number, documentId: number): Promise<Blob> {
    const { data } = await http.get(`/knowledge-bases/${kbId}/documents/${documentId}/file`, {
      responseType: 'blob',
    })
    return data as Blob
  },
  deleteDocument(kbId: number, documentId: number) {
    return unwrap<void>(http.delete(`/knowledge-bases/${kbId}/documents/${documentId}`))
  },
  reindexDocument(kbId: number, documentId: number, embedding_model_id?: number | null) {
    return unwrap<KnowledgeDocument>(
      http.post(`/knowledge-bases/${kbId}/documents/${documentId}/reindex`, undefined, {
        params: typeof embedding_model_id === 'number' ? { embedding_model_id } : undefined,
        timeout: longRequestTimeoutMs,
      }),
    )
  },
  listChunks(
    kbId: number,
    documentId: number,
    params?: { page?: number; page_size?: number; keyword?: string },
  ) {
    return unwrap<PaginatedResponse<KnowledgeChunk>>(
      http.get(`/knowledge-bases/${kbId}/documents/${documentId}/chunks`, { params }),
    )
  },
  search(kbId: number, payload: KnowledgeSearchRequest) {
    return unwrap<KnowledgeSearchResponse>(http.post(`/knowledge-bases/${kbId}/search`, payload))
  },
}

function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
}

export type DocumentProcessStreamMode = 'parse' | 'reindex'

/**
 * 通过 SSE（text/event-stream）消费解析/重建过程日志，完成后返回文档快照。
 * 需使用 fetch：axios 对流式响应支持不便。
 */
export async function streamDocumentProcess(
  kbId: number,
  documentId: number,
  mode: DocumentProcessStreamMode,
  options: {
    embedding_model_id?: number | null
    onLog: (line: string) => void
    onDone?: (document: KnowledgeDocument) => void
    onError?: (message: string, code?: string) => void
  },
): Promise<KnowledgeDocument> {
  const token = localStorage.getItem('auth_token')
  const enterpriseSpace = localStorage.getItem('current_enterprise_space')
  const base = getApiBaseUrl().replace(/\/$/, '')
  const path =
    mode === 'parse'
      ? `/knowledge-bases/${kbId}/documents/${documentId}/parse-stream`
      : `/knowledge-bases/${kbId}/documents/${documentId}/reindex-stream`
  const params = new URLSearchParams()
  if (typeof options.embedding_model_id === 'number') {
    params.set('embedding_model_id', String(options.embedding_model_id))
  }
  const qs = params.toString()
  const url = `${base}${path}${qs ? `?${qs}` : ''}`

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(enterpriseSpace ? { 'X-Enterprise-Space': enterpriseSpace } : {}),
      Accept: 'text/event-stream',
    },
  })

  if (!res.ok) {
    let message = res.statusText || '请求失败'
    try {
      const j = (await res.json()) as { message?: string; detail?: string }
      if (typeof j.message === 'string' && j.message.trim()) {
        message = j.message
      } else if (typeof j.detail === 'string' && j.detail.trim()) {
        message = j.detail
      }
    } catch {
      /* ignore */
    }
    options.onLog(`【错误】${message}`)
    options.onError?.(message)
    throw new Error(message)
  }

  const reader = res.body?.getReader()
  if (!reader) {
    const err = '无法读取响应流'
    options.onLog(`【错误】${err}`)
    options.onError?.(err)
    throw new Error(err)
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let completed: KnowledgeDocument | undefined
  let streamError: Error | undefined

  const handlePayload = (raw: string) => {
    let obj: { type?: string; message?: string; document?: KnowledgeDocument; code?: string }
    try {
      obj = JSON.parse(raw) as typeof obj
    } catch {
      return
    }
    if (obj.type === 'log' && typeof obj.message === 'string') {
      options.onLog(obj.message)
      return
    }
    if (obj.type === 'done' && obj.document) {
      completed = obj.document
      options.onDone?.(obj.document)
      return
    }
    if (obj.type === 'error') {
      const msg = typeof obj.message === 'string' ? obj.message : '处理失败'
      const code = typeof obj.code === 'string' ? obj.code : undefined
      options.onLog(`【错误】${msg}${code ? ` [${code}]` : ''}`)
      options.onError?.(msg, code)
      streamError = new Error(msg)
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split(/\n\n/)
    buffer = parts.pop() || ''
    for (const block of parts) {
      for (const line of block.split('\n')) {
        const trimmed = line.trim()
        if (trimmed.startsWith('data:')) {
          handlePayload(trimmed.slice(5).trim())
        }
      }
    }
    if (streamError) {
      throw streamError
    }
  }

  const tail = decoder.decode()
  if (tail) {
    buffer += tail
  }
  if (buffer.trim()) {
    for (const block of buffer.split(/\n\n/)) {
      for (const line of block.split('\n')) {
        const trimmed = line.trim()
        if (trimmed.startsWith('data:')) {
          handlePayload(trimmed.slice(5).trim())
        }
      }
    }
  }
  if (streamError) {
    throw streamError
  }
  if (!completed) {
    const err = new Error('解析流已结束但未收到完成事件，请查看后端日志或重试')
    options.onLog(`【错误】${err.message}`)
    options.onError?.(err.message)
    throw err
  }
  return completed
}
