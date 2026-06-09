/** 表格 HTML 展示辅助：固定行高省略 + 悬停 title */

function escapeAttr(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
}

/**
 * 为 td/th 补充 title（悬停看全文）；不改变表格结构。
 */
export function enrichTableHtmlForDisplay(html: string): string {
  const trimmed = html.trim()
  if (!trimmed || !/<table[\s>]/i.test(trimmed)) {
    return trimmed
  }
  if (typeof DOMParser === 'undefined') {
    return trimmed
  }
  try {
    const doc = new DOMParser().parseFromString(`<div id="wrap">${trimmed}</div>`, 'text/html')
    const wrap = doc.getElementById('wrap')
    if (!wrap) {
      return trimmed
    }
    wrap.querySelectorAll('td, th').forEach((el) => {
      const text = (el.textContent || '').replace(/\s+/g, ' ').trim()
      if (text) {
        el.setAttribute('title', text)
      }
    })
    return wrap.innerHTML
  } catch {
    return trimmed
  }
}

export function tableCellHtml(tag: 'td' | 'th', cell: string): string {
  const esc = cell
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  const title = escapeAttr(cell)
  return `<${tag} title="${title}">${esc}</${tag}>`
}
