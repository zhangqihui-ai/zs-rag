/** MinerU content_list 条目：用于按页 Markdown 与 PDF 框选联动（与后端 mineru_gateway 过滤大致一致） */

export type MineruContentItem = Record<string, unknown> & { _index?: number }

const SKIP_TYPES = new Set(['header', 'footer', 'page_number'])

/** 与 Markdown 分页、PDF 热区一致：跳过页眉页脚等；无正文且无 bbox 的条目不展示 */
export function shouldShowMineruBlock(item: MineruContentItem): boolean {
  const t = String(item.type || '').toLowerCase()
  if (SKIP_TYPES.has(t)) {
    return false
  }
  return mineruBlockPlainText(item).length > 0 || hasRenderableBbox(item)
}

function hasRenderableBbox(item: MineruContentItem): boolean {
  const b = item.bbox
  return Array.isArray(b) && b.length >= 4 && Number(b[2]) > Number(b[0]) && Number(b[3]) > Number(b[1])
}

export function mineruBlockPlainText(item: MineruContentItem): string {
  const t = String(item.type || '').toLowerCase()
  if (t === 'code') {
    const raw = item.code_body ?? item.text ?? item.content
    return String(raw ?? '')
      .replace(/\r\n/g, '\n')
      .trim()
  }
  if (t === 'table') {
    const body = item.table_body ?? item.html ?? item.content
    if (typeof body === 'string' && body.trim()) {
      const stripped = body.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
      return stripped.length > 200 ? `${stripped.slice(0, 200)}…` : stripped || '[表格]'
    }
    return '[表格]'
  }
  if (t === 'image') {
    const cap = String(item.image_caption ?? '').trim()
    const ocr = String(item.image_ocr_text ?? item.caption ?? '').trim()
    return [cap, ocr].filter(Boolean).join(' ') || '[图片]'
  }
  return String(item.text ?? item.content ?? '').trim()
}

export function pageScaleFromItems(items: MineruContentItem[], pageIdx0: number): { mx: number; my: number } {
  let mx = 1
  let my = 1
  for (const it of items) {
    if (Number(it.page_idx) !== pageIdx0) {
      continue
    }
    if (!shouldShowMineruBlock(it)) {
      continue
    }
    const b = it.bbox
    if (!Array.isArray(b) || b.length < 4) {
      continue
    }
    const x0 = Number(b[0])
    const y0 = Number(b[1])
    const x1 = Number(b[2])
    const y1 = Number(b[3])
    if (Number.isFinite(x0) && Number.isFinite(x1) && Number.isFinite(y0) && Number.isFinite(y1)) {
      mx = Math.max(mx, x0, x1)
      my = Math.max(my, y0, y1)
    }
  }
  if (mx <= 0) {
    mx = 1000
  }
  if (my <= 0) {
    my = 1000
  }
  return { mx, my }
}

export type PageGroup = { pageIdx0: number; pageNo: number; entries: { index: number; item: MineruContentItem }[] }

export function groupMineruItemsByPage(items: MineruContentItem[]): PageGroup[] {
  const withIdx = items.map((it, index) => {
    const o: MineruContentItem = { ...it, _index: index }
    return o
  })
  const shown = withIdx.filter(shouldShowMineruBlock)
  const byPage = new Map<number, { index: number; item: MineruContentItem }[]>()
  for (const it of shown) {
    const idx = typeof it._index === 'number' ? it._index : 0
    const p0 = typeof it.page_idx === 'number' ? it.page_idx : 0
    const arr = byPage.get(p0) ?? []
    arr.push({ index: idx, item: it })
    byPage.set(p0, arr)
  }
  const pages = [...byPage.keys()].sort((a, b) => a - b)
  return pages.map((pageIdx0) => ({
    pageIdx0,
    pageNo: pageIdx0 + 1,
    entries: byPage.get(pageIdx0) ?? [],
  }))
}
