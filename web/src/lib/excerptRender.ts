/**
 * 将解析后的原文摘录（MinerU/Markdown 风格纯文本）渲染为带结构的 HTML：
 * - `#`~`######` → 不同字号标题（在弹窗内适当缩小）
 * - `**加粗**` → <strong>
 * - 其余按段落
 * 并按字符区间对「本切片」做精确高亮（逐行裁剪，避免跨块标签错乱）。
 *
 * 文本全部转义后再注入固定标签，输入视为可信解析结果，无脚本注入风险。
 */

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** 转义 + 行内加粗。 */
function renderInline(raw: string): string {
  if (!raw) {
    return ''
  }
  return escapeHtml(raw).replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
}

/** 在行内 [start, end) 处包裹高亮；start<0 表示该行无高亮。 */
function renderLineInner(line: string, start: number, end: number): string {
  if (start < 0 || end <= start) {
    return renderInline(line)
  }
  const s = Math.max(0, Math.min(start, line.length))
  const e = Math.max(s, Math.min(end, line.length))
  return (
    renderInline(line.slice(0, s)) +
    '<mark class="exc-mark">' +
    renderInline(line.slice(s, e)) +
    '</mark>' +
    renderInline(line.slice(e))
  )
}

const HEADING_RE = /^(#{1,6})(\s+)(.*)$/

export function renderExcerptHtml(text: string, highlightStart: number, highlightEnd: number): string {
  if (!text) {
    return ''
  }
  const lines = text.split('\n')
  const parts: string[] = []
  let offset = 0
  for (const line of lines) {
    const lineStart = offset
    const lineEnd = offset + line.length
    offset = lineEnd + 1 // 计入换行符

    const trimmed = line.trim()
    if (!trimmed) {
      continue
    }

    // 本行与高亮区间的交集（行内局部坐标）
    const interStart = Math.max(highlightStart, lineStart)
    const interEnd = Math.min(highlightEnd, lineEnd)
    let localStart = -1
    let localEnd = -1
    if (interStart < interEnd) {
      localStart = interStart - lineStart
      localEnd = interEnd - lineStart
    }

    let tag = 'p'
    let body = line
    let prefixLen = 0
    const hm = line.match(HEADING_RE)
    if (hm) {
      const level = hm[1].length
      tag = `h${Math.min(6, level + 2)}`
      prefixLen = hm[1].length + hm[2].length
      body = hm[3]
    }

    let bs = localStart
    let be = localEnd
    if (bs >= 0) {
      bs = Math.max(0, bs - prefixLen)
      be = Math.max(0, be - prefixLen)
    }

    const inner = renderLineInner(body, bs, be)
    parts.push(`<${tag} class="exc-block">${inner}</${tag}>`)
  }
  return parts.join('')
}
