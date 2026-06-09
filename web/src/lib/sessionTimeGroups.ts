import type { ChatSession } from '../api/chat'
import { parseApiDateTime } from './formatDateTime'

export type SessionTimeGroup = {
  key: string
  label: string
  sessions: ChatSession[]
}

const FIXED_GROUP_LABELS: Record<string, string> = {
  pinned: '置顶',
  today: '今天',
  yesterday: '昨天',
  unknown: '更早',
}

/** 按 Asia/Shanghai 日历日取 YYYY-MM-DD。 */
export function shanghaiCalendarDay(date: Date): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai' }).format(date)
}

function dayDiffFromToday(day: string, today: string): number {
  const todayMs = Date.parse(`${today}T00:00:00+08:00`)
  const dayMs = Date.parse(`${day}T00:00:00+08:00`)
  return Math.round((todayMs - dayMs) / 86_400_000)
}

/** 具体日期展示：同年为「M月D日」，跨年为「YYYY年M月D日」。 */
export function formatDayGroupLabel(day: string, now: Date = new Date()): string {
  const [year, month, date] = day.split('-').map((part) => parseInt(part, 10))
  const nowYear = parseInt(shanghaiCalendarDay(now).slice(0, 4), 10)
  if (year === nowYear) {
    return `${month}月${date}日`
  }
  return `${year}年${month}月${date}日`
}

/**
 * 会话更新时间所属分组键：
 * today | yesterday | day:YYYY-MM-DD | YYYY-MM | unknown
 */
export function sessionTimeGroupKey(updatedAt: string, now: Date = new Date()): string {
  const date = parseApiDateTime(updatedAt)
  if (Number.isNaN(date.getTime())) {
    return 'unknown'
  }

  const today = shanghaiCalendarDay(now)
  const day = shanghaiCalendarDay(date)
  if (day === today) {
    return 'today'
  }

  const diffDays = dayDiffFromToday(day, today)
  if (diffDays === 1) {
    return 'yesterday'
  }
  if (diffDays > 1 && diffDays < 30) {
    return `day:${day}`
  }

  return day.slice(0, 7)
}

function labelForGroupKey(key: string, now: Date): string {
  if (key in FIXED_GROUP_LABELS) {
    return FIXED_GROUP_LABELS[key]
  }
  if (key.startsWith('day:')) {
    return formatDayGroupLabel(key.slice(4), now)
  }
  return key
}

function sortSessionsByUpdatedDesc(sessions: ChatSession[]): ChatSession[] {
  return [...sessions].sort(
    (a, b) => parseApiDateTime(b.updated_at).getTime() - parseApiDateTime(a.updated_at).getTime(),
  )
}

function compareGroupKeys(a: string, b: string): number {
  if (a.startsWith('day:') && b.startsWith('day:')) {
    return b.slice(4).localeCompare(a.slice(4))
  }
  return b.localeCompare(a)
}

/** 将同一会话列表按时间分组展示（置顶优先，其余按更新时间倒序）。 */
export function groupSessionsByTime(
  sessions: ChatSession[],
  options?: { pinnedIds?: Array<number | string>; now?: Date },
): SessionTimeGroup[] {
  const pinnedIds = (options?.pinnedIds ?? []).map((id) => String(id).trim()).filter(Boolean)
  const pinnedSet = new Set(pinnedIds)
  const now = options?.now ?? new Date()

  const pinnedOrdered: ChatSession[] = []
  for (const id of pinnedIds) {
    const row = sessions.find((s) => String(s.id) === id)
    if (row) {
      pinnedOrdered.push(row)
    }
  }

  const rest = sortSessionsByUpdatedDesc(sessions.filter((s) => !pinnedSet.has(String(s.id))))

  const bucketMap = new Map<string, ChatSession[]>()
  for (const session of rest) {
    const key = sessionTimeGroupKey(session.updated_at, now)
    const bucket = bucketMap.get(key)
    if (bucket) {
      bucket.push(session)
    } else {
      bucketMap.set(key, [session])
    }
  }

  const groups: SessionTimeGroup[] = []
  if (pinnedOrdered.length > 0) {
    groups.push({ key: 'pinned', label: labelForGroupKey('pinned', now), sessions: pinnedOrdered })
  }

  for (const key of ['today', 'yesterday'] as const) {
    const rows = bucketMap.get(key)
    if (rows?.length) {
      groups.push({ key, label: labelForGroupKey(key, now), sessions: rows })
      bucketMap.delete(key)
    }
  }

  const dayKeys = [...bucketMap.keys()]
    .filter((key) => key.startsWith('day:'))
    .sort(compareGroupKeys)
  for (const key of dayKeys) {
    const rows = bucketMap.get(key)
    if (rows?.length) {
      groups.push({ key, label: labelForGroupKey(key, now), sessions: rows })
      bucketMap.delete(key)
    }
  }

  const monthKeys = [...bucketMap.keys()]
    .filter((key) => key !== 'unknown')
    .sort((a, b) => b.localeCompare(a))
  for (const key of monthKeys) {
    const rows = bucketMap.get(key)
    if (rows?.length) {
      groups.push({ key, label: labelForGroupKey(key, now), sessions: rows })
      bucketMap.delete(key)
    }
  }

  const unknown = bucketMap.get('unknown')
  if (unknown?.length) {
    groups.push({ key: 'unknown', label: labelForGroupKey('unknown', now), sessions: unknown })
  }

  return groups
}
