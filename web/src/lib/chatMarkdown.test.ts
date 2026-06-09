import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'
import { describe, it } from 'node:test'

const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>')
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  Node: dom.window.Node,
  Element: dom.window.Element,
  HTMLElement: dom.window.HTMLElement,
})

const { assistantContentSegments, protectCitationRefs, renderAssistantMessageHtml, renderChatMarkdown } =
  await import('./chatMarkdown')

describe('chatMarkdown', () => {
  it('renders headings and bold', () => {
    const html = renderChatMarkdown('## 标题\n\n**加粗**内容')
    assert.match(html, /<h2[^>]*>标题<\/h2>/)
    assert.match(html, /<strong>加粗<\/strong>/)
  })

  it('renders gfm table with wrap', () => {
    const md = '| 材料 | 备注 |\n| --- | --- |\n| 身份证 | 原件 |'
    const html = renderChatMarkdown(md)
    assert.match(html, /chat-markdown-table-wrap/)
    assert.match(html, /<table/)
    assert.match(html, /<th[^>]*>材料<\/th>/)
  })

  it('strips script tags', () => {
    const html = renderChatMarkdown('<script>alert(1)</script>\n\n正常段落')
    assert.doesNotMatch(html, /<script/i)
    assert.match(html, /正常段落/)
  })

  it('renders citation badges without breaking markdown', () => {
    const html = renderAssistantMessageHtml('说明[1]结束', {
      showCitations: true,
      streaming: false,
      citationTitleForRef: () => '文档A',
    })
    assert.match(html, /data-citation-ref="1"/)
    assert.match(html, /msg-citation-badge/)
    assert.match(html, /说明/)
    assert.match(html, /结束/)
  })

  it('renders citations in table cells', () => {
    const md = '| 项目 | 内容 |\n| --- | --- |\n| 时限 | 1天 [3] |'
    const html = renderAssistantMessageHtml(md, {
      showCitations: true,
      streaming: false,
    })
    assert.match(html, /<table/)
    assert.match(html, /data-citation-ref="3"/)
    assert.doesNotMatch(html, /\| 承诺/)
  })

  it('renders adjacent citations as separate badges', () => {
    const html = renderAssistantMessageHtml('依据[1][2][3]说明', {
      showCitations: true,
      streaming: false,
    })
    assert.match(html, /data-citation-ref="1"/)
    assert.match(html, /data-citation-ref="2"/)
    assert.match(html, /data-citation-ref="3"/)
    const count = (html.match(/msg-citation-badge/g) ?? []).length
    assert.equal(count, 3)
  })

  it('renders citation badges while streaming', () => {
    const html = renderAssistantMessageHtml('说明[1]结束', {
      showCitations: true,
      streaming: true,
    })
    assert.match(html, /data-citation-ref="1"/)
  })

  it('protectCitationRefs handles fullwidth brackets', () => {
    const protectedText = protectCitationRefs('前［2］后')
    assert.match(protectedText, /\uE0002\uE001/)
  })

  it('assistantContentSegments splits refs', () => {
    const segs = assistantContentSegments('前[1]后[2]')
    assert.equal(segs.length, 4)
    assert.deepEqual(segs[1], { k: 'r', n: 1 })
    assert.deepEqual(segs[3], { k: 'r', n: 2 })
  })
})
