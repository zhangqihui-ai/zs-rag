import type { KnowledgeChunk } from '../api/knowledge-base'
import { mineruBlockPlainText, shouldShowMineruBlock, type MineruContentItem } from './mineruContentDisplay'

function normalizeForMatch(text: string): string {
  return text.replace(/\s+/g, '').toLowerCase()
}

function overlapScore(chunkText: string, blockText: string): number {
  const a = normalizeForMatch(chunkText)
  const b = normalizeForMatch(blockText)
  if (!a || !b) {
    return 0
  }
  if (a.includes(b) || b.includes(a)) {
    return Math.min(a.length, b.length)
  }
  const probeLen = Math.min(48, a.length)
  const probe = a.slice(0, probeLen)
  if (probe.length >= 8 && b.includes(probe)) {
    return probe.length
  }
  const tail = a.slice(Math.max(0, a.length - probeLen))
  if (tail.length >= 8 && b.includes(tail)) {
    return tail.length
  }
  return 0
}

/** 在 MinerU content_list 中找与切片正文最匹配的块索引（用于 PDF 左侧高亮）。 */
export function findMineruBlockForChunk(
  chunk: Pick<KnowledgeChunk, 'content' | 'page_no'>,
  items: MineruContentItem[],
): number | null {
  if (!items.length || !chunk.content.trim()) {
    return null
  }
  const pageIdx0 =
    typeof chunk.page_no === 'number' && Number.isFinite(chunk.page_no) && chunk.page_no >= 1
      ? chunk.page_no - 1
      : null

  let best: { index: number; score: number } | null = null
  items.forEach((item, index) => {
    if (!shouldShowMineruBlock(item)) {
      return
    }
    if (pageIdx0 != null && Number(item.page_idx) !== pageIdx0) {
      return
    }
    const blockText = mineruBlockPlainText(item)
    const score = overlapScore(chunk.content, blockText)
    if (score <= 0) {
      return
    }
    if (!best || score > best.score) {
      best = { index, score }
    }
  })
  return best?.index ?? null
}

export function parseRouteFocusInt(raw: unknown): number | null {
  if (raw == null || Array.isArray(raw)) {
    return null
  }
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}
