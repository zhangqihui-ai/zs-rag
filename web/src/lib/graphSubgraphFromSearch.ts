import type { GraphSubgraphEdge, GraphSubgraphNode, GraphSubgraphResponse } from '../api/graph-knowledge-base'

function pickField(row: Record<string, unknown>, ...keys: string[]): string {
  for (const key of keys) {
    const value = row[key]
    if (value !== undefined && value !== null && String(value).trim()) {
      return String(value).trim()
    }
  }
  return ''
}

function ensureNode(
  nodeMap: Map<string, GraphSubgraphNode>,
  id: string,
  entityType: string | null = null,
): void {
  if (nodeMap.has(id)) {
    return
  }
  nodeMap.set(id, {
    id,
    label: id,
    entity_type: entityType,
    degree: 0,
  })
}

export function buildSubgraphFromGraphSearch(
  entities: Record<string, unknown>[] | null | undefined,
  relationships: Record<string, unknown>[] | null | undefined,
): GraphSubgraphResponse | null {
  const nodeMap = new Map<string, GraphSubgraphNode>()

  for (const row of entities ?? []) {
    const name = pickField(row, 'entity_name', 'entity_id', 'name')
    if (!name) {
      continue
    }
    const entityType = pickField(row, 'entity_type', 'type') || null
    ensureNode(nodeMap, name, entityType)
    const node = nodeMap.get(name)!
    if (entityType) {
      node.entity_type = entityType
    }
  }

  const edges: GraphSubgraphEdge[] = []
  for (const row of relationships ?? []) {
    const source = pickField(row, 'src_id', 'entity1', 'source')
    const target = pickField(row, 'tgt_id', 'entity2', 'target')
    if (!source || !target) {
      continue
    }
    ensureNode(nodeMap, source)
    ensureNode(nodeMap, target)
    const keywords = pickField(row, 'keywords')
    const description = pickField(row, 'description')
    edges.push({
      source,
      target,
      label: keywords || null,
      properties: description ? { description } : undefined,
    })
  }

  if (nodeMap.size === 0) {
    return null
  }

  for (const edge of edges) {
    const source = nodeMap.get(edge.source)
    const target = nodeMap.get(edge.target)
    if (source) {
      source.degree = (source.degree ?? 0) + 1
    }
    if (target) {
      target.degree = (target.degree ?? 0) + 1
    }
  }

  const nodes = [...nodeMap.values()]
  return {
    nodes,
    edges,
    stats: {
      node_shown: nodes.length,
      edge_shown: edges.length,
      node_total: nodes.length,
      edge_total: edges.length,
    },
  }
}
