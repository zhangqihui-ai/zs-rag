<template>
  <div class="agent-trace-panel">
    <button type="button" class="agent-trace-toggle" @click="expanded = !expanded">
      <AppIcon :name="expanded ? 'chevron-up' : 'chevron-down'" :size="14" />
      <span>决策轨迹{{ trace.length ? ` (${trace.length} 步)` : '' }}</span>
      <span v-if="running" class="agent-trace-running">执行中…</span>
    </button>
    <div v-if="expanded" class="agent-trace-body">
      <div v-if="trace.length === 0" class="agent-trace-empty">
        {{ running ? '正在执行，等待轨迹…' : '暂无轨迹。' }}
      </div>
      <ol v-else class="agent-trace-list">
        <li v-for="(item, index) in trace" :key="`${item.step}-${index}`" class="agent-trace-item">
          <div class="agent-trace-dot"></div>
          <div class="agent-trace-content">
            <div class="agent-trace-title">
              <strong>{{ stepLabel(item.step) }}</strong>
              <span v-if="item.elapsed_ms != null">{{ item.elapsed_ms }} ms</span>
            </div>
            <p>{{ traceSummary(item) }}</p>
          </div>
        </li>
      </ol>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import type { AgentTraceEvent } from '../../api/chat'
import AppIcon from '../AppIcon.vue'

const props = withDefaults(
  defineProps<{
    trace: AgentTraceEvent[]
    running?: boolean
    defaultExpanded?: boolean
  }>(),
  {
    running: false,
    defaultExpanded: false,
  },
)

const expanded = ref(props.defaultExpanded)

function routeDecisionLabel(value: string) {
  return value === 'direct' ? '直接回答' : '知识库检索'
}

function stepLabel(step: string) {
  const map: Record<string, string> = {
    route: '路由判断',
    route_refine: '路由二次判断',
    retrieve: '知识检索',
    grade: '相关性评估',
    rewrite: '问题改写',
    generate: '生成回答',
  }
  return map[step] || step
}

function traceSummary(item: AgentTraceEvent) {
  if (item.step === 'route') {
    const pass = item.route_pass != null ? `（第 ${item.route_pass} 轮）` : ''
    return `决策：${routeDecisionLabel(String(item.decision || 'retrieve'))}${pass}。${String(item.reason || '')}`
  }
  if (item.step === 'route_refine') {
    const preTotal = item.pre_retrieve_total ?? 0
    return `预检索试探 ${preTotal} 条后二次路由：${routeDecisionLabel(String(item.decision || 'retrieve'))}。${String(item.reason || '')}`
  }
  if (item.step === 'retrieve') {
    return `第 ${item.iteration || 1} 轮查询「${item.query || ''}」，召回 ${item.total || 0} 条。`
  }
  if (item.step === 'grade') {
    return `相关片段 ${item.relevant_count || 0} / ${item.total || 0}。`
  }
  if (item.step === 'rewrite') {
    return `改写为「${item.to || ''}」。`
  }
  if (item.step === 'generate') {
    return `生成 ${item.answer_chars || 0} 字，引用 ${item.citation_count || 0} 条。`
  }
  return '已完成。'
}
</script>

<style scoped>
.agent-trace-panel {
  margin-top: 10px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-secondary);
  overflow: hidden;
}

.agent-trace-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.85rem;
  cursor: pointer;
}

.agent-trace-toggle:hover {
  color: var(--brand-primary);
  background: var(--bg-tertiary);
}

.agent-trace-running {
  margin-left: auto;
  color: var(--brand-primary);
  font-size: 0.8rem;
}

.agent-trace-body {
  padding: 0 12px 12px;
}

.agent-trace-empty {
  color: var(--text-tertiary);
  font-size: 0.85rem;
}

.agent-trace-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
}

.agent-trace-item {
  display: grid;
  grid-template-columns: 12px 1fr;
  gap: 8px;
}

.agent-trace-dot {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 999px;
  background: var(--brand-primary);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
}

.agent-trace-content {
  min-width: 0;
}

.agent-trace-title {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: var(--text-primary);
  font-size: 0.85rem;
}

.agent-trace-title span,
.agent-trace-content p {
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.agent-trace-content p {
  margin: 4px 0 0;
  line-height: 1.55;
}
</style>
