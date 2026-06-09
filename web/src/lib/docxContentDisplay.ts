import { tableCellHtml } from './tableHtmlDisplay'

/** Word docx content_list 块：与后端 docx_view_export 输出一致 */

export type DocxContentBlock = {
  block_index: number
  type?: string
  text?: string
  block?: string
  heading_path?: string | null
  heading_class?: string
  table_role?: string
  table_index?: number
  page_idx?: number
  page_no?: number
}

export function docxBlockPlainText(item: DocxContentBlock): string {
  return String(item.text || '').trim()
}

function parseMetaInt(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.trunc(value)
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value.trim())
    if (Number.isFinite(n)) {
      return Math.trunc(n)
    }
  }
  return null
}

/** 从切片 metadata 读取起始 block_index（含合并块的 block_indices）。 */
export function blockIndexFromChunkMeta(meta: Record<string, unknown> | null | undefined): number | null {
  if (!meta || typeof meta !== 'object') {
    return null
  }
  const idx = parseMetaInt(meta.block_index)
  if (idx != null) {
    return idx
  }
  const list = meta.block_indices
  if (Array.isArray(list)) {
    for (const v of list) {
      const n = parseMetaInt(v)
      if (n != null) {
        return n
      }
    }
  }
  return null
}

export function docxHighlightTextForBlock(blocks: DocxContentBlock[], blockIndex: number): string | null {
  const block = blocks.find((b) => b.block_index === blockIndex)
  const text = block ? docxBlockPlainText(block) : ''
  if (!text) {
    return null
  }
  return text.length > 160 ? text.slice(0, 160) : text
}

export function docxBlockTypeLabel(item: DocxContentBlock): string {
  const t = String(item.type || item.block || 'text')
  const map: Record<string, string> = {
    title: '标题',
    section: '小节',
    text: '正文',
    table: '表格',
    table_overview: '表格',
    heading: '标题',
    paragraph: '正文',
  }
  return map[t] || t
}

