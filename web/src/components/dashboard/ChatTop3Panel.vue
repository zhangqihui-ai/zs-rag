<template>
  <aside class="chat-top-panel">
    <header class="chat-top-head">
      <h3>对话调用 Top3</h3>
      <p>当前时段最常用助手</p>
    </header>

    <div v-if="loading" class="chat-top-skeleton" aria-hidden="true"></div>
    <div v-else-if="error" class="chat-top-empty">{{ error }}</div>
    <div v-else-if="!items.length" class="chat-top-empty">暂无对话使用数据</div>
    <div v-else ref="chartRef" class="chat-top-chart"></div>
  </aside>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { getDashboardChatTop, type DashboardChatTopItem, type DashboardUsageRange } from '../../api/dashboard'
import { waitForSpaceContextReady } from '../../composables/useSpaceReady'

const props = defineProps<{
  range: DashboardUsageRange
}>()

const loading = ref(true)
const error = ref('')
const items = ref<DashboardChatTopItem[]>([])
const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

function disposeChart() {
  chart?.dispose()
  chart = null
}

async function fetchTopChats() {
  await waitForSpaceContextReady()
  disposeChart()
  loading.value = true
  error.value = ''
  try {
    const res = await getDashboardChatTop({ range: props.range })
    items.value = res.data.items
  } catch {
    items.value = []
    error.value = '加载失败'
  } finally {
    loading.value = false
    await nextTick()
    renderChart()
  }
}

function renderChart() {
  if (!chartRef.value || !items.value.length) {
    disposeChart()
    return
  }
  disposeChart()
  chart = echarts.init(chartRef.value)

  const names = items.value.map((item) => truncateTitle(item.title))
  const sessions = items.value.map((item) => item.session_count)
  const messages = items.value.map((item) => item.message_count)

  chart.setOption(
    {
      animationDuration: 400,
      grid: { left: 40, right: 12, top: 32, bottom: 36 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, right: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 11 } },
      xAxis: {
        type: 'category',
        data: names,
        axisLine: { lineStyle: { color: '#94a3b8' } },
        axisLabel: {
          color: '#1e293b',
          fontSize: 11,
          fontWeight: 600,
          interval: 0,
          rotate: 0,
        },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        name: '数量',
        nameTextStyle: { color: '#94a3b8', fontSize: 10 },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,0.2)' } },
        axisLabel: { color: '#64748b', fontSize: 10 },
      },
      series: [
        {
          name: '会话数',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 7,
          data: sessions,
          itemStyle: { color: '#22c55e' },
          lineStyle: { width: 2 },
          areaStyle: { opacity: 0.06 },
        },
        {
          name: '消息数',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 7,
          data: messages,
          itemStyle: { color: '#3b82f6' },
          lineStyle: { width: 2 },
          areaStyle: { opacity: 0.06 },
        },
      ],
    },
    true,
  )
  chart.resize()
}

function truncateTitle(title: string): string {
  const text = title.trim() || '未命名对话'
  return text.length > 10 ? `${text.slice(0, 10)}…` : text
}

function handleResize() {
  chart?.resize()
}

watch(
  () => props.range,
  () => {
    fetchTopChats()
  },
)

watch(items, () => {
  nextTick(() => renderChart())
})

onMounted(() => {
  fetchTopChats()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  disposeChart()
})
</script>

<style scoped>
.chat-top-panel {
  display: grid;
  gap: 12px;
  align-content: start;
  min-height: 100%;
  padding-left: 18px;
  border-left: 1px solid var(--border-color);
}

.chat-top-head h3 {
  margin: 0;
  font-size: 0.95rem;
  color: var(--text-primary);
}

.chat-top-head p {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 0.78rem;
}

.chat-top-chart {
  width: 100%;
  height: 280px;
}

.chat-top-skeleton {
  height: 280px;
  border-radius: 12px;
  background: linear-gradient(120deg, var(--bg-tertiary) 0%, rgba(148, 163, 184, 0.14) 50%, var(--bg-tertiary) 100%);
}

.chat-top-empty {
  display: grid;
  place-items: center;
  min-height: 220px;
  color: var(--text-tertiary);
  font-size: 0.84rem;
  text-align: center;
  padding: 16px;
}

@media (max-width: 1100px) {
  .chat-top-panel {
    padding-left: 0;
    border-left: none;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
  }
}
</style>
