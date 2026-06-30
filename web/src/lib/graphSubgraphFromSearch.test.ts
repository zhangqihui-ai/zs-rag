import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { buildSubgraphFromGraphSearch } from './graphSubgraphFromSearch'

describe('graphSubgraphFromSearch', () => {
  it('builds nodes and edges from search payload', () => {
    const subgraph = buildSubgraphFromGraphSearch(
      [
        { entity_name: '故意杀人罪', entity_type: '罪名' },
        { entity_name: '刑法', entity_type: '法律' },
      ],
      [{ src_id: '故意杀人罪', tgt_id: '刑法', keywords: '适用', weight: 2 }],
    )
    assert.ok(subgraph)
    assert.equal(subgraph!.nodes.length, 2)
    assert.equal(subgraph!.edges.length, 1)
    assert.equal(subgraph!.edges[0]?.source, '故意杀人罪')
    assert.equal(subgraph!.edges[0]?.target, '刑法')
    assert.equal(subgraph!.stats.node_shown, 2)
    assert.equal(subgraph!.stats.edge_shown, 1)
  })

  it('creates endpoint nodes missing from entity list', () => {
    const subgraph = buildSubgraphFromGraphSearch(
      [{ entity_name: 'A', entity_type: '概念' }],
      [{ src_id: 'A', tgt_id: 'B' }],
    )
    assert.ok(subgraph)
    assert.equal(subgraph!.nodes.length, 2)
    assert.deepEqual(
      subgraph!.nodes.map((node) => node.id).sort(),
      ['A', 'B'],
    )
  })

  it('returns null when no graph data', () => {
    assert.equal(buildSubgraphFromGraphSearch([], []), null)
  })
})