export function isDocxTableBlock(item: DocxContentBlock): boolean {
  const t = String(item.type || '')
  return t.startsWith('table') || item.block === 'table'
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** 单块渲染为接近原文的 HTML（左侧框内 / 右侧 Markdown Tab 卡片）。 */
export function docxBlockDisplayHtml(item: DocxContentBlock): string {
  const text = docxBlockPlainText(item)
  if (!text) {
    return ''
  }
  const esc = escapeHtml(text)
  const cls = String(item.heading_class || '')
  const t = String(item.type || item.block || 'text')
  if (cls === 'chapter' || t === 'title') {
    return `<h2 class="docx-block-h2">${esc}</h2>`
  }
  if (cls === 'section' || t === 'section') {
    return `<h3 class="docx-block-h3">${esc}</h3>`
  }
  if (isDocxTableBlock(item)) {
    return tableBlockPreviewHtml(item) || `<p class="docx-block-p">${esc}</p>`
  }
  return `<p class="docx-block-p">${esc}</p>`
}

export function groupDocxBlocksByPage(blocks: DocxContentBlock[]): DocxPageGroup[] {
  const byPage = new Map<number, { index: number; item: DocxContentBlock }[]>()
  for (const item of blocks) {
    const idx = Number(item.block_index)
    if (!Number.isFinite(idx)) {
      continue
    }
    const text = docxBlockPlainText(item)
    if (!text) {
      continue
    }
    const p0 =
      typeof item.page_idx === 'number'
        ? item.page_idx
        : typeof item.page_no === 'number'
          ? item.page_no - 1
          : 0
    const arr = byPage.get(p0) ?? []
    arr.push({ index: idx, item })
    byPage.set(p0, arr)
  }
  const pages = [...byPage.keys()].sort((a, b) => a - b)
  return pages.map((pageIdx0) => ({
    pageIdx0,
    pageNo: pageIdx0 + 1,
    entries: byPage.get(pageIdx0) ?? [],
  }))
}

export function buildDocxPageAnchorTexts(blocks: DocxContentBlock[]): Record<number, string> {
  const out: Record<number, string> = {}
  for (const pg of groupDocxBlocksByPage(blocks)) {
    const first = pg.entries[0]?.item
    const text = first ? docxBlockPlainText(first) : ''
    if (text) {
      out[pg.pageNo] = text
    }
  }
  return out
}

export function countDocxPages(blocks: DocxContentBlock[]): number {
  const pages = new Set<number>()
  for (const item of blocks) {
    if (typeof item.page_no === 'number' && item.page_no >= 1) {
      pages.add(item.page_no)
    } else if (typeof item.page_idx === 'number') {
      pages.add(item.page_idx + 1)
    } else {
      pages.add(1)
    }
  }
  return pages.size || 1
}

/** 用于滚动联动：优先 block 原文，避免 enrichment 行干扰 mammoth 匹配。 */
export function chunkOriginalScrollProbe(
  chunk: { content?: string; content_preview?: string | null; metadata?: Record<string, unknown> | null },
  blocks: DocxContentBlock[],
): string | null {
  const blockIdx = blockIndexFromChunkMeta(chunk.metadata) ?? findDocxBlockForChunk(chunk, blocks)
  if (blockIdx != null) {
    const text = docxHighlightTextForBlock(blocks, blockIdx)
    if (text) {
      return text
    }
  }
  const raw = String(chunk.content || '').trim()
  if (!raw) {
    return null
  }
  const body = raw
    .split('\n')
    .filter((line) => !/^关键词：/.test(line.trim()) && !/^问题：/.test(line.trim()))
    .join('\n')
    .trim()
  const probe = body || raw
  if (probe.length <= 160) {
    return probe
  }
  const preview = String(chunk.content_preview || '').trim()
  if (preview.length >= 8) {
    return preview.length > 120 ? preview.slice(0, 120) : preview
  }
  return probe.slice(0, 120)
}

export function resolveChunkWordPage(
  chunk: { content?: string; page_no?: number | null; metadata?: Record<string, unknown> | null },
  blocks: DocxContentBlock[],
): number | null {
  if (typeof chunk.page_no === 'number' && Number.isFinite(chunk.page_no) && chunk.page_no >= 1) {
    return chunk.page_no
  }
  const meta = chunk.metadata
  if (meta && typeof meta === 'object') {
    const pn = parseMetaInt(meta.page_no)
    if (pn != null && pn >= 1) {
      return pn
    }
    const idx = blockIndexFromChunkMeta(meta)
    if (idx != null) {
      const block = blocks.find((b) => b.block_index === idx)
      if (typeof block?.page_no === 'number' && block.page_no >= 1) {
        return block.page_no
      }
      if (typeof block?.page_idx === 'number') {
        return block.page_idx + 1
      }
    }
  }
  const blockIdx = findDocxBlockForChunk(chunk, blocks)
  if (blockIdx != null) {
    const block = blocks.find((b) => b.block_index === blockIdx)
    if (typeof block?.page_no === 'number' && block.page_no >= 1) {
      return block.page_no
    }
    if (typeof block?.page_idx === 'number') {
      return block.page_idx + 1
    }
  }
  return blocks.length > 0 ? 1 : null
}

export function chunkMatchesDocxBlock(
  chunk: { content?: string; metadata?: Record<string, unknown> | null },
  blockIndex: number,
): boolean {
  const meta = chunk.metadata
  if (meta && typeof meta === 'object') {
    const idx = parseMetaInt(meta.block_index)
    const end = parseMetaInt(meta.block_index_end)
    const list = meta.block_indices
    if (idx != null && idx === blockIndex) {
      return true
    }
    if (idx != null && end != null && blockIndex >= idx && blockIndex <= end) {
      return true
    }
    if (Array.isArray(list) && list.some((v) => parseMetaInt(v) === blockIndex)) {
      return true
    }
  }
  return false
}

function keyValueLineToHtml(line: string): string | null {
  if (!line.includes('：') || !line.includes('；')) {
    return null
  }
  const pairs: Array<[string, string]> = []
  for (const part of line.split('；')) {
    const idx = part.indexOf('：')
    if (idx > 0) {
      const key = part.slice(0, idx).trim()
      const value = part.slice(idx + 1).trim()
      if (key) {
        pairs.push([key, value])
      }
    }
  }
  if (!pairs.length) {
    return null
  }
  let html = '<table><thead><tr>'
  html += tableCellHtml('th', '字段')
  html += tableCellHtml('th', '内容')
  html += '</tr></thead><tbody>'
  for (const [key, value] of pairs) {
    html += `<tr>${tableCellHtml('th', key)}${tableCellHtml('td', value)}</tr>`
  }
  html += '</tbody></table>'
  return html
}

export function tableBlockPreviewHtml(item: DocxContentBlock): string {
  const text = docxBlockPlainText(item)
  if (!text) {
    return ''
  }
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean)
  if (lines.length === 0) {
    return ''
  }
  if (lines.length === 1) {
    const kv = keyValueLineToHtml(lines[0])
    if (kv) {
      return kv
    }
  }
  const rows: string[][] = []
  for (const line of lines) {
    if (line.includes('；') && line.includes('：')) {
      const kv = keyValueLineToHtml(line)
      if (kv && lines.length === 1) {
        return kv
      }
      const cells: string[] = []
      for (const part of line.split('；')) {
        const idx = part.indexOf('：')
        if (idx > 0) {
          cells.push(part.slice(idx + 1).trim())
        } else if (part.trim()) {
          cells.push(part.trim())
        }
      }
      if (cells.length) {
        rows.push(cells)
        continue
      }
    }
    if (line.includes('|')) {
      rows.push(line.split('|').map((c) => c.trim()).filter(Boolean))
    } else {
      rows.push([line])
    }
  }
  if (rows.length >= 2) {
    const width = Math.max(...rows.map((r) => r.length))
    let html = '<table>'
    rows.forEach((row, ri) => {
      html += '<tr>'
      const cells = [...row, ...Array(Math.max(0, width - row.length)).fill('')]
      for (const cell of cells) {
        html += tableCellHtml(ri === 0 ? 'th' : 'td', cell)
      }
      html += '</tr>'
    })
    html += '</table>'
    return html
  }
  return `<pre>${text.replace(/&/g, '&amp;').replace(/</g, '&lt;')}</pre>`
}

/** 在 docx content_list 中找与切片最匹配的 block_index（用于左侧块高亮）。 */
export function findDocxBlockForChunk(
  chunk: { content?: string; metadata?: Record<string, unknown> | null },
  blocks: DocxContentBlock[],
): number | null {
  const fromMeta = blockIndexFromChunkMeta(chunk.metadata)
  if (fromMeta != null) {
    return fromMeta
  }
  const content = String(chunk.content || '').trim()
  if (!content || !blocks.length) {
    return null
  }
  const norm = content.replace(/\s+/g, '')
  let best: { index: number; score: number } | null = null
  for (const item of blocks) {
    const idx = Number(item.block_index)
    if (!Number.isFinite(idx)) {
      continue
    }
    const text = docxBlockPlainText(item).replace(/\s+/g, '')
    if (!text) {
      continue
    }
    let score = 0
    if (norm.includes(text) || text.includes(norm)) {
      score = Math.min(norm.length, text.length)
    } else {
      const probe = norm.slice(0, Math.min(48, norm.length))
      if (probe.length >= 8 && text.includes(probe)) {
        score = probe.length
      }
    }
    if (score > 0 && (!best || score > best.score)) {
      best = { index: idx, score }
    }
  }
  return best?.index ?? null
}
