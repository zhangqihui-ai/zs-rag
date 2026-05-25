/** MinerU content_list 条目：用于按页 Markdown 与 PDF 框选联动（与后端 mineru_gateway 过滤大致一致） */

import type { KnowledgeChunk } from '../api/knowledge-base'

export type MineruContentItem = Record<string, unknown> & { _index?: number }

const SKIP_TYPES = new Set(['header', 'footer', 'page_number'])

const TABLE_ALLOWED_TAGS = new Set(['TABLE', 'THEAD', 'TBODY', 'TFOOT', 'TR', 'TH', 'TD', 'CAPTION', 'BR', 'SPAN', 'SUP', 'SUB'])
const TABLE_ALLOWED_ATTRS = new Set(['colspan', 'rowspan', 'class'])

function pipeLineToRow(line: string): string[] {
  return line
    .split('|')
    .map((c) => c.trim())
    .filter((c) => c.length > 0)
}

function gridToHtmlTable(rows: string[][], headerRows = 1): string {
  if (!rows.length) {
    return ''
  }
  const width = Math.max(...rows.map((r) => r.length))
  const parts = ['<table>']
  rows.forEach((row, ri) => {
    parts.push('<tr>')
    const cells = [...row, ...Array(Math.max(0, width - row.length)).fill('')]
    for (const cell of cells) {
      const tag = ri < headerRows ? 'th' : 'td'
      parts.push(`<${tag}>${escapeHtml(cell)}</${tag}>`)
    }
    parts.push('</tr>')
  })
  parts.push('</table>')
  return parts.join('')
}

function pipeContentToHtml(content: string, header?: string[]): string {
  const line = content.trim()
  if (!line.includes('|')) {
    return ''
  }
  const row = pipeLineToRow(line)
  if (!row.length) {
    return ''
  }
  if (header?.length) {
    return sanitizeTableHtml(gridToHtmlTable([header, row], 1))
  }
  return sanitizeTableHtml(gridToHtmlTable([row], 0))
}

function tableIndexFromMetadata(m: Record<string, unknown>): number | null {
  const raw = m.table_index
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return raw
  }
  if (typeof raw === 'string' && raw.trim()) {
    const n = Number(raw)
    return Number.isFinite(n) ? n : null
  }
  return null
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function markdownTableToHtml(md: string): string {
  const rows: string[][] = []
  for (const raw of md.split('\n')) {
    const line = raw.trim()
    if (!line.startsWith('|') || !line.endsWith('|')) {
      continue
    }
    const cells = line
      .slice(1, -1)
      .split('|')
      .map((c) => c.trim())
    if (cells.length && cells.every((c) => /^:?-+:?$/.test(c) || !c)) {
      continue
    }
    rows.push(cells)
  }
  if (!rows.length) {
    return ''
  }
  const parts = ['<table>']
  rows.forEach((cells, ri) => {
    parts.push('<tr>')
    for (const cell of cells) {
      const tag = ri === 0 ? 'th' : 'td'
      parts.push(`<${tag}>${escapeHtml(cell)}</${tag}>`)
    }
    parts.push('</tr>')
  })
  parts.push('</table>')
  return parts.join('')
}

/** 仅保留 table 相关标签，去掉 script / 事件属性 */
export function sanitizeTableHtml(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed || !/<table[\s>]/i.test(trimmed)) {
    return ''
  }
  try {
    const doc = new DOMParser().parseFromString(trimmed, 'text/html')
    const table = doc.body.querySelector('table')
    if (!table) {
      return ''
    }
    const walk = (el: Element) => {
      const tag = el.tagName.toUpperCase()
      if (!TABLE_ALLOWED_TAGS.has(tag)) {
        const parent = el.parentElement
        while (el.firstChild) {
          parent?.insertBefore(el.firstChild, el)
        }
        parent?.removeChild(el)
        return
      }
      ;[...el.attributes].forEach((attr) => {
        const name = attr.name.toLowerCase()
        if (name.startsWith('on') || !TABLE_ALLOWED_ATTRS.has(name)) {
          el.removeAttribute(attr.name)
        }
      })
      ;[...el.children].forEach((child) => walk(child))
    }
    walk(table)
    return table.outerHTML
  } catch {
    return ''
  }
}

export function mineruBlockTableBody(item: MineruContentItem): string {
  const body = item.table_body ?? item.html ?? item.content
  return typeof body === 'string' ? body.trim() : ''
}

