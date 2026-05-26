const HIGHLIGHT_CLASS = 'doc-original-highlight'

export function clearHtmlHighlights(root: HTMLElement | null | undefined): void {
  if (!root) {
    return
  }
  root.querySelectorAll(`mark.${HIGHLIGHT_CLASS}`).forEach((el) => {
    const parent = el.parentNode
    if (!parent) {
      return
    }
    parent.replaceChild(document.createTextNode(el.textContent || ''), el)
    parent.normalize()
  })
}

function normalizeForMatch(text: string): string {
  return text
    .replace(/\s+/g, '')
    .replace(/[“”«»]/g, '"')
    .replace(/[''‛]/g, "'")
    .replace(/[…]/g, '...')
}

export function highlightAndScrollHtmlText(root: HTMLElement | null | undefined, query: string): boolean {
  if (!root) {
    return false
  }
  clearHtmlHighlights(root)
  const raw = query.trim()
  if (!raw) {
    return false
  }

  const probes = [raw, raw.slice(0, Math.min(48, raw.length)), raw.slice(0, Math.min(24, raw.length))].filter(
    (p, i, arr) => p.length >= 4 && arr.indexOf(p) === i,
  )

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  let node = walker.nextNode() as Text | null
  while (node) {
    const content = node.textContent || ''
    for (const probe of probes) {
      let idx = content.indexOf(probe)
      if (idx < 0 && probe.length >= 8) {
        const compactContent = normalizeForMatch(content)
        const compactProbe = normalizeForMatch(probe)
        const compactIdx = compactContent.indexOf(compactProbe)
        if (compactIdx >= 0) {
          idx = compactIdx
          const endIdx = compactIdx + compactProbe.length
          let rawStart = 0
          let rawEnd = content.length
          let seen = 0
          for (let i = 0; i < content.length; i += 1) {
            if (!/\s/.test(content[i] || '')) {
              if (seen === compactIdx) {
                rawStart = i
              }
              if (seen === endIdx - 1) {
                rawEnd = i + 1
                break
              }
              seen += 1
            }
          }
          try {
            const range = document.createRange()
            range.setStart(node, rawStart)
            range.setEnd(node, rawEnd)
            const mark = document.createElement('mark')
            mark.className = HIGHLIGHT_CLASS
            range.surroundContents(mark)
            mark.scrollIntoView({ behavior: 'smooth', block: 'center' })
            return true
          } catch {
            /* 跨节点时 fallback 到整段 scroll */
          }
        }
      }
      if (idx >= 0) {
        try {
          const range = document.createRange()
          range.setStart(node, idx)
          range.setEnd(node, idx + probe.length)
          const mark = document.createElement('mark')
          mark.className = HIGHLIGHT_CLASS
          range.surroundContents(mark)
          mark.scrollIntoView({ behavior: 'smooth', block: 'center' })
          return true
        } catch {
          /* ignore */
        }
      }
    }
    node = walker.nextNode() as Text | null
  }
  return false
}

/** 滚动到匹配文本（可选高亮）。 */
export function scrollHtmlToText(
  root: HTMLElement | null | undefined,
  query: string,
  options?: { highlight?: boolean },
): boolean {
  if (!root) {
    return false
  }
  if (options?.highlight === false) {
    const target = findTextRangeRoot(root, query)
    if (!target) {
      return false
    }
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    return true
  }
  return highlightAndScrollHtmlText(root, query)
}

const PAGE_SENTINEL_CLASS = 'docx-page-sentinel'

function findTextRangeRoot(root: HTMLElement, query: string): HTMLElement | null {
  const raw = query.trim()
  if (!raw) {
    return null
  }
  const probes = [raw, raw.slice(0, Math.min(48, raw.length)), raw.slice(0, Math.min(24, raw.length))].filter(
    (p, i, arr) => p.length >= 4 && arr.indexOf(p) === i,
  )
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  let node = walker.nextNode() as Text | null
  while (node) {
    const content = node.textContent || ''
    for (const probe of probes) {
      if (content.includes(probe)) {
        const el = node.parentElement
        return el ?? null
      }
      if (probe.length >= 8 && normalizeForMatch(content).includes(normalizeForMatch(probe))) {
        const el = node.parentElement
        return el ?? null
      }
    }
    node = walker.nextNode() as Text | null
  }
  return null
}

export function clearDocxPageSentinels(root: HTMLElement | null | undefined): void {
  root?.querySelectorAll(`.${PAGE_SENTINEL_CLASS}`).forEach((el) => el.remove())
}

/** 在 mammoth 原文 HTML 中为每页插入不可见锚点（data-docx-page）。 */
export function installDocxPageSentinels(root: HTMLElement | null | undefined, anchors: Record<number, string>): void {
  if (!root) {
    return
  }
  clearDocxPageSentinels(root)
  const pages = Object.keys(anchors)
    .map((k) => Number(k))
    .filter((n) => Number.isFinite(n) && n >= 1)
    .sort((a, b) => a - b)
  for (const pageNo of pages) {
    const query = anchors[pageNo]
    if (!query?.trim()) {
      continue
    }
    const target = findTextRangeRoot(root, query)
    if (!target) {
      continue
    }
    const sentinel = document.createElement('div')
    sentinel.className = PAGE_SENTINEL_CLASS
    sentinel.dataset.docxPage = String(pageNo)
    sentinel.setAttribute('aria-hidden', 'true')
    target.parentNode?.insertBefore(sentinel, target)
  }
}

export function scrollDocxPageSentinel(
  root: HTMLElement | null | undefined,
  pageNo: number,
  anchors?: Record<number, string> | null,
): boolean {
  if (!root || pageNo < 1) {
    return false
  }
  const sentinel = root.querySelector<HTMLElement>(`.${PAGE_SENTINEL_CLASS}[data-docx-page="${pageNo}"]`)
  if (sentinel) {
    sentinel.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return true
  }
  const query = anchors?.[pageNo]
  if (query) {
    return highlightAndScrollHtmlText(root, query)
  }
  return false
}

export function pickVisibleDocxPage(root: HTMLElement | null | undefined): number | null {
  if (!root) {
    return null
  }
  const cr = root.getBoundingClientRect()
  if (cr.height < 8) {
    return null
  }
  const anchorY = cr.top + Math.min(72, cr.height * 0.18)
  const sentinels = root.querySelectorAll<HTMLElement>(`.${PAGE_SENTINEL_CLASS}[data-docx-page]`)
  let best: { dist: number; page: number } | null = null
  for (const el of sentinels) {
    const r = el.getBoundingClientRect()
    const raw = el.dataset.docxPage
    if (!raw) {
      continue
    }
    const page = Number(raw)
    if (!Number.isFinite(page) || page < 1) {
      continue
    }
    const dist = Math.abs(r.top - anchorY)
    if (!best || dist < best.dist) {
      best = { dist, page }
    }
  }
  return best?.page ?? null
}
