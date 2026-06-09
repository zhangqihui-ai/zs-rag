import { marked } from 'marked'

export type AssistantContentSeg =
  | { k: 't'; v: string }
  | { k: 'r'; n: number }

export type RenderAssistantMessageOptions = {
  showCitations: boolean
  streaming: boolean
  citationTitleForRef?: (refNum: number) => string
}

const markedConfigured = marked.setOptions({
  gfm: true,
  breaks: true,
})

void markedConfigured

/** 引文占位符（Markdown 解析后再替换为角标，避免拆坏表格/列表）。 */
const CITATION_PLACEHOLDER_RE = /\uE000(\d+)\uE001/g

const CITATION_SOURCE_RE = /\[(\d+)\]|［(\d+)］/g

const ALLOWED_TAGS = new Set([
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'p',
  'br',
  'hr',
  'strong',
  'em',
  'del',
  'ul',
  'ol',
  'li',
  'blockquote',
  'pre',
  'code',
  'table',
  'thead',
  'tbody',
  'tr',
  'th',
  'td',
  'a',
  'div',
  'span',
  'sup',
  'mark',
])

const ALLOWED_ATTR = new Set([
  'href',
  'title',
  'class',
  'target',
  'rel',
  'tabindex',
  'role',
  'data-citation-ref',
])

function escapeHtmlAttr(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function wrapTables(html: string): string {
  return html.replace(/<table\b/gi, '<div class="chat-markdown-table-wrap"><table').replace(/<\/table>/gi, '</table></div>')
}

function sanitizeElement(el: Element): void {
  const children = [...el.children]
  for (const child of children) {
    const tag = child.tagName.toLowerCase()
    if (!ALLOWED_TAGS.has(tag)) {
      while (child.firstChild) {
        el.insertBefore(child.firstChild, child)
      }
      el.removeChild(child)
      continue
    }

    for (const attr of [...child.attributes]) {
      const name = attr.name.toLowerCase()
      if (!ALLOWED_ATTR.has(name)) {
        child.removeAttribute(attr.name)
      }
    }

    if (tag === 'a') {
      child.setAttribute('rel', 'noopener noreferrer')
      child.setAttribute('target', '_blank')
    }

    sanitizeElement(child)
  }
}

/** 白名单净化（浏览器 / jsdom 的 DOMParser，无 dompurify 依赖）。 */
function sanitizeChatHtml(html: string): string {
  if (!html) {
    return ''
  }
  if (typeof DOMParser === 'undefined') {
    return wrapTables(html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, ''))
  }

  const doc = new DOMParser().parseFromString(`<div id="chat-md-root">${html}</div>`, 'text/html')
  const root = doc.getElementById('chat-md-root')
  if (!root) {
    return ''
  }
  sanitizeElement(root)
  return wrapTables(root.innerHTML)
}

/** 将 [1] / ［1］ 替换为占位符，避免 marked 当链接解析或分段破坏表格。 */
export function protectCitationRefs(text: string): string {
  return text.replace(CITATION_SOURCE_RE, (_, ascii, fullwidth) => {
    const num = ascii ?? fullwidth
    return `\uE000${num}\uE001`
  })
}

function citationBadgeHtml(refNum: number, title: string): string {
  const safeTitle = escapeHtmlAttr(title)
  return (
    `<sup class="msg-citation-badge" tabindex="0" role="button" ` +
    `data-citation-ref="${refNum}" title="${safeTitle}（点击查看切片）">${refNum}</sup>`
  )
}

function restoreCitationRefs(
  html: string,
  titleFor: (refNum: number) => string,
): string {
  return html.replace(CITATION_PLACEHOLDER_RE, (_, digits: string) => {
    const refNum = parseInt(digits, 10)
    return citationBadgeHtml(refNum, titleFor(refNum))
  })
}

/** 将 Markdown 文本渲染为可安全注入的 HTML。 */
export function renderChatMarkdown(text: string): string {
  if (!text) {
    return ''
  }
  const raw = marked.parse(text, { async: false }) as string
  return sanitizeChatHtml(raw)
}

/** 按 [1]、[2] 拆分助手正文（引文角标）。 */
export function assistantContentSegments(text: string): AssistantContentSeg[] {
  const out: AssistantContentSeg[] = []
  const re = /\[(\d+)\]|［(\d+)］/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      out.push({ k: 't', v: text.slice(last, m.index) })
    }
    const num = m[1] ?? m[2]
    out.push({ k: 'r', n: parseInt(num, 10) })
    last = m.index + m[0].length
  }
  if (last < text.length) {
    out.push({ k: 't', v: text.slice(last) })
  }
  if (out.length === 0) {
    out.push({ k: 't', v: text })
  }
  return out
}

/** 助手消息统一 HTML 渲染（Markdown + 可选引文角标）。 */
export function renderAssistantMessageHtml(
  content: string,
  options: RenderAssistantMessageOptions,
): string {
  let source = content
  if (options.showCitations) {
    source = protectCitationRefs(content)
  }
  const html = renderChatMarkdown(source)
  if (!options.showCitations) {
    return html
  }
  const titleFor = options.citationTitleForRef ?? ((n: number) => `引文 ${n}`)
  return restoreCitationRefs(html, titleFor)
}
