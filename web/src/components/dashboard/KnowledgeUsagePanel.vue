<template>
  <section class="surface-card kb-usage-panel">
    <header class="kb-usage-head">
      <span class="kb-usage-icon tone-blue">
        <AppIcon name="knowledge" :size="20" />
      </span>
      <div class="kb-usage-title">
        <h3>知识库使用情况</h3>
        <p>Top5 常用知识库、类型与文件分布</p>
      </div>
      <router-link to="/knowledge-bases" class="btn btn-ghost kb-usage-link">管理</router-link>
    </header>

    <div class="kb-usage-strip">
      <div v-for="item in summaryStrip" :key="item.label" class="kb-usage-strip-item">
        <span :class="['kb-usage-strip-icon', item.tone]">
          <AppIcon :name="item.icon" :size="16" />
        </span>
        <strong :class="item.color">{{ item.value }}</strong>
        <span>{{ item.label }}</span>
      </div>
    </div>

    <div class="kb-usage-grid">
      <div class="kb-usage-block">
        <div class="kb-usage-block-head">
          <span>Top5 常用知识库</span>
          <span class="kb-usage-meta">按召回次数排序</span>
        </div>
        <div v-if="!topItems.length" class="kb-usage-empty">暂无引用数据</div>
        <div v-else ref="topChartRef" class="kb-top-chart"></div>
      </div>

      <div class="kb-usage-block">
        <div class="kb-usage-block-head">
          <span>类型分布</span>
          <span class="kb-usage-meta">Milvus {{ knowledge.vector }} · LightRAG {{ knowledge.graph }}</span>
        </div>
        <div class="kb-type-bar" aria-hidden="true">
          <span class="kb-type-seg kb-type-seg--vector" :style="{ width: `${vectorPercent}%` }"></span>
          <span class="kb-type-seg kb-type-seg--graph" :style="{ width: `${graphPercent}%` }"></span>
        </div>
        <div class="kb-type-legend">
          <span><i class="dot dot-blue"></i>向量库 Milvus</span>
          <span><i class="dot dot-red"></i>图库 LightRAG</span>
        </div>
      </div>

      <div class="kb-usage-block">
        <div class="kb-usage-block-head">
          <span>文件类型分布</span>
        </div>
        <div v-if="!fileExtItems.length" class="kb-usage-empty">暂无文件</div>
        <div v-else ref="extChartRef" class="kb-ext-chart"></div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { DashboardKnowledgeStats, DashboardKnowledgeUsageStats } from '../../api/dashboard'
import AppIcon from '../AppIcon.vue'

const props = defineProps<{
  knowledge: DashboardKnowledgeStats
  usage: DashboardKnowledgeUsageStats
}>()

const topChartRef = ref<HTMLElement | null>(null)
const extChartRef = ref<HTMLElement | null>(null)
let topChart: echarts.ECharts | null = null
let extChart: echarts.ECharts | null = null

const topItems = computed(() => props.usage.top_knowledge_bases ?? [])
const fileExtItems = computed(() => props.usage.file_ext_distribution ?? [])

const vectorPercent = computed(() => {
  const total = props.knowledge.total
  if (!total) return 0
  return Math.round((props.knowledge.vector / total) * 100)
})

const graphPercent = computed(() => {
  const total = props.knowledge.total
  if (!total) return 0
  return Math.round((props.knowledge.graph / total) * 100)
})

const summaryStrip = computed(() => [
  {
    label: '知识库总数',
    value: formatNumber(props.knowledge.total),
    icon: 'knowledge',
    tone: 'tone-blue',
    color: 'c-blue',
  },
  {
    label: '文件总数',
    value: formatNumber(props.knowledge.document_total),
    icon: 'folder',
    tone: 'tone-teal',
    color: 'c-teal',
  },
  {
    label: '存储容量',
    value: formatBytes(props.knowledge.storage_bytes),
    icon: 'database',
    tone: 'tone-indigo',
    color: 'c-indigo',
  },
])