/** 侧车 content_list 中的完整 table HTML → 可渲染 HTML */
export function mineruBlockTableHtml(item: MineruContentItem): string {
  const t = String(item.type || '').toLowerCase()
  if (t !== 'table') {
    return ''
  }
  const body = mineruBlockTableBody(item)
  if (!body) {
    return ''
  }
  if (body.startsWith('<')) {
    const sanitized = sanitizeTableHtml(body)
    if (sanitized) {
      return sanitized
    }
    // 侧车 HTML 为内部可信来源；sanitize 失败时仍展示完整表格
    if (/<table[\s>]/i.test(body) && /<\/table>/i.test(body)) {
      return body.trim()
    }
    return ''
  }
  if (body.includes('|')) {
    return sanitizeTableHtml(markdownTableToHtml(body)) || ''
  }
  return ''
}

export function mineruBlockIsTableRenderable(item: MineruContentItem): boolean {
  return mineruBlockTableHtml(item).length > 0
}

/** 与 Markdown 分页、PDF 热区一致：跳过页眉页脚等；无正文且无 bbox 的条目不展示 */
export function shouldShowMineruBlock(item: MineruContentItem): boolean {
  const t = String(item.type || '').toLowerCase()
  if (SKIP_TYPES.has(t)) {
    return false
  }
  if (t === 'table' && mineruBlockIsTableRenderable(item)) {
    return true
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
    if (mineruBlockIsTableRenderable(item)) {
      const cap = String(item.table_caption ?? '').trim()
      return cap || '[表格]'
    }
    const body = mineruBlockTableBody(item)
    if (body) {
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

function resolveContentListTableItem(
  meta: Record<string, unknown>,
  items: MineruContentItem[],
  pageNo?: number | null,
): MineruContentItem | null {
  const cli = meta.content_list_index
  if (typeof cli === 'number' && Number.isFinite(cli) && items[cli]) {
    const hit = items[cli]
    if (String(hit.type || '').toLowerCase() === 'table') {
      return hit
    }
  }
  if (typeof cli === 'string' && cli.trim()) {
    const idx = Number(cli)
    if (Number.isFinite(idx) && items[idx] && String(items[idx].type || '').toLowerCase() === 'table') {
      return items[idx]
    }
  }

  const tables = items.filter((it) => String(it.type || '').toLowerCase() === 'table')
  const ti = tableIndexFromMetadata(meta)
  if (ti != null && tables[ti]) {
    return tables[ti]
  }

  const pn = pageNo ?? meta.page_no
  if (typeof pn === 'number' && Number.isFinite(pn)) {
    const pageIdx = pn - 1
    const onPage = tables.filter((t) => t.page_idx === pageIdx)
    if (onPage.length === 1) {
      return onPage[0]
    }
    if (ti != null && onPage[ti]) {
      return onPage[ti]
    }
  }
  return null
}

function tableHtmlFromMetadata(meta: Record<string, unknown>): string {
  const stored = meta.table_body_html
  if (typeof stored !== 'string' || !stored.trim()) {
    return ''
  }
  const sanitized = sanitizeTableHtml(stored)
  if (sanitized) {
    return sanitized
  }
  if (/<table[\s>]/i.test(stored) && /<\/table>/i.test(stored)) {
    return stored.trim()
  }
  return ''
}

export function chunkTableHtml(
  chunk: KnowledgeChunk,
  items: MineruContentItem[],
): string {
  const m = chunk.metadata
  if (!m || typeof m !== 'object') {
    return ''
  }
  const meta = m as Record<string, unknown>
  if (meta.block !== 'table') {
    return ''
  }

  const fromMeta = tableHtmlFromMetadata(meta)
  if (fromMeta) {
    return fromMeta
  }

  const hit = resolveContentListTableItem(meta, items, chunk.page_no)
  if (hit) {
    const html = mineruBlockTableHtml(hit)
    if (html) {
      return html
    }
  }

  // overview 切片正文是「表格 N；列：…」描述，不能当表格数据渲染
  if (meta.table_role === 'overview') {
    return ''
  }

  const header = Array.isArray(meta.table_header)
    ? meta.table_header.filter((h): h is string => typeof h === 'string')
    : undefined
  if (meta.table_role === 'row' && chunk.content.includes('|')) {
    return pipeContentToHtml(chunk.content, header)
  }
  return ''
}

export function chunkShowsTableView(chunk: KnowledgeChunk, items: MineruContentItem[]): boolean {
  return chunkTableHtml(chunk, items).length > 0
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
