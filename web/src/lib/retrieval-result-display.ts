import type { KnowledgeSearchResult } from '../api/knowledge-base'

const BLOCK_LABELS: Record<string, string> = {
  image: '图片',
  table: '表格',
  heading: '标题',
  paragraph: '正文',
  document_preamble: '文前',
}

export function formatSearchScore(value: number | null | undefined) {
  return value != null && Number.isFinite(value) ? value.toFixed(3) : '—'
}

export function searchResultPreview(result: KnowledgeSearchResult) {
  const preview = result.content_preview?.trim()
  if (preview) return preview
  const content = result.content?.trim() ?? ''
  if (content.length <= 240) return content
  return `${content.slice(0, 239).trim()}…`
}

export function searchResultChunkLabel(result: KnowledgeSearchResult) {
  return `Chunk-${result.chunk_index + 1}`
}

export function searchResultBlockLabel(result: KnowledgeSearchResult) {
  const block = result.citation.block ?? (result.metadata?.block as string | undefined)
  if (!block) return null
  return BLOCK_LABELS[block] ?? block
}

export function searchResultLocationText(result: KnowledgeSearchResult) {
  const citation = result.citation
  if (citation.location_label) return citation.location_label
  if (citation.heading_path) {
    const parts = citation.heading_path.split(' / ').filter(Boolean)
    return parts[parts.length - 1] ?? citation.heading_path
  }
  if (result.heading_path) {
    const parts = result.heading_path.split(' / ').filter(Boolean)
    return parts[parts.length - 1] ?? result.heading_path
  }
  if (citation.page_no != null && citation.page_no > 1) {
    return `第 ${citation.page_no} 页`
  }
  return null
}

export function searchResultOffsetText(result: KnowledgeSearchResult) {
  const start = result.start_offset
  const end = result.end_offset
  if (start == null || end == null || end <= start) return null
  return `字符 ${start}–${end}`
}

export function searchResultKeywords(result: KnowledgeSearchResult) {
  if (Array.isArray(result.enrichment_keywords) && result.enrichment_keywords.length > 0) {
    return result.enrichment_keywords
  }
  const raw = result.metadata?.enrichment_keywords
  return Array.isArray(raw) ? raw.map(String).filter(Boolean) : []
}

export function searchResultQuestions(result: KnowledgeSearchResult) {
  if (Array.isArray(result.enrichment_questions) && result.enrichment_questions.length > 0) {
    return result.enrichment_questions
  }
  const raw = result.metadata?.enrichment_questions
  return Array.isArray(raw) ? raw.map(String).filter(Boolean) : []
}
