import axios from 'axios'

import { resolveApiBaseUrl } from '../lib/apiBaseUrl'
import { http, longRequestTimeoutMs, documentRequestTimeoutMs, searchRequestTimeoutMs, resolveEnterpriseSpaceSlug } from '../lib/http'

export type RetrievalMode = 'vector' | 'keyword' | 'hybrid'

/** 知识库底层实现类型；图可视化 Tab 在 lightrag 或 graph_db_enabled 时展示 */
export type KnowledgeBaseType = 'lightrag' | 'classic' | string

export interface KnowledgeBase {
  id: number
  enterprise_space_id: number
  name: string
  description: string | null
  status: 'active' | 'inactive' | 'embedding_unavailable' | 'deleted'
  /** 后端 Phase 1+ 返回；未返回时前端以 graph_db_enabled 作为图 Tab 回退 */
  kb_type?: KnowledgeBaseType | null
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
  kb_type?: KnowledgeBaseType
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

export interface KbProcessLogSummary {
  total_documents: number
  indexed_documents: number
  processing_documents: number
  recent_24h_success: number
  recent_24h_failed: number
}

export interface KbProcessLogEvent {
  id: number
  batch_uid: string
  username: string
  action: string
  action_label: string
  status: string
  total_count: number
  success_count: number
  failed_count: number
  started_at: string
  finished_at: string | null
  duration_seconds: number | null
  duration_label: string
  summary: string
}

export interface KbProcessLogBatchItem {
  id: number
  document_id: number | null
  file_name: string
  status: string
  error_message: string | null
  started_at: string
  finished_at: string | null
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
  /** 实际解析引擎（metadata.parser_backend） */
  parser_engine?: string | null
  parser_engine_label?: string | null
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
  /** 为 true 表示本次上传因内容重复被跳过，返回的是已有文档 */
  upload_skipped?: boolean
  skip_reason?: string | null
  /** 最近一次解析/重建索引完成时间 */
  last_parsed_at?: string | null
  /** 为 true 表示文档处于"可续传"态（取消时保留了已切片/已向量化内容） */
  resumable?: boolean
  created_at: string
  updated_at: string
}

/** 服务端持久化的解析/重建索引日志 */
export interface KnowledgeDocumentParseLog {
  kind: 'parse' | 'reindex' | null
  phase: 'running' | 'success' | 'error' | null
  lines: { t: string; text: string }[]
  updated_at: string | null
  progress?: DocumentProgressPayload | null
}

export interface BatchDocumentProcessItemResult {
  document_id: number
  queued: boolean
  skipped?: boolean
  mode?: 'parse' | 'reindex' | null
  celery_task_id?: string | null
  background_task_id?: number | null
  force?: boolean
  fallback?: boolean
  skip_reason?: string | null
  error?: string | null
}

export interface BatchDocumentProcessResponse {
  items: BatchDocumentProcessItemResult[]
  queued_count: number
  failed_count: number
  skipped_count: number
  total: number
}

export interface BatchDocumentDeleteItemResult {
  document_id: number
  deleted: boolean
  skipped?: boolean
  error?: string | null
}

export interface BatchDocumentDeleteResponse {
  items: BatchDocumentDeleteItemResult[]
  deleted_count: number
  failed_count: number
  skipped_count: number
  total: number
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
  keyword_text?: string | null
  enrichment_keywords?: string[]
  enrichment_questions?: string[]
  metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface KnowledgeChunkEnrichmentUpdatePayload {
  keywords: string[]
  questions: string[]
}

export interface KnowledgeChunkEnrichmentRegenerateResponse {
  keywords: string[]
  questions: string[]
}

export interface ChunkSourceContext {
  text: string
  highlight_start: number
  highlight_end: number
  start_offset: number | null
  end_offset: number | null
  truncated_before: boolean
  truncated_after: boolean
  fallback: boolean
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface DocumentFileExtOption {
  value: string
  label: string
  count: number
}

export interface KnowledgeDocumentListResponse extends PaginatedResponse<KnowledgeDocument> {
  file_ext_options?: DocumentFileExtOption[]
}

export interface KnowledgeSearchRequest {
  query: string
  mode?: RetrievalMode
  top_k?: number
  /** 相似度下限 0~1；低于此值的块被过滤 */
  score_threshold?: number | null
  /** 混合检索：向量分支权重（0~1），全文关键词权重为 1-w；缺省后端 0.5 */
  vector_weight?: number | null
  /** 混合检索通道融合方式：weighted=加权求和（默认）；rrf=加权倒数排名融合 */
  fusion_method?: 'weighted' | 'rrf' | null
  /** 是否召回独立 block=image 的截图 OCR 切片；缺省 false */
  include_image_ocr?: boolean | null
  document_ids?: number[]
}

export interface KnowledgeSearchResult {
  chunk_id: number
  chunk_uid: string
  document_id: number
  document_name: string
  chunk_index: number
  content: string
  content_preview?: string | null
  char_count?: number | null
  start_offset?: number | null
  end_offset?: number | null
  heading_path?: string | null
  enrichment_keywords?: string[]
  enrichment_questions?: string[]
  score: number
  vector_score: number | null
  keyword_score: number | null
  metadata: Record<string, unknown> | null
  citation: {
    document_name: string
    page_no: number | null
    chunk_index: number
    heading_path?: string | null
    location_label?: string | null
    block?: string | null
  }
  /** 多库检索时由后端填充 */
  knowledge_base_id?: number | null
  knowledge_base_name?: string | null
}

export interface KnowledgeSearchResponse {
  query: string
  mode: RetrievalMode
  total: number
  results: KnowledgeSearchResult[]
}

export interface MultiKnowledgeSearchRequest extends KnowledgeSearchRequest {
  knowledge_base_ids: number[]
}

export interface MultiKnowledgeSearchResponse {
  query: string
  mode: RetrievalMode
  knowledge_base_ids: number[]
  total: number
  results: KnowledgeSearchResult[]
}

interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
}

const isEnvelope = <T>(value: unknown): value is ApiEnvelope<T> => {
  return (
    Boolean(value) &&
    typeof value === 'object' &&
    !Array.isArray(value) &&
    'code' in (value as Record<string, unknown>) &&
    'data' in (value as Record<string, unknown>)
  )
}

/** 解包接口响应：支持裸数据、{ code, data }、仅 { data }、分页 { items } */
export function unwrapPayload<T>(payload: unknown): T {
  if (isEnvelope<T>(payload)) {
    return payload.data
  }
  if (
    payload &&
    typeof payload === 'object' &&
    !Array.isArray(payload) &&
    'data' in (payload as Record<string, unknown>)
  ) {
    return (payload as ApiEnvelope<T>).data
  }
  return payload as T
}

export function normalizeKnowledgeBaseList(raw: unknown): KnowledgeBase[] {
  const payload = unwrapPayload<unknown>(raw)
  if (Array.isArray(payload)) {
    return payload as KnowledgeBase[]
  }
  if (payload && typeof payload === 'object' && Array.isArray((payload as { items?: unknown }).items)) {
    return (payload as { items: KnowledgeBase[] }).items
  }
  return []
}

const unwrap = async <T>(request: Promise<{ data: unknown }>): Promise<T> => {
  const response = await request
  return unwrapPayload<T>(response.data)
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
    return unwrap<KnowledgeBase>(http.get(`/knowledge-bases/${kbId}`, { timeout: documentRequestTimeoutMs }))
  },
  create(payload: KnowledgeBasePayload, options?: { signal?: AbortSignal }) {
    return unwrap<KnowledgeBase>(
      http.post('/knowledge-bases', payload, {
        timeout: longRequestTimeoutMs,
        signal: options?.signal,
      }),
    )
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
  listDocuments(
    kbId: number,
    params?: {
      status?: string
      keyword?: string
      /** 扩展名筛选，不含点；多个用逗号分隔，如 doc,docx */
      file_ext?: string
      page?: number
      page_size?: number
      /** created_desc | created_asc | name_asc | updated_desc */
      sort?: string
    },
  ) {
    return unwrap<KnowledgeDocumentListResponse>(
      http.get(`/knowledge-bases/${kbId}/documents`, { params, timeout: documentRequestTimeoutMs }),
    )
  },
  async uploadDocument(
    kbId: number,
    payload: {
      file: File
      chunk_size?: number | null
      chunk_overlap?: number | null
      /** 同一知识库内已有相同内容（SHA256）时跳过上传，返回已有文档 */
      skip_if_duplicate?: boolean
    },
  ): Promise<KnowledgeDocument> {
    const formData = new FormData()
    formData.append('file', payload.file)
    if (typeof payload.chunk_size === 'number') {
      formData.append('chunk_size', String(payload.chunk_size))
    }
    if (typeof payload.chunk_overlap === 'number') {
      formData.append('chunk_overlap', String(payload.chunk_overlap))
    }
    if (payload.skip_if_duplicate) {
      formData.append('skip_if_duplicate', 'true')
    }

    const token = localStorage.getItem('auth_token')
    const enterpriseSpace = resolveEnterpriseSpaceSlug()
    const base = resolveApiBaseUrl().replace(/\/$/, '')
    const url = `${base}/knowledge-bases/${kbId}/documents/upload`

    const controller = new AbortController()
    const timeoutId = window.setTimeout(() => controller.abort(), longRequestTimeoutMs)
    try {
      const res = await fetch(url, {
        method: 'POST',
        signal: controller.signal,
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          'X-Enterprise-Space': enterpriseSpace,
        },
        body: formData,
      })
      if (!res.ok) {
        let message = res.statusText || '上传失败'
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
        throw new Error(message)
      }
      const raw = (await res.json()) as KnowledgeDocument | ApiEnvelope<KnowledgeDocument>
      return isEnvelope<KnowledgeDocument>(raw) ? raw.data : raw
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new Error('上传超时，请稍后重试')
      }
      throw error
    } finally {
      window.clearTimeout(timeoutId)
    }
  },
  recordUploadBatch(
    kbId: number,
    payload: {
      batch_uid: string
      items: Array<{ document_id: number; file_name: string }>
    },
  ) {
    return unwrap<void>(http.post(`/knowledge-bases/${kbId}/process-log/upload-batch`, payload))
  },
  startProcessBatch(
    kbId: number,
    payload: {
      batch_uid: string
      action: 'parse' | 'reindex' | 'delete'
      force?: boolean
    },
  ) {
    return unwrap<void>(http.post(`/knowledge-bases/${kbId}/process-log/start-batch`, payload))
  },
  reconcileProcessBatch(kbId: number, payload: { batch_uid: string }) {
    return unwrap<KbProcessLogEvent>(http.post(`/knowledge-bases/${kbId}/process-log/reconcile-batch`, payload))
  },
  /** 批量提交解析/重建至 Celery 队列（一次 HTTP，不占用浏览器 SSE 连接） */
  batchEnqueueProcess(
    kbId: number,
    payload: {
      document_ids: number[]
      batch_uid?: string
      force?: boolean
      embedding_model_id?: number | null
    },
  ) {
    return unwrap<BatchDocumentProcessResponse>(
      http.post(`/knowledge-bases/${kbId}/documents/batch-process`, payload, {
        timeout: longRequestTimeoutMs,
      }),
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
    return unwrap<KnowledgeDocument>(
      http.get(`/knowledge-bases/${kbId}/documents/${documentId}`, { timeout: documentRequestTimeoutMs }),
    )
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
    return unwrap<KnowledgeDocumentParseLog>(
      http.get(`/knowledge-bases/${kbId}/documents/${documentId}/parse-log`, {
        timeout: documentRequestTimeoutMs,
      }),
    )
  },
  /** 获取原始文件二进制（需携带 Token，用于新窗口预览；大 PDF 单独放宽超时） */
  async fetchDocumentFileBlob(kbId: number, documentId: number): Promise<Blob> {
    const fileTimeoutMs = Number(import.meta.env.VITE_FILE_DOWNLOAD_TIMEOUT_MS) || 180_000
    const { data } = await http.get(`/knowledge-bases/${kbId}/documents/${documentId}/file`, {
      responseType: 'blob',
      timeout: fileTimeoutMs,
    })
    return data as Blob
  },
  /** Word 预览用 docx（.doc 由后端 LibreOffice 转换） */
  async fetchDocumentWordPreviewBlob(kbId: number, documentId: number): Promise<Blob> {
    const fileTimeoutMs = Number(import.meta.env.VITE_FILE_DOWNLOAD_TIMEOUT_MS) || 180_000
    const { data } = await http.get(`/knowledge-bases/${kbId}/documents/${documentId}/word-preview`, {
      responseType: 'blob',
      timeout: fileTimeoutMs,
    })
    return data as Blob
  },
  /** MinerU 侧车 Markdown（仅 MinerU 解析成功且已落盘时可用） */
  async getDocumentMineruMarkdown(kbId: number, documentId: number): Promise<string> {
    const { data } = await http.get(`/knowledge-bases/${kbId}/documents/${documentId}/mineru-markdown`, {
      responseType: 'text',
    })
    return typeof data === 'string' ? data : String(data)
  },
  /** MinerU content_list JSON 原文 */
  async getDocumentMineruContentListText(kbId: number, documentId: number): Promise<string> {
    const { data } = await http.get(`/knowledge-bases/${kbId}/documents/${documentId}/mineru-content-list`, {
      responseType: 'text',
    })
    return typeof data === 'string' ? data : String(data)
  },
  async getDocumentDocxMarkdown(kbId: number, documentId: number): Promise<string> {
    const { data } = await http.get(`/knowledge-bases/${kbId}/documents/${documentId}/docx-markdown`, {
      responseType: 'text',
    })
    return typeof data === 'string' ? data : String(data)
  },
  async getDocumentDocxContentListText(kbId: number, documentId: number): Promise<string> {
    const { data } = await http.get(`/knowledge-bases/${kbId}/documents/${documentId}/docx-content-list`, {
      responseType: 'text',
    })
    return typeof data === 'string' ? data : String(data)
  },
  deleteDocument(kbId: number, documentId: number, batchId?: string | null) {
    return unwrap<void>(
      http.delete(`/knowledge-bases/${kbId}/documents/${documentId}`, {
        params: batchId ? { batch_id: batchId } : undefined,
        timeout: longRequestTimeoutMs,
      }),
    )
  },
  batchDeleteDocuments(
    kbId: number,
    payload: { document_ids: number[]; batch_uid?: string | null },
  ) {
    return unwrap<BatchDocumentDeleteResponse>(
      http.post(`/knowledge-bases/${kbId}/documents/batch-delete`, payload, {
        timeout: longRequestTimeoutMs,
      }),
    )
  },
  getProcessLogSummary(kbId: number) {
    return unwrap<KbProcessLogSummary>(http.get(`/knowledge-bases/${kbId}/process-log/summary`))
  },
  listProcessLogEvents(
    kbId: number,
    params?: {
      page?: number
      page_size?: number
      action?: string
      status?: string
      keyword?: string
    },
  ) {
    return unwrap<PaginatedResponse<KbProcessLogEvent>>(
      http.get(`/knowledge-bases/${kbId}/process-log/events`, { params }),
    )
  },
  listProcessLogBatchItems(kbId: number, batchId: number) {
    return unwrap<{ batch: KbProcessLogEvent; items: KbProcessLogBatchItem[] }>(
      http.get(`/knowledge-bases/${kbId}/process-log/events/${batchId}/items`),
    )
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
    params?: { page?: number; page_size?: number; keyword?: string; chunk_view?: 'lightrag' | 'parse' },
  ) {
    return unwrap<PaginatedResponse<KnowledgeChunk>>(
      http.get(`/knowledge-bases/${kbId}/documents/${documentId}/chunks`, { params }),
    )
  },
  /** 按切片主键取全文（引文详情等） */
  getChunk(kbId: number, chunkId: number) {
    return unwrap<KnowledgeChunk>(http.get(`/knowledge-bases/${kbId}/chunks/${chunkId}`))
  },
  getChunkSourceContext(kbId: number, chunkId: number, contextChars = 320) {
    return unwrap<ChunkSourceContext>(
      http.get(`/knowledge-bases/${kbId}/chunks/${chunkId}/source-context`, {
        params: { context_chars: contextChars },
      }),
    )
  },
  updateChunkEnrichment(kbId: number, chunkId: number, payload: KnowledgeChunkEnrichmentUpdatePayload) {
    return unwrap<KnowledgeChunk>(
      http.patch(`/knowledge-bases/${kbId}/chunks/${chunkId}`, payload),
    )
  },
  regenerateChunkEnrichment(kbId: number, chunkId: number) {
    return unwrap<KnowledgeChunkEnrichmentRegenerateResponse>(
      http.post(`/knowledge-bases/${kbId}/chunks/${chunkId}/regenerate-enrichment`),
    )
  },
  search(kbId: number, payload: KnowledgeSearchRequest) {
    return unwrap<KnowledgeSearchResponse>(
      http.post(`/knowledge-bases/${kbId}/search`, payload, { timeout: searchRequestTimeoutMs }),
    )
  },
  /** 跨多个知识库检索，结果按分数全局合并 */
  searchMulti(payload: MultiKnowledgeSearchRequest) {
    return unwrap<MultiKnowledgeSearchResponse>(
      http.post('/knowledge-bases/multi-search', payload, { timeout: searchRequestTimeoutMs }),
    )
  },
}

export type DocumentProcessStreamMode = 'parse' | 'reindex'

export interface DocumentProgressPayload {
  phase: string
  percent: number
  current?: number | null
  total?: number | null
  message?: string
}

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
    force?: boolean
    batchId?: string | null
    signal?: AbortSignal
    onLog: (line: string) => void
    onProgress?: (payload: DocumentProgressPayload) => void
    onDone?: (document: KnowledgeDocument) => void
    onError?: (message: string, code?: string) => void
    onCancelled?: (document: KnowledgeDocument) => void
  },
): Promise<KnowledgeDocument> {
  const token = localStorage.getItem('auth_token')
  const enterpriseSpace = resolveEnterpriseSpaceSlug()
  const base = resolveApiBaseUrl().replace(/\/$/, '')
  const path =
    mode === 'parse'
      ? `/knowledge-bases/${kbId}/documents/${documentId}/parse-stream`
      : `/knowledge-bases/${kbId}/documents/${documentId}/reindex-stream`
  const params = new URLSearchParams()
  if (typeof options.embedding_model_id === 'number') {
    params.set('embedding_model_id', String(options.embedding_model_id))
  }
  if (options.force) {
    params.set('force', 'true')
  }
  if (options.batchId) {
    params.set('batch_id', options.batchId)
  }
  const qs = params.toString()
  const url = `${base}${path}${qs ? `?${qs}` : ''}`

  const res = await fetch(url, {
    method: 'POST',
    signal: options.signal,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      'X-Enterprise-Space': enterpriseSpace,
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
    let obj: {
      type?: string
      message?: string
      document?: KnowledgeDocument
      code?: string
      phase?: string
      percent?: number
      current?: number | null
      total?: number | null
    }
    try {
      obj = JSON.parse(raw) as typeof obj
    } catch {
      return
    }
    if (obj.type === 'log' && typeof obj.message === 'string') {
      options.onLog(obj.message)
      return
    }
    if (obj.type === 'progress') {
      const phase = typeof obj.phase === 'string' ? obj.phase : 'parsing'
      const percent =
        typeof obj.percent === 'number'
          ? obj.percent
          : phase === 'done' || phase === 'success'
            ? 100
            : 5
      options.onProgress?.({
        phase,
        percent,
        current: obj.current ?? null,
        total: obj.total ?? null,
        message: typeof obj.message === 'string' ? obj.message : '',
      })
      return
    }
    if (obj.type === 'done' && obj.document) {
      completed = obj.document
      options.onDone?.(obj.document)
      return
    }
    if (obj.type === 'cancelled' && obj.document) {
      completed = obj.document
      options.onCancelled?.(obj.document)
      options.onLog('【已取消】解析任务已停止')
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
    if (options.signal?.aborted) {
      const err = new DOMException('Aborted', 'AbortError')
      throw err
    }
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

export async function cancelDocumentProcess(
  kbId: number,
  documentId: number,
  preservePartial = false,
): Promise<KnowledgeDocument> {
  return unwrap<KnowledgeDocument>(
    http.post(`/knowledge-bases/${kbId}/documents/${documentId}/cancel-process`, undefined, {
      params: { preserve_partial: preservePartial },
      timeout: documentRequestTimeoutMs,
    }),
  )
}
