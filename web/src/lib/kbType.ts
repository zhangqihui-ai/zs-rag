import type { KnowledgeBase } from '../api/knowledge-base'

/** 与 backend app.core.kb_type.get_kb_type 对齐 */
export function resolveKnowledgeBaseType(
  kb: Pick<KnowledgeBase, 'kb_type' | 'graph_db_enabled' | 'config'> | null | undefined,
): 'lightrag' | 'classic' {
  if (!kb) {
    return 'classic'
  }
  const raw = kb.kb_type
  if (raw === 'lightrag' || raw === 'classic') {
    return raw
  }
  const cfg = kb.config
  if (cfg && typeof cfg === 'object') {
    const legacy = (cfg as Record<string, unknown>).kb_type
    if (legacy === 'lightrag') {
      return 'lightrag'
    }
    if (legacy === 'classic') {
      return 'classic'
    }
  }
  if (kb.graph_db_enabled) {
    return 'lightrag'
  }
  return 'classic'
}

export function isGraphKnowledgeBase(
  kb: Pick<KnowledgeBase, 'kb_type' | 'graph_db_enabled' | 'config'> | null | undefined,
): boolean {
  return resolveKnowledgeBaseType(kb) === 'lightrag'
}
