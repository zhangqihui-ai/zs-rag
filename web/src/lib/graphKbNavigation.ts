import type { RouteLocationRaw } from 'vue-router'

import { GRAPH_ENTITY_QUERY_KEY, GRAPH_TAB_QUERY_KEY } from './graphNavigation'

/** 跳转到知识库详情页的「知识图谱可视化」Tab，可选定位实体。 */
export function graphVisualizationRoute(kbId: number, entityId?: string | null): RouteLocationRaw {
  const query: Record<string, string> = { [GRAPH_TAB_QUERY_KEY]: 'graph' }
  if (entityId?.trim()) {
    query[GRAPH_ENTITY_QUERY_KEY] = entityId.trim()
  }
  return {
    name: 'knowledge-base-detail',
    params: { id: String(kbId) },
    query,
  }
}
