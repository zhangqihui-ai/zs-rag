import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ChatCitation } from '../api/chat'

const {
  buildInlineCitationChunk,
  hasInlineCitationContent,
  resolveNumericChunkId,
  shouldUseInlineCitationContent,
} = await import('./citationDetail')

function cite(overrides: Partial<ChatCitation>): ChatCitation {
  return {
    ref: 1,
    document_name: '刑法',
    page_no: 7,
    ...overrides,
  }
}

describe('citationDetail', () => {
  it('detects inline content', () => {
    assert.equal(hasInlineCitationContent(cite({ content: '  条文  ' })), true)
    assert.equal(hasInlineCitationContent(cite({ content: '' })), false)
  })

  it('parses numeric chunk id', () => {
    assert.equal(resolveNumericChunkId(cite({ chunk_id: 42 })), 42)
    assert.equal(resolveNumericChunkId(cite({ chunk_id: '42' })), 42)
    assert.equal(resolveNumericChunkId(cite({ chunk_id: -1 })), null)
  })

  it('prefers inline content for agentic citations', () => {
    const row = cite({ source: 'agentic', content: '第十二条…', chunk_id: 99 })
    assert.equal(shouldUseInlineCitationContent(row), true)
    assert.equal(buildInlineCitationChunk(row).content, '第十二条…')
  })

  it('uses inline content when chunk id is missing', () => {
    const row = cite({ source: 'vector', content: '片段正文' })
    assert.equal(shouldUseInlineCitationContent(row), true)
  })
})
