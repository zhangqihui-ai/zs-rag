import type {
  AgentTraceCandidateSummary,
  AgentTraceEvent,
  AgentTraceGradeSummary,
} from '../api/chat'
import { knowledgeBaseApi, type KnowledgeChunk } from '../api/knowledge-base'
import { buildInlineCitationChunk, hasInlineCitationContent, resolveNumericChunkId } from './citationDetail'
import { isGraphCitation } from './citationSource'

export type TraceChunkSummary = AgentTraceGradeSummary | AgentTraceCandidateSummary

export type TraceKbResolver = (row: TraceChunkSummary) => number | null

export function isGraphTraceSource(source?: string | null): boolean {
  const value = (source || '').trim().toLowerCase()
  return value === 'lightrag' || value === 'graph'
}

export function resolveTraceNumericChunkId(chunkId: unknown): number | null {
  return resolveNumericChunkId({ chunk_id: chunkId } as Parameters<typeof resolveNumericChunkId>[0])
}

export function findRetrieveCandidatesBeforeStep(
  trace: AgentTraceEvent[],
  stepIndex: number,
): AgentTraceCandidateSummary[] {
  for (let i = stepIndex - 1; i >= 0; i -= 1) {
    const item = trace[i]
    if (item?.step === 'retrieve' && Array.isArray(item.candidates)) {
      return item.candidates
    }
  }
  return []
}

function resolveTraceKbId(row: TraceChunkSummary, resolveKbId?: TraceKbResolver): number | null {
  if (row.knowledge_base_id != null && Number.isFinite(row.knowledge_base_id)) {
    return row.knowledge_base_id
  }
  return resolveKbId?.(row) ?? null
}

export function enrichTraceChunkSummary(
  row: TraceChunkSummary,
  fallbackCandidates: AgentTraceCandidateSummary[],
): TraceChunkSummary {
  const fallback = fallbackCandidates.find((item) => item.index === row.index)
  if (!fallback) {
    return row
  }
  return {
    ...fallback,
    ...row,
    preview: row.preview || fallback.preview,
    content: row.content || fallback.content,
    knowledge_base_id: row.knowledge_base_id ?? fallback.knowledge_base_id,
    document_id: row.document_id ?? fallback.document_id,
    chunk_id: row.chunk_id ?? fallback.chunk_id,
    source: row.source || fallback.source,
    page_no: row.page_no ?? fallback.page_no,
    chunk_index: row.chunk_index ?? fallback.chunk_index,
    knowledge_base_name: row.knowledge_base_name || fallback.knowledge_base_name,
  }
}

function traceRowAsCitation(row: TraceChunkSummary) {
  return {
    document_name: row.document_name,
    page_no: row.page_no ?? null,
    knowledge_base_id: row.knowledge_base_id ?? undefined,
    chunk_id: row.chunk_id ?? undefined,
    document_id: row.document_id ?? undefined,
    chunk_index: row.chunk_index ?? undefined,
    source: row.source,
    content: row.content,
    ref: row.index,
  }
}

function buildInlineTraceChunk(row: TraceChunkSummary): KnowledgeChunk {
  return buildInlineCitationChunk(traceRowAsCitation(row) as Parameters<typeof buildInlineCitationChunk>[0])
}

export async function loadTraceChunkBody(
  row: TraceChunkSummary,
  resolveKbId?: TraceKbResolver,
): Promise<{ chunk: KnowledgeChunk | null; fallbackContent: string | null; error: string | null }> {
  const citationLike = traceRowAsCitation(row)
  const previewContent = String(row.preview || '').trim()

  if (isGraphCitation(citationLike as Parameters<typeof isGraphCitation>[0])) {
    if (!hasInlineCitationContent(citationLike as Parameters<typeof hasInlineCitationContent>[0])) {
      if (previewContent) {
        return { chunk: null, fallbackContent: previewContent, error: null }
      }
      return {
        chunk: null,
        fallbackContent: null,
        error: '该图谱引用未携带正文，请点击「打开文档原文」查看。',
      }
    }
    return {
      chunk: buildInlineTraceChunk(row),
      fallbackContent: null,
      error: null,
    }
  }

  const kbId = resolveTraceKbId(row, resolveKbId)
  const chunkId = resolveTraceNumericChunkId(row.chunk_id)

  if (kbId != null && chunkId != null) {
    try {
      const chunk = await knowledgeBaseApi.getChunk(kbId, chunkId)
      return { chunk, fallbackContent: null, error: null }
    } catch (error) {
      console.error(error)
      if (hasInlineCitationContent(citationLike as Parameters<typeof hasInlineCitationContent>[0])) {
        return { chunk: buildInlineTraceChunk(row), fallbackContent: null, error: null }
      }
    }
  }

  if (hasInlineCitationContent(citationLike as Parameters<typeof hasInlineCitationContent>[0])) {
    return { chunk: buildInlineTraceChunk(row), fallbackContent: null, error: null }
  }

  if (kbId == null || chunkId == null) {
    if (previewContent) {
      return { chunk: null, fallbackContent: previewContent, error: null }
    }
    return {
      chunk: null,
      fallbackContent: null,
      error:
        kbId == null
          ? '无法确定所属知识库（多库对话请在设置中暂只选一个，或重新对话以生成含知识库信息的轨迹）。'
          : '该片段缺少切片 ID，无法加载正文。',
    }
  }

  return { chunk: null, fallbackContent: null, error: '加载切片正文失败，请稍后重试。' }
}
