<template>
  <div class="graph-viz-panel">
    <div class="graph-viz-toolbar">
      <label class="field graph-viz-search">
        <span class="field-label">实体搜索</span>
        <div class="input-wrap">
          <AppIcon name="search" class="input-icon" :size="16" />
          <input
            v-model.trim="searchLabel"
            class="input"
            type="text"
            placeholder="输入实体名（* 表示全部；勿在关键词前加 *）"
            @keydown.enter.prevent="loadSubgraph"
          />
        </div>
      </label>

      <label class="field graph-viz-limit">
        <span class="field-label">节点上限</span>
        <div class="graph-viz-stepper">
          <button class="btn btn-ghost" type="button" :disabled="loading || nodeLimit <= 20" @click="bumpLimit(-10)">
            −
          </button>
          <span class="graph-viz-limit-value">{{ nodeLimit }}</span>
          <button class="btn btn-ghost" type="button" :disabled="loading || nodeLimit >= 500" @click="bumpLimit(10)">
            +
          </button>
        </div>
      </label>

      <div class="graph-viz-toolbar-actions">
        <button class="btn btn-secondary" type="button" :disabled="loading" @click="loadSubgraph">
          <AppIcon name="refresh" :size="16" />
          刷新
        </button>
        <button class="btn btn-ghost" type="button" :disabled="loading || exporting" @click="exportGraph">
          {{ exporting ? '导出中…' : '导出数据' }}
        </button>
      </div>
    </div>

    <p v-if="truncatedHint" class="graph-viz-hint">{{ truncatedHint }}</p>
    <div v-if="error" class="status-box error">{{ error }}</div>

    <div class="graph-viz-main">
      <div ref="canvasWrapRef" class="graph-viz-canvas-wrap">
        <div v-if="loading" class="graph-viz-loading">加载图谱…</div>
        <div ref="canvasRef" class="graph-viz-canvas"></div>

        <div class="graph-viz-stats">
          <span>节点 {{ stats.node_shown }}/{{ stats.node_total }}</span>
          <span class="graph-viz-stats-sep">·</span>
          <span>边 {{ stats.edge_shown }}/{{ stats.edge_total }}</span>
        </div>

        <div class="graph-viz-zoom-tools">
          <button class="btn btn-ghost btn-row-compact" type="button" title="放大" @click="zoomBy(1.2)">+</button>
          <button class="btn btn-ghost btn-row-compact" type="button" title="缩小" @click="zoomBy(0.8)">−</button>
          <button class="btn btn-ghost btn-row-compact" type="button" title="适应窗口" @click="fitView">适应</button>
          <button class="btn btn-ghost btn-row-compact" type="button" title="重置布局" @click="loadSubgraph">重置</button>
        </div>
      </div>

      <GraphNodeDetailDrawer
        :kb-id="kbId"
        :detail="nodeDetail"
        :loading="detailLoading"
        :error="detailError"
        @close="clearSelection"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Graph } from '@antv/g6'
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import {
  graphKnowledgeBaseApi,
  type GraphNodeDetail,
  type GraphSubgraphResponse,
} from '../../api/graph-knowledge-base'
import { getKnowledgeBaseErrorMessage } from '../../api/knowledge-base'
import { colorForEntityType } from '../../lib/graphEntityColors'
import AppIcon from '../AppIcon.vue'
import GraphNodeDetailDrawer from './GraphNodeDetailDrawer.vue'

const props = defineProps<{
  kbId: number
  /** 从路由或图检索跳转时预选的实体 ID */
  focusEntityId?: string | null
}>()

const emit = defineEmits<{
  'select-node': [entityId: string]
}>()

const searchLabel = ref('*')
const nodeLimit = ref(100)
const loading = ref(false)
const exporting = ref(false)
const error = ref('')
const truncatedHint = ref('')

const stats = ref({
  node_shown: 0,
  edge_shown: 0,
  node_total: 0,
  edge_total: 0,
})

const canvasRef = ref<HTMLDivElement | null>(null)
const canvasWrapRef = ref<HTMLDivElement | null>(null)
let graph: Graph | null = null
let resizeObserver: ResizeObserver | null = null

const selectedNodeId = ref<string | null>(null)
const nodeDetail = ref<GraphNodeDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

function bumpLimit(delta: number) {
  nodeLimit.value = Math.max(20, Math.min(500, nodeLimit.value + delta))
}

function syncGraphSize() {
  const container = canvasRef.value
  if (!container || !graph) {
    return
  }
  const width = container.clientWidth
  const height = container.clientHeight
  if (width > 0 && height > 0) {
    graph.setSize(width, height)
  }
}

function destroyGraph() {
  if (graph) {
    graph.destroy()
    graph = null
  }
}

function setupResizeObserver() {
  resizeObserver?.disconnect()
  const target = canvasWrapRef.value ?? canvasRef.value
  if (!target) {
    return
  }
  resizeObserver = new ResizeObserver(() => {
    syncGraphSize()
  })
  resizeObserver.observe(target)
}

