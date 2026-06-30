import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { AgentTraceEvent } from '../api/chat'
import { agentTraceSummary } from './agentTraceDisplay'

describe('agentTraceDisplay', () => {
  it('explains zero relevant grades', () => {
    const item: AgentTraceEvent = {
      step: 'grade',
      relevant_count: 0,
      total: 1,
    }
    const summary = agentTraceSummary(item)
    assert.match(summary, /0 \/ 1/)
    assert.match(summary, /均未达相关标准/)
  })
})
