import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ChatSession } from '../api/chat'
import {
  formatDayGroupLabel,
  groupSessionsByTime,
  sessionTimeGroupKey,
} from './sessionTimeGroups'

function session(id: string, updatedAt: string): ChatSession {
  return {
    id,
    chat_id: '1',
    user_id: 1,
    enterprise_space_id: 1,
    title: `会话 ${id}`,
    created_at: updatedAt,
    updated_at: updatedAt,
  }
}

describe('sessionTimeGroups', () => {
  const now = new Date('2026-06-02T10:00:00+08:00')

  it('classifies today, yesterday, day and month', () => {
    assert.equal(sessionTimeGroupKey('2026-06-02T02:00:00', now), 'today')
    assert.equal(sessionTimeGroupKey('2026-06-01T02:00:00', now), 'yesterday')
    assert.equal(sessionTimeGroupKey('2026-05-20T02:00:00', now), 'day:2026-05-20')
    assert.equal(sessionTimeGroupKey('2026-02-15T02:00:00', now), '2026-02')
  })

  it('formats day labels', () => {
    assert.equal(formatDayGroupLabel('2026-05-20', now), '5月20日')
    assert.equal(formatDayGroupLabel('2025-12-01', now), '2025年12月1日')
  })

  it('groups sessions with pinned first and concrete dates', () => {
    const groups = groupSessionsByTime(
      [
        session('a', '2026-06-02T08:00:00'),
        session('b', '2026-05-20T08:00:00'),
        session('c', '2026-02-01T08:00:00'),
        session('d', '2026-01-10T08:00:00'),
      ],
      { pinnedIds: ['c'], now },
    )

    assert.deepEqual(
      groups.map((g) => g.label),
      ['置顶', '今天', '5月20日', '2026-01'],
    )
    assert.deepEqual(
      groups.map((g) => g.sessions.map((s) => s.id)),
      [['c'], ['a'], ['b'], ['d']],
    )
  })
})
