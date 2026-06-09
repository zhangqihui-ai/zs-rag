import { resolveApiBaseUrl } from '../lib/apiBaseUrl'
import { resolveEnterpriseSpaceSlug } from '../lib/http'
import type { ChatCitation } from './chat'
import type { RetrievalMode } from './knowledge-base'

export interface AgenticRAGQueryRequest {
  question: string
  knowledge_base_ids: number[]
  model_id?: number | null
  top_k?: number
  mode?: RetrievalMode | null
  score_threshold?: number | null
  vector_weight?: number | null
  fusion_method?: 'weighted' | 'rrf' | null
  include_image_ocr?: boolean | null
  max_iterations?: number | null
  min_relevant_docs?: number | null
  temperature?: number | null
  max_tokens?: number | null
  top_p?: number | null
}

export interface AgenticRAGTraceEvent {
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
}

export interface AgenticRAGCompleteResponse {
  answer: string
  citations: ChatCitation[]
  trace: AgenticRAGTraceEvent[]
  route_decision?: string | null
  route_reason?: string | null
  iterations: number
  current_query?: string | null
}

export type AgenticRAGStreamEvent =
  | { type: 'step_completed'; step: string; trace: AgenticRAGTraceEvent; route_decision?: string | null; iterations?: number }
  | { type: 'assistant_delta'; content: string }
  | ({ type: 'assistant_done' } & AgenticRAGCompleteResponse)
  | { type: 'error'; message: string; code?: string }

export async function streamAgenticRAG(
  payload: AgenticRAGQueryRequest,
  onEvent: (event: AgenticRAGStreamEvent) => void,
  options?: { signal?: AbortSignal },
): Promise<void> {
  const token = localStorage.getItem('auth_token') || ''
  const enterpriseSpace = resolveEnterpriseSpaceSlug()
  const res = await fetch(`${resolveApiBaseUrl()}/api/v1/agentic-rag/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      'X-Enterprise-Space': enterpriseSpace,
    },
    body: JSON.stringify(payload),
    signal: options?.signal,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = (await res.json()) as { message?: string; detail?: unknown }
      if (typeof j.message === 'string' && j.message.trim()) {
        detail = j.message
      } else if (j.detail != null) {
        detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
      }
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`)
  }

  const reader = res.body?.getReader()
  if (!reader) {
    throw new Error('响应无 body（无法读取 SSE）')
  }
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep: number
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      for (const line of block.split('\n')) {
        const t = line.trim()
        if (!t.startsWith('data:')) continue
        const raw = t.slice(5).trimStart()
        if (!raw || raw === '[DONE]') continue
        try {
          onEvent(JSON.parse(raw) as AgenticRAGStreamEvent)
        } catch (e) {
          console.warn('Agentic RAG SSE JSON 解析跳过', raw, e)
        }
      }
    }
  }
}
