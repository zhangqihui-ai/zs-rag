import type { ChatCitation } from '../api/chat'

export function citationExcerpt(text: string, maxLen = 240): string {
  const oneLine = text.replace(/\s+/g, ' ').trim()
  if (!oneLine) {
    return ''
  }
  if (oneLine.length <= maxLen) {
    return oneLine
  }
  return `${oneLine.slice(0, maxLen - 1)}…`
}

export function citationPreviewMeta(c: ChatCitation): string {
  const parts: string[] = []
  if (c.page_no != null) {
    parts.push(`第 ${c.page_no} 页`)
  }
  if (c.chunk_index != null) {
    parts.push(`片段 #${c.chunk_index + 1}`)
  }
  if (c.source === 'graph') {
    parts.push('图检索')
  }
  return parts.join(' · ')
}
