/** 跨页面共享「知识库上下文」多选（知识检索、对话等），按工作区隔离。 */

function storageKey(spaceId: number, spaceSlug: string): string {
  if (spaceId > 0) {
    return `zs-rag:retrieval-kb-ids:${spaceId}`
  }
  return `zs-rag:retrieval-kb-ids:s:${spaceSlug || 'default'}`
}

export function loadRetrievalKbPreference(spaceId: number, spaceSlug: string): number[] {
  try {
    const raw = localStorage.getItem(storageKey(spaceId, spaceSlug))
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed
      .map((x) => (typeof x === 'string' ? Number(x) : Number(x)))
      .filter((n): n is number => Number.isInteger(n) && n > 0)
  } catch {
    return []
  }
}

export function saveRetrievalKbPreference(spaceId: number, spaceSlug: string, ids: number[]): void {
  try {
    const uniq: number[] = []
    const seen = new Set<number>()
    for (const n of ids) {
      const x = typeof n === 'string' ? Number(n) : n
      if (!Number.isInteger(x) || x <= 0 || seen.has(x)) {
        continue
      }
      seen.add(x)
      uniq.push(x)
    }
    localStorage.setItem(storageKey(spaceId, spaceSlug), JSON.stringify(uniq))
  } catch {
    // 配额等异常忽略
  }
}
