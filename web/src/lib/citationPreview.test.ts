import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

const { citationExcerpt, citationPreviewMeta } = await import('./citationPreview')

describe('citationPreview', () => {
  it('truncates long excerpt', () => {
    const text = '甲'.repeat(300)
    const excerpt = citationExcerpt(text, 240)
    assert.equal(excerpt.length, 240)
    assert.match(excerpt, /…$/)
  })

  it('builds preview meta', () => {
    const meta = citationPreviewMeta({
      ref: 1,
      document_name: '刑法',
      page_no: 7,
      chunk_index: 11,
    })
    assert.match(meta, /第 7 页/)
    assert.match(meta, /片段 #12/)
  })
})
