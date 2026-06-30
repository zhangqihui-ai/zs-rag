import type { ChatCitation } from '../api/chat'

function metadataSource(citation: ChatCitation): string {
  const meta = (citation as ChatCitation & { metadata?: { source?: string } }).metadata
  return typeof meta?.source === 'string' ? meta.source.trim().toLowerCase() : ''
}

/** 是否为图知识库（LightRAG）引文。 */
export function isGraphCitation(citation: ChatCitation): boolean {
  const source = (citation.source || '').trim().toLowerCase()
  if (source === 'graph' || source === 'lightrag') {
    return true
  }
  if (metadataSource(citation) === 'lightrag') {
    return true
  }
  if (typeof citation.chunk_id === 'string' && citation.chunk_id.trim()) {
    return true
  }
  return false
}

/** 是否为经典向量/混合知识库引文。 */
export function isVectorCitation(citation: ChatCitation): boolean {
  return !isGraphCitation(citation)
}
