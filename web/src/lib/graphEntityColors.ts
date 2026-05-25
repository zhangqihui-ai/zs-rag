const ENTITY_TYPE_PALETTE = [
  '#3b82f6',
  '#22c55e',
  '#f97316',
  '#a855f7',
  '#ec4899',
  '#14b8a6',
  '#eab308',
  '#ef4444',
  '#6366f1',
  '#06b6d4',
  '#84cc16',
  '#f43f5e',
] as const

const UNKNOWN_COLOR = '#94a3b8'

const typeColorCache = new Map<string, string>()

export function colorForEntityType(entityType: string | null | undefined): string {
  if (!entityType || !entityType.trim()) {
    return UNKNOWN_COLOR
  }
  const key = entityType.trim().toLowerCase()
  const cached = typeColorCache.get(key)
  if (cached) {
    return cached
  }
  let hash = 0
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0
  }
  const color = ENTITY_TYPE_PALETTE[hash % ENTITY_TYPE_PALETTE.length]
  typeColorCache.set(key, color)
  return color
}

export function isLightragKnowledgeBase(config: Record<string, unknown> | null | undefined): boolean {
  if (!config || typeof config !== 'object') {
    return false
  }
  return config.kb_type === 'lightrag'
}

export function entityTypeLegendTypes(types: Iterable<string | null | undefined>): string[] {
  const set = new Set<string>()
  for (const t of types) {
    const v = (t || '').trim()
    if (v) {
      set.add(v)
    }
  }
  return [...set].sort((a, b) => a.localeCompare(b, 'zh-CN'))
}
