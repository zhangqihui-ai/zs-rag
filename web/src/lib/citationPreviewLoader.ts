import type { ChatCitation } from '../api/chat'
import { knowledgeBaseApi } from '../api/knowledge-base'

import { citationExcerpt } from './citationPreview'
import { isGraphCitation } from './citationSource'

const previewCache = new Map<string, string>()

export async function loadCitationPreviewText(
  c: ChatCitation,
  resolveKbId: (row: ChatCitation) => number | null,
): Promise<string> {
  const inline = c.content != null ? String(c.content).trim() : ''
  if (inline) {
    return citationExcerpt(inline)
  }

  if (isGraphCitation(c)) {
    return '点击查看图谱引文详情。'
  }

  const kbId = resolveKbId(c)
  const chunkId = c.chunk_id
  if (kbId == null || chunkId == null || typeof chunkId !== 'number') {
    return '点击查看引文详情。'
  }

  const cacheKey = `${kbId}:${chunkId}`
  const cached = previewCache.get(cacheKey)
  if (cached != null) {
    return cached
  }

  try {
    const ctx = await knowledgeBaseApi.getChunkSourceContext(kbId, chunkId, 320)
    const excerpt = citationExcerpt(ctx.text || '')
    previewCache.set(cacheKey, excerpt || '点击查看引文详情。')
    return previewCache.get(cacheKey)!
  } catch {
    return '无法加载预览，点击查看详情。'
  }
}