function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function formatBytes(value: number): string {
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size >= 10 || unitIndex === 0 ? size.toFixed(unitIndex === 0 ? 0 : 1) : size.toFixed(2)} ${units[unitIndex]}`
}

function renderTopChart() {
  if (!topChartRef.value || !topItems.value.length) {
    topChart?.dispose()
    topChart = null
    return
  }
  if (!topChart) topChart = echarts.init(topChartRef.value)

  const names = topItems.value.map((item) => item.kb_name)
  const recalls = topItems.value.map((item) => item.recall_count)
  const binds = topItems.value.map((item) => item.conversation_bind_count)

  topChart.setOption(
    {
      grid: { left: 120, right: 24, top: 8, bottom: 8 },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { top: 0, right: 0, data: ['召回次数', '绑定次数'] },
      xAxis: { type: 'value', minInterval: 1, splitLine: { show: false } },
      yAxis: {
        type: 'category',
        data: names,
        axisLabel: { width: 100, overflow: 'truncate' },
      },
      series: [
        {
          name: '召回次数',
          type: 'bar',
          data: recalls,
          itemStyle: { color: '#3b82f6', borderRadius: [0, 4, 4, 0] },
          barMaxWidth: 14,
        },
        {
          name: '绑定次数',
          type: 'bar',
          data: binds,
          itemStyle: { color: '#94a3b8', borderRadius: [0, 4, 4, 0] },
          barMaxWidth: 14,
        },
      ],
    },
    true,
  )
  topChart.resize()
}

function renderExtChart() {
  if (!extChartRef.value || !fileExtItems.value.length) {
    extChart?.dispose()
    extChart = null
    return
  }
  if (!extChart) extChart = echarts.init(extChartRef.value)

  extChart.setOption(
    {
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, type: 'scroll' },
      series: [
        {
          type: 'pie',
          radius: ['42%', '68%'],
          center: ['50%', '44%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          label: { formatter: '{b}\n{d}%' },
          data: fileExtItems.value.map((item, index) => ({
            name: item.file_ext || 'unknown',
            value: item.count,
            itemStyle: { color: extColors[index % extColors.length] },
          })),
        },
      ],
    },
    true,
  )
  extChart.resize()
}

const extColors = ['#3b82f6', '#14b8a6', '#8b5cf6', '#f59e0b', '#ef4444', '#06b6d4', '#84cc16', '#64748b']

function renderCharts() {
  renderTopChart()
  renderExtChart()
}

function handleResize() {
  topChart?.resize()
  extChart?.resize()
}

watch([topItems, fileExtItems], () => nextTick(() => renderCharts()))

onMounted(() => {
  nextTick(() => renderCharts())
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  topChart?.dispose()
  extChart?.dispose()
  topChart = null
  extChart = null
})
</script>

<style scoped>
.kb-usage-panel {
  display: grid;
  gap: 18px;
}

.kb-usage-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.kb-usage-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  flex-shrink: 0;
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
}

.kb-usage-title {
  flex: 1;
  min-width: 0;
}

.kb-usage-title h3 {
  margin: 0;
  font-size: 1rem;
}

.kb-usage-title p {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.kb-usage-link {
  flex-shrink: 0;
}

.kb-usage-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.kb-usage-strip-item {
  display: grid;
  justify-items: center;
  gap: 6px;
  padding: 12px 8px;
  border-radius: 14px;
  background: var(--bg-tertiary);
  text-align: center;
}

.kb-usage-strip-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
}

.kb-usage-grid {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr 0.8fr;
  gap: 16px;
}

.kb-usage-block {
  display: grid;
  gap: 10px;
  align-content: start;
  padding: 14px;
  border-radius: 14px;
  background: var(--bg-tertiary);
}

.kb-usage-block-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 0.84rem;
  color: var(--text-secondary);
}

.kb-usage-meta {
  color: var(--text-tertiary);
  font-size: 0.76rem;
}

.kb-top-chart,
.kb-ext-chart {
  width: 100%;
  height: 220px;
}

.kb-type-bar {
  display: flex;
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.15);
}

.kb-type-seg--vector {
  background: linear-gradient(90deg, #2563eb, #60a5fa);
}

.kb-type-seg--graph {
  background: linear-gradient(90deg, #dc2626, #f87171);
}

.kb-type-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.78rem;
  color: var(--text-tertiary);
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 6px;
  border-radius: 999px;
  vertical-align: middle;
}

.dot-blue { background: #3b82f6; }
.dot-red { background: #ef4444; }

.kb-usage-empty {
  display: grid;
  place-items: center;
  min-height: 160px;
  color: var(--text-tertiary);
  font-size: 0.84rem;
}

.tone-blue { background: rgba(59, 130, 246, 0.12); color: #2563eb; }
.tone-teal { background: rgba(20, 184, 166, 0.12); color: #0d9488; }
.tone-indigo { background: rgba(99, 102, 241, 0.12); color: #4f46e5; }
.c-blue { color: #2563eb; }
.c-teal { color: #0d9488; }
.c-indigo { color: #4f46e5; }

@media (max-width: 1280px) {
  .kb-usage-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 820px) {
  .kb-usage-strip {
    grid-template-columns: 1fr;
  }
}
</style>
