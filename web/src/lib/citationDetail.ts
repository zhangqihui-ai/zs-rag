import type { ChatCitation } from '../api/chat'
import type { KnowledgeChunk } from '../api/knowledge-base'

export function hasInlineCitationContent(citation: ChatCitation): boolean {
  return citation.content != null && String(citation.content).trim().length > 0
}

export function resolveNumericChunkId(citation: ChatCitation): number | null {
  const raw = citation.chunk_id
  if (typeof raw === 'number' && Number.isFinite(raw) && raw > 0) {
    return raw
  }
  if (typeof raw === 'string' && raw.trim()) {
    const parsed = Number(raw.trim())
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed
    }
  }
  return null
}

export function shouldUseInlineCitationContent(citation: ChatCitation): boolean {
  return hasInlineCitationContent(citation)
}

export function buildInlineCitationChunk(citation: ChatCitation): KnowledgeChunk {
  const content = String(citation.content ?? '')
  const chunkId = resolveNumericChunkId(citation)
  return {
    id: chunkId ?? 0,
    chunk_uid: '',
    document_id: citation.document_id ?? 0,
    chunk_index: citation.chunk_index ?? 0,
    content,
    content_preview: null,
    char_count: content.length,
    token_count: null,
    start_offset: null,
    end_offset: null,
    page_no: citation.page_no,
    heading_path: null,
    vector_status: '',
    vector_id: null,
    metadata: null,
    created_at: '',
    updated_at: '',
  }
}
