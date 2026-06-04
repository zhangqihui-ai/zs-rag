import { describe, expect, it } from 'vitest'

import { formatApiDateTime, parseApiDateTime } from './formatDateTime'

describe('parseApiDateTime', () => {
  it('treats naive ISO datetime as UTC', () => {
    const date = parseApiDateTime('2026-05-27T04:27:40')
    expect(date.toISOString()).toBe('2026-05-27T04:27:40.000Z')
  })

  it('parses explicit Z suffix', () => {
    const date = parseApiDateTime('2026-06-01T03:13:52Z')
    expect(date.toISOString()).toBe('2026-06-01T03:13:52.000Z')
  })
})

describe('formatApiDateTime', () => {
  it('returns fallback for empty value', () => {
    expect(formatApiDateTime(null)).toBe('—')
  })

  it('formats naive UTC datetime as Asia/Shanghai (CST)', () => {
    const formatted = formatApiDateTime('2026-06-04T02:30:35')
    expect(formatted).toContain('10:30:35')
    expect(formatted).toMatch(/2026/)
  })
})
