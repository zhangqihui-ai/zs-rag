/**
 * 后端 naive datetime 均按 UTC 存储（datetime.utcnow），JSON 常不带时区后缀。
 * 展示前先按 UTC 解析，再转为用户本地时区。
 */
export function parseApiDateTime(value: string): Date {
  const s = value.trim()
  if (!s) {
    return new Date(Number.NaN)
  }
  if (/[zZ]$/.test(s) || /[+-]\d{2}:\d{2}$/.test(s)) {
    return new Date(s)
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
    return new Date(`${s}T00:00:00Z`)
  }
  const normalized = s.includes('T') ? s : s.replace(' ', 'T')
  return new Date(`${normalized}Z`)
}

export function formatApiDateTime(value: string | null | undefined, fallback = '—'): string {
  if (!value) {
    return fallback
  }
  const date = parseApiDateTime(value)
  if (Number.isNaN(date.getTime())) {
    return fallback
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}
