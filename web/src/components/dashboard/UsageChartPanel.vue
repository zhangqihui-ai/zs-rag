<template>
  <div class="usage-chart-panel">
    <header class="usage-chart-head">
      <div>
        <h3>调用统计</h3>
      </div>
      <div class="usage-chart-controls">
        <div class="usage-range-tabs">
          <button
            v-for="item in rangeOptions"
            :key="item.value"
            type="button"
            :class="['usage-tab', { active: range === item.value }]"
            @click="setRange(item.value)"
          >
            {{ item.label }}
          </button>
        </div>
        <div class="usage-metric-tabs">
          <button
            v-for="item in metricOptions"
            :key="item.value"
            type="button"
            :class="['usage-tab', { active: metric === item.value }]"
            @click="setMetric(item.value)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
    </header>

    <div v-if="loading" class="usage-chart-skeleton" aria-hidden="true"></div>
    <div v-else-if="error" class="usage-chart-empty">{{ error }}</div>
    <div v-else-if="isEmpty" class="usage-chart-empty">暂无用量数据</div>
    <div v-else ref="chartRef" class="usage-chart-canvas"></div>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  getDashboardUsage,
  type DashboardUsageMetric,
  type DashboardUsageRange,
  type DashboardUsageSeries,
} from '../../api/dashboard'
import { waitForSpaceContextReady } from '../../composables/useSpaceReady'

const range = defineModel<DashboardUsageRange>('range', { default: '24h' })

const rangeOptions = [
  { value: '24h' as const, label: '近24h' },
  { value: '7d' as const, label: '近7天' },
  { value: '30d' as const, label: '近30天' },
]

const metricOptions = [
  { value: 'model_calls' as const, label: '模型调用' },
  { value: 'tokens' as const, label: 'Token 消耗' },
  { value: 'chat_api' as const, label: '对话 API' },
]

const metric = ref<DashboardUsageMetric>('model_calls')
const loading = ref(true)
const error = ref('')
const series = ref<DashboardUsageSeries[]>([])
const total = ref(0)
const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

function disposeChart() {
  chart?.dispose()
  chart = null
}

const isEmpty = computed(() => {
  if (loading.value || error.value) return false
  if (total.value > 0) return false
  return !series.value.some((s) => s.points.some((p) => p.v > 0))
})

const palette: Record<string, string> = {
  llm: '#3b82f6',
  embedding: '#14b8a6',
  tokens: '#8b5cf6',
  chat_api: '#22c55e',
}

async function fetchUsage() {
  await waitForSpaceContextReady()
  disposeChart()
  loading.value = true
  error.value = ''
  try {
    const res = await getDashboardUsage({ range: range.value, metric: metric.value })
    series.value = res.data.series
    total.value = res.data.total
  } catch {
    series.value = []
    total.value = 0
    error.value = '用量数据加载失败'
  } finally {
    loading.value = false
    await nextTick()
    renderChart()
  }
}

function setRange(value: DashboardUsageRange) {
  if (range.value === value) return
  range.value = value
}

function setMetric(value: DashboardUsageMetric) {
  if (metric.value === value) return
  metric.value = value
  fetchUsage()
}

function renderChart() {
  if (!chartRef.value || isEmpty.value) {
    disposeChart()
    return
  }
  disposeChart()
  chart = echarts.init(chartRef.value)

  const categories = series.value[0]?.points.map((p) => p.t) ?? []
  const isGroupedBar = metric.value === 'model_calls'
  const isLine = metric.value === 'tokens'

  chart.setOption(
    {
      animationDuration: 400,
      grid: { left: 48, right: 16, top: 24, bottom: 32 },
      tooltip: { trigger: 'axis' },
      legend: series.value.length > 1 ? { top: 0, right: 0 } : undefined,
      xAxis: {
        type: 'category',
        data: categories,
        axisLine: { lineStyle: { color: '#94a3b8' } },
        axisLabel: { color: '#64748b', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,0.2)' } },
        axisLabel: { color: '#64748b', fontSize: 11 },
      },
      series: series.value.map((item) => ({
        name: item.label,
        type: isLine ? 'line' : 'bar',
        smooth: isLine,
        barMaxWidth: isGroupedBar ? 22 : 28,
        barGap: isGroupedBar ? '18%' : undefined,
        itemStyle: { color: palette[item.key] ?? '#3b82f6', borderRadius: isLine ? undefined : 4 },
        areaStyle: isLine ? { opacity: 0.08 } : undefined,
        data: item.points.map((p) => p.v),
      })),
    },
    true,
  )
  chart.resize()
}

function handleResize() {
  chart?.resize()
}

watch(range, () => {
  fetchUsage()
})

onMounted(() => {
  fetchUsage()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  disposeChart()
})

watch([series, metric], () => {
  nextTick(() => renderChart())
})
</script>

<style scoped>
.usage-chart-panel {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.usage-chart-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.usage-chart-head h3 {
  margin: 0;
  font-size: 1rem;
  color: var(--text-primary);
}

.usage-chart-controls {
  display: grid;
  gap: 8px;
  justify-items: end;
}

.usage-range-tabs,
.usage-metric-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.usage-tab {
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 0.78rem;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.usage-tab.active {
  background: rgba(59, 130, 246, 0.12);
  border-color: rgba(59, 130, 246, 0.35);
  color: #2563eb;
  font-weight: 600;
}

.usage-chart-canvas {
  width: 100%;
  height: 280px;
}

.usage-chart-skeleton {
  height: 280px;
  border-radius: 12px;
  background: linear-gradient(120deg, var(--bg-tertiary) 0%, rgba(148, 163, 184, 0.14) 50%, var(--bg-tertiary) 100%);
}

.usage-chart-empty {
  display: grid;
  place-items: center;
  min-height: 220px;
  color: var(--text-tertiary);
  font-size: 0.9rem;
  text-align: center;
  padding: 24px;
}
</style>
