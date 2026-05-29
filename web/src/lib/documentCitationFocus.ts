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

  let bestIndex = -1
  let bestScore = 0
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
    if (bestIndex < 0 || score > bestScore) {
      bestIndex = index
      bestScore = score
    }
  })
  return bestIndex >= 0 ? bestIndex : null
}

/** 块文本是否属于该切片（含截断容错）。 */
function blockBelongsToChunk(blockNorm: string, chunkNorm: string): boolean {
  if (blockNorm.length < 4) {
    return false
  }
  if (chunkNorm.includes(blockNorm)) {
    return true
  }
  const probe = blockNorm.slice(0, Math.min(16, blockNorm.length))
  return probe.length >= 8 && chunkNorm.includes(probe)
}

/** 按起始块 bbox 在 content_list 中定位起始索引（文本锚定失败时的兜底）。 */
function findStartByBbox(
  meta: Record<string, unknown>,
  pageIdx0: number | null,
  items: MineruContentItem[],
): number {
  const rawBbox = Array.isArray(meta.bbox) ? (meta.bbox as unknown[]).map((n) => Number(n)) : null
  const bbox = rawBbox && rawBbox.length >= 4 && rawBbox.every(Number.isFinite) ? rawBbox : null
  if (!bbox) {
    return -1
  }
  let startIdx = -1
  let bestDist = Number.POSITIVE_INFINITY
  items.forEach((it, i) => {
    if (!shouldShowMineruBlock(it)) {
      return
    }
    if (pageIdx0 != null && Number(it.page_idx) !== pageIdx0) {
      return
    }
    const b = it.bbox
    if (!Array.isArray(b) || b.length < 4) {
      return
    }
    const dist =
      Math.abs(Number(b[0]) - bbox[0]) +
      Math.abs(Number(b[1]) - bbox[1]) +
      Math.abs(Number(b[2]) - bbox[2]) +
      Math.abs(Number(b[3]) - bbox[3])
    if (dist < bestDist) {
      bestDist = dist
      startIdx = i
    }
  })
  return bestDist <= 12 ? startIdx : -1
}

/**
 * 找出切片对应的全部 MinerU 版面块索引（用于 PDF 框选整段切片）。
 * 主路：文本锚定——以「切片正文开头所属的块」为起点，沿文档顺序持续纳入
 * 仍属于该切片的块，遇到不属于的块即停止（天然不会越界到下一节）。
 * 文本锚定失败时回退 bbox 起点 / 单块模糊匹配。
 */
export function findMineruBlocksForChunk(
  chunk: Pick<KnowledgeChunk, 'content' | 'page_no'> & { metadata?: Record<string, unknown> | null },
  items: MineruContentItem[],
): number[] {
  if (!items.length) {
    return []
  }
  const meta = chunk.metadata && typeof chunk.metadata === 'object' ? chunk.metadata : {}
  const chunkNorm = normalizeForMatch(chunk.content || '')

  const pageNo =
    typeof chunk.page_no === 'number' && Number.isFinite(chunk.page_no) && chunk.page_no >= 1
      ? chunk.page_no
      : typeof (meta as Record<string, unknown>).page_no === 'number'
        ? ((meta as Record<string, unknown>).page_no as number)
        : null
  const pageIdx0 = pageNo != null ? pageNo - 1 : null

  // 1) 文本锚定起点：切片正文以哪个块的文本开头
  let startIdx = -1
  let startLen = 0
  if (chunkNorm) {
    items.forEach((it, i) => {
      if (!shouldShowMineruBlock(it)) {
        return
      }
      const t = normalizeForMatch(mineruBlockPlainText(it))
      if (t.length >= 6 && chunkNorm.startsWith(t) && t.length > startLen) {
        startIdx = i
        startLen = t.length
      }
    })
  }

  // 2) bbox 兜底起点
  if (startIdx < 0) {
    startIdx = findStartByBbox(meta as Record<string, unknown>, pageIdx0, items)
  }

  // 3) 单块模糊兜底
  if (startIdx < 0) {
    const single = findMineruBlockForChunk(chunk, items)
    return single != null ? [single] : []
  }

  // 4) 顺序扩展：纳入仍属于该切片的块，遇到不属于者停止；可用合并段数兜底封顶
  const rawCount = Math.floor(Number((meta as Record<string, unknown>).merged_segment_count) || 0)
  const maxCount = rawCount > 0 ? rawCount : Number.POSITIVE_INFINITY
  const out: number[] = []
  for (let i = startIdx; i < items.length && out.length < maxCount; i += 1) {
    if (!shouldShowMineruBlock(items[i])) {
      continue
    }
    const t = normalizeForMatch(mineruBlockPlainText(items[i]))
    if (out.length === 0 || blockBelongsToChunk(t, chunkNorm)) {
      out.push(i)
    } else {
      break
    }
  }
  return out
}

export function parseRouteFocusInt(raw: unknown): number | null {
  if (raw == null || Array.isArray(raw)) {
    return null
  }
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}
