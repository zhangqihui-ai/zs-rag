import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ChatCitation } from '../api/chat'
import { isGraphCitation, isVectorCitation } from './citationSource'

describe('citationSource', () => {
  it('detects graph citations', () => {
    const row: ChatCitation = {
      ref: 1,
      document_name: '刑法.pdf',
      page_no: null,
      source: 'graph',
    }
    assert.equal(isGraphCitation(row), true)
    assert.equal(isVectorCitation(row), false)
  })

  it('detects legacy agentic lightrag via metadata', () => {
    const row = {
      ref: 1,
      document_name: '刑法.pdf',
      page_no: null,
      source: 'agentic',
      metadata: { source: 'lightrag' },
    } as ChatCitation
    assert.equal(isGraphCitation(row), true)
  })

  it('detects vector citations', () => {
    const row: ChatCitation = {
      ref: 1,
      document_name: '医保制度',
      page_no: 6,
      source: 'vector',
    }
    assert.equal(isVectorCitation(row), true)
    assert.equal(isGraphCitation(row), false)
  })
})
