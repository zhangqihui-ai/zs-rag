type GraphRouter = {
  push: (to: {
    name: string
    params?: Record<string, string>
    query?: Record<string, string>
  }) => Promise<unknown> | void
}

/** 跳转到知识库详情页的「知识图谱可视化」Tab，并定位到指定实体 */
export function navigateToGraphEntity(router: GraphRouter, kbId: number, entityLabel: string) {
  const label = entityLabel.trim()
  if (!label) {
    return
  }
  void router.push({
    name: 'knowledge-base-detail',
    params: { id: String(kbId) },
    query: {
      tab: 'graph',
      graphEntity: label,
    },
  })
}

export const GRAPH_TAB_QUERY_KEY = 'graph'
export const GRAPH_ENTITY_QUERY_KEY = 'graphEntity'