function buildGraphData(data: GraphSubgraphResponse) {
  return {
    nodes: data.nodes.map((node) => ({
      id: node.id,
      data: node,
      style: {
        fill: colorForEntityType(node.entity_type),
        labelText: node.label,
        size: 10 + Math.min(node.degree ?? 0, 8),
      },
    })),
    edges: data.edges.map((edge, index) => ({
      id: `${edge.source}-${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
      data: edge,
      style: {
        stroke: '#94a3b8',
        lineWidth: 1,
      },
    })),
  }
}

async function renderGraph(data: GraphSubgraphResponse) {
  await nextTick()
  const container = canvasRef.value
  if (!container) {
    return
  }
  destroyGraph()
  const width = container.clientWidth || 640
  const height = container.clientHeight || 480
  graph = new Graph({
    container,
    width,
    height,
    autoResize: true,
    data: buildGraphData(data) as unknown as import('@antv/g6').GraphData,
    layout: {
      type: 'force',
      preventOverlap: true,
      linkDistance: 80,
    },
    node: {
      style: {
        labelFontSize: 10,
        labelFill: '#334155',
      },
    },
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    autoFit: 'view',
  })
  graph.on('node:click', (event) => {
    const id = (event as unknown as { target?: { id?: string } }).target?.id
    if (id) {
      void selectNode(String(id))
    }
  })
  graph.on('canvas:click', () => {
    clearSelection()
  })
  await graph.render()
  setupResizeObserver()
  syncGraphSize()
}

function normalizeSearchLabel(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed || trimmed === '*') {
    return '*'
  }
  let label = trimmed
  while (label.startsWith('*') && label.length > 1) {
    label = label.slice(1).trim()
  }
  return label || '*'
}

async function loadSubgraph() {
  if (!props.kbId || Number.isNaN(props.kbId)) {
    return
  }
  loading.value = true
  error.value = ''
  truncatedHint.value = ''
  try {
    const label = normalizeSearchLabel(searchLabel.value)
    const data = await graphKnowledgeBaseApi.subgraph(props.kbId, {
      label,
      limit: nodeLimit.value,
      depth: 1,
    })
    stats.value = { ...data.stats }
    if (data.stats.node_total > data.stats.node_shown) {
      truncatedHint.value =
        '仅展示部分子图。全库节点较多时请搜索具体实体以缩小范围。'
    }
    await renderGraph(data)
    if (props.focusEntityId?.trim()) {
      await selectNode(props.focusEntityId.trim())
    } else if (selectedNodeId.value) {
      await selectNode(selectedNodeId.value)
    }
  } catch (value) {
    error.value = getKnowledgeBaseErrorMessage(value, '加载图谱失败')
    destroyGraph()
  } finally {
    loading.value = false
  }
}

async function selectNode(entityId: string) {
  selectedNodeId.value = entityId
  emit('select-node', entityId)
  detailLoading.value = true
  detailError.value = ''
  try {
    nodeDetail.value = await graphKnowledgeBaseApi.nodeDetail(props.kbId, entityId)
    if (graph) {
      const states: Record<string, string[]> = {}
      graph.getNodeData().forEach((node) => {
        const id = String(node.id)
        states[id] = id === entityId ? ['active'] : []
      })
      await graph.setElementState(states)
    }
  } catch (value) {
    detailError.value = getKnowledgeBaseErrorMessage(value, '加载节点详情失败')
    nodeDetail.value = null
  } finally {
    detailLoading.value = false
  }
}

function clearSelection() {
  selectedNodeId.value = null
  nodeDetail.value = null
  detailError.value = ''
  if (graph) {
    const states: Record<string, string[]> = {}
    graph.getNodeData().forEach((node) => {
      states[String(node.id)] = []
    })
    void graph.setElementState(states)
  }
}

async function exportGraph() {
  exporting.value = true
  try {
    const label = searchLabel.value.trim() || '*'
    const blob = await graphKnowledgeBaseApi.exportJson(props.kbId, {
      label,
      limit: nodeLimit.value,
      depth: 1,
    })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `graph-kb-${props.kbId}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (value) {
    error.value = getKnowledgeBaseErrorMessage(value, '导出失败')
  } finally {
    exporting.value = false
  }
}

function zoomBy(ratio: number) {
  void graph?.zoomBy(ratio)
}

function fitView() {
  void graph?.fitView()
}

watch(
  () => props.kbId,
  () => {
    void loadSubgraph()
  },
  { immediate: true },
)

watch(
  () => props.focusEntityId,
  (value) => {
    if (value?.trim()) {
      searchLabel.value = value.trim()
      void loadSubgraph()
    }
  },
)

watch(nodeLimit, () => {
  void loadSubgraph()
})

onMounted(() => {
  setupResizeObserver()
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  destroyGraph()
})

defineExpose({
  focusEntity: (entityId: string) => {
    searchLabel.value = entityId
    void loadSubgraph()
  },
})
</script>

<style scoped>
.graph-viz-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-height: 0;
  height: 100%;
}

.graph-viz-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 14px 18px;
  flex-shrink: 0;
}

.graph-viz-search {
  flex: 1;
  min-width: min(320px, 100%);
  margin: 0;
}

.graph-viz-limit {
  margin: 0;
}

.graph-viz-stepper {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-tertiary);
}

.graph-viz-limit-value {
  min-width: 36px;
  text-align: center;
  font-weight: 600;
}

.graph-viz-toolbar-actions {
  display: inline-flex;
  gap: 10px;
  margin-left: auto;
}

.graph-viz-hint {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.graph-viz-panel > .status-box {
  flex-shrink: 0;
}

.graph-viz-main {
  display: flex;
  flex: 1;
  min-height: 0;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  overflow: hidden;
  background: var(--bg-tertiary);
}

.graph-viz-canvas-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.graph-viz-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.graph-viz-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.6);
  z-index: 2;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.graph-viz-stats {
  position: absolute;
  left: 12px;
  bottom: 12px;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  font-size: 0.82rem;
  color: var(--text-secondary);
  box-shadow: var(--card-shadow-xs);
}

.graph-viz-stats-sep {
  opacity: 0.5;
}

.graph-viz-zoom-tools {
  position: absolute;
  left: 12px;
  bottom: 52px;
  z-index: 3;
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
}
</style>
