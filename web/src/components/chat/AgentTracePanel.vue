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

            <div v-if="item.step === 'retrieve' && pathResults(item).length" class="agent-trace-detail-block">
              <button
                type="button"
                class="agent-trace-section-toggle"
                :aria-expanded="isSectionExpanded(index, 'paths')"
                @click="toggleSection(index, 'paths')"
              >
                <AppIcon
                  :name="isSectionExpanded(index, 'paths') ? 'chevron-up' : 'chevron-down'"
                  :size="12"
                />
                <span class="agent-trace-section-title">各路召回</span>
                <span class="agent-trace-section-hint">
                  {{ pathResultsSummary(item) }}
                </span>
              </button>
              <div v-if="isSectionExpanded(index, 'paths')" class="agent-trace-section-body">
                <ul class="agent-trace-detail-list">
                  <li
                    v-for="(path, pathIndex) in pathResults(item)"
                    :key="`p-${pathIndex}`"
                    class="agent-trace-detail-card agent-trace-path-card"
                  >
                    <div class="agent-trace-detail-head">
                      <span class="agent-trace-source-badge" :class="path.kb_type === 'lightrag' ? 'is-graph' : 'is-vector'">
                        {{ pathTypeLabel(path.kb_type) }}
                      </span>
                      <span v-if="path.knowledge_base_name" class="agent-trace-kb-badge">{{ path.knowledge_base_name }}</span>
                      <span class="agent-trace-detail-meta">
                        召回 {{ path.recalled_count ?? 0 }} / Top K {{ path.path_top_k ?? '—' }}
                      </span>
                    </div>
                    <ul v-if="path.candidates?.length" class="agent-trace-path-candidates">
                      <li v-for="row in path.candidates" :key="`pc-${pathIndex}-${row.index}`">
                        <span class="agent-trace-detail-index">[{{ row.index }}]</span>
                        <span class="agent-trace-detail-doc">{{ row.document_name }}</span>
                        <span class="agent-trace-detail-score">检索分 {{ formatScore(row.score) }}</span>
                      </li>
                    </ul>
                    <p v-if="path.error" class="agent-trace-detail-reason agent-trace-detail-reason--muted">{{ path.error }}</p>
                  </li>
                </ul>
              </div>
            </div>

            <div v-if="item.step === 'retrieve' && mergeMeta(item)" class="agent-trace-detail-block">
              <button
                type="button"
                class="agent-trace-section-toggle"
                :aria-expanded="isSectionExpanded(index, 'merge')"
                @click="toggleSection(index, 'merge')"
              >
                <AppIcon
                  :name="isSectionExpanded(index, 'merge') ? 'chevron-up' : 'chevron-down'"
                  :size="12"
                />
                <span class="agent-trace-section-title">合并筛选</span>
                <span class="agent-trace-section-hint">{{ mergePhaseLine(item) }}</span>
              </button>
              <div v-if="isSectionExpanded(index, 'merge')" class="agent-trace-section-body">
                <p class="agent-trace-merge-line">{{ mergePhaseLine(item) }}</p>
                <p v-if="mergeMeta(item)?.strategy === 'auto_fair'" class="agent-trace-merge-meta">
                  策略：自动公平合并
                </p>
                <p v-else-if="mergeMeta(item)?.strategy" class="agent-trace-merge-meta">
                  策略：{{ mergeMeta(item)?.strategy }}
                </p>
                <p v-if="mergeMeta(item)?.strategy === 'auto_fair'" class="agent-trace-merge-desc">
                  {{ mergeFairStrategyText() }}
                </p>
                <ul v-if="mergePhaseSteps(item).length" class="agent-trace-merge-steps">
                  <li v-for="(line, stepIndex) in mergePhaseSteps(item)" :key="`ms-${stepIndex}`">
                    {{ line }}
                  </li>
                </ul>
              </div>
            </div>

            <div v-if="item.step === 'retrieve' && retrieveCandidates(item).length" class="agent-trace-detail-block">
              <button
                type="button"
                class="agent-trace-section-toggle"
                :aria-expanded="isSectionExpanded(index, 'final')"
                @click="toggleSection(index, 'final')"
              >
                <AppIcon
                  :name="isSectionExpanded(index, 'final') ? 'chevron-up' : 'chevron-down'"
                  :size="12"
                />
                <span class="agent-trace-section-title">最终片段 ({{ retrieveCandidates(item).length }})</span>
                <span class="agent-trace-section-hint">{{ finalCandidatesSummary(item) }}</span>
              </button>
              <div v-if="isSectionExpanded(index, 'final')" class="agent-trace-section-body">
                <ul class="agent-trace-detail-list">
                  <li v-for="row in retrieveCandidates(item)" :key="`c-${row.index}`" class="agent-trace-detail-card">
                    <div class="agent-trace-detail-head">
                      <span class="agent-trace-detail-index">[{{ row.index }}]</span>
                      <span
                        v-if="row.source"
                        class="agent-trace-source-badge"
                        :class="sourceBadgeClass(row.source)"
                      >
                        {{ sourceLabel(row.source) }}
                      </span>
                      <span v-if="row.knowledge_base_name" class="agent-trace-kb-badge">{{ row.knowledge_base_name }}</span>
                      <span class="agent-trace-detail-doc">{{ row.document_name }}</span>
                      <span v-if="chunkLabel(row.page_no, row.chunk_index)" class="agent-trace-detail-meta">
                        {{ chunkLabel(row.page_no, row.chunk_index) }}
                      </span>
                      <span class="agent-trace-detail-score">
                        检索分 {{ formatScore(row.score) }}
                        <template v-if="row.merge_score != null"> · 合并分 {{ formatScore(row.merge_score) }}</template>
                      </span>
                    </div>
                    <p v-if="row.preview" class="agent-trace-detail-preview">{{ row.preview }}</p>
                  </li>
                </ul>
              </div>
            </div>

            <div v-if="item.step === 'grade' && gradeRows(item).length" class="agent-trace-detail-block">
              <button
                type="button"
                class="agent-trace-section-toggle"
                :aria-expanded="isSectionExpanded(index, 'grade')"
                @click="toggleSection(index, 'grade')"
              >
                <AppIcon
                  :name="isSectionExpanded(index, 'grade') ? 'chevron-up' : 'chevron-down'"
                  :size="12"
                />
                <span class="agent-trace-section-title">逐条评估 ({{ gradeRows(item).length }})</span>
                <span class="agent-trace-section-hint">{{ gradeRowsSummary(item) }}</span>
              </button>
              <div v-if="isSectionExpanded(index, 'grade')" class="agent-trace-section-body">
                <div v-if="item.evaluated_question" class="agent-trace-eval-question">
                  评估问题：{{ item.evaluated_question }}
                </div>
                <ul class="agent-trace-detail-list">
                  <li
                    v-for="row in gradeRows(item)"
                    :key="`g-${row.index}`"
                    class="agent-trace-detail-card agent-trace-detail-card--clickable"
                    :class="row.relevant ? 'is-relevant' : 'is-irrelevant'"
                    role="button"
                    tabindex="0"
                    :title="'点击查看切片正文'"
                    @click="openGradeChunk(row, index)"
                    @keydown.enter.prevent="openGradeChunk(row, index)"
                    @keydown.space.prevent="openGradeChunk(row, index)"
                  >
                    <div class="agent-trace-detail-head">
                      <span class="agent-trace-detail-index">[{{ row.index }}]</span>
                      <span class="agent-trace-detail-doc">{{ row.document_name }}</span>
                      <span class="agent-trace-detail-score">检索分 {{ formatScore(row.retrieval_score) }}</span>
                      <span
                        class="agent-trace-grade-badge"
                        :class="row.relevant ? 'is-relevant' : 'is-irrelevant'"
                      >
                        {{ gradeVerdict(row.relevant, row.grade_score) }}
                      </span>
                    </div>
                    <p
                      v-if="row.reason"
                      class="agent-trace-grade-reason"
                      :class="row.relevant ? 'is-relevant' : 'is-irrelevant'"
                    >
                      {{ row.reason }}
                    </p>
                    <p v-else class="agent-trace-grade-reason agent-trace-grade-reason--muted">未返回评估原因</p>
                    <p v-if="row.preview" class="agent-trace-grade-preview">{{ row.preview }}</p>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </li>
      </ol>
    </div>

    <AgentTraceChunkModal
      :open="chunkModalOpen"
      :row="chunkModalRow"
      :resolve-kb-id="resolveKbId"
      @close="closeGradeChunkModal"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import type { AgentTraceEvent, AgentTraceGradeSummary } from '../../api/chat'
import {
  agentTraceGradeRows,
  agentTraceMergeMeta,
  agentTracePathResults,
  agentTraceRetrieveCandidates,
  agentTraceStepLabel,
  agentTraceSummary,
  formatChunkLabel,
  formatGradeVerdict,
  formatMergeFairStrategyText,
  formatMergePhaseLine,
  formatMergePhaseSteps,
  formatRetrievalScore,
  tracePathTypeLabel,
  traceSourceLabel,
} from '../../lib/agentTraceDisplay'
import {
  enrichTraceChunkSummary,
  findRetrieveCandidatesBeforeStep,
  type TraceKbResolver,
} from '../../lib/traceChunkDetail'
import AgentTraceChunkModal from './AgentTraceChunkModal.vue'
import AppIcon from '../AppIcon.vue'

type TraceSectionKey = 'paths' | 'merge' | 'final' | 'grade'

const props = withDefaults(
  defineProps<{
    trace: AgentTraceEvent[]
    running?: boolean
    defaultExpanded?: boolean
    resolveKbId?: TraceKbResolver
  }>(),
  {
    running: false,
    defaultExpanded: false,
  },
)

const expanded = ref(props.defaultExpanded)
const sectionExpanded = ref<Record<string, boolean>>({})
const chunkModalOpen = ref(false)
const chunkModalRow = ref<AgentTraceGradeSummary | null>(null)

function openGradeChunk(row: AgentTraceGradeSummary, traceIndex: number): void {
  const fallbackCandidates = findRetrieveCandidatesBeforeStep(props.trace, traceIndex)
  chunkModalRow.value = enrichTraceChunkSummary(row, fallbackCandidates) as AgentTraceGradeSummary
  chunkModalOpen.value = true
}

function closeGradeChunkModal(): void {
  chunkModalOpen.value = false
  chunkModalRow.value = null
}

function sectionStorageKey(traceIndex: number, section: TraceSectionKey): string {
  return `${traceIndex}-${section}`
}

function isSectionExpanded(traceIndex: number, section: TraceSectionKey): boolean {
  return sectionExpanded.value[sectionStorageKey(traceIndex, section)] === true
}

function toggleSection(traceIndex: number, section: TraceSectionKey): void {
  const key = sectionStorageKey(traceIndex, section)
  sectionExpanded.value = {
    ...sectionExpanded.value,
    [key]: !isSectionExpanded(traceIndex, section),
  }
}

function pathResultsSummary(item: AgentTraceEvent): string {
  const paths = pathResults(item)
  const parts = paths.map((path) => {
    const label = path.kb_type === 'lightrag' ? '图' : '向量'
    return `${label} ${path.recalled_count ?? 0}`
  })
  return parts.length ? parts.join(' · ') : '点击展开'
}

function finalCandidatesSummary(item: AgentTraceEvent): string {
  const rows = retrieveCandidates(item)
  const names = rows
    .slice(0, 2)
    .map((row) => row.document_name)
    .filter(Boolean)
  if (!names.length) {
    return '点击展开'
  }
  if (rows.length > 2) {
    return `${names.join('、')} 等 ${rows.length} 条`
  }
  return names.join('、')
}

function gradeRowsSummary(item: AgentTraceEvent): string {
  const rows = gradeRows(item)
  const total = item.total ?? rows.length
  const relevant =
    item.relevant_count ?? rows.filter((row) => row.relevant).length
  return `相关 ${relevant} / ${total}`
}

const stepLabel = agentTraceStepLabel
const traceSummary = agentTraceSummary
const retrieveCandidates = agentTraceRetrieveCandidates
const pathResults = agentTracePathResults
const mergeMeta = agentTraceMergeMeta
const mergePhaseLine = formatMergePhaseLine
const mergeFairStrategyText = formatMergeFairStrategyText
const mergePhaseSteps = formatMergePhaseSteps
const gradeRows = agentTraceGradeRows
const formatScore = formatRetrievalScore
const gradeVerdict = formatGradeVerdict
const chunkLabel = formatChunkLabel
const sourceLabel = traceSourceLabel
const pathTypeLabel = tracePathTypeLabel

function sourceBadgeClass(source?: string | null): string {
  const value = (source || '').trim().toLowerCase()
  return value === 'lightrag' || value === 'graph' ? 'is-graph' : 'is-vector'
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
.agent-trace-content > p {
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.agent-trace-content > p {
  margin: 4px 0 0;
  line-height: 1.55;
}

.agent-trace-detail-block {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.agent-trace-section-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.78rem;
  text-align: left;
  cursor: pointer;
}

.agent-trace-section-toggle:hover {
  color: var(--brand-primary);
}

.agent-trace-section-title {
  font-weight: 600;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.agent-trace-section-hint {
  margin-left: auto;
  min-width: 0;
  color: var(--text-tertiary);
  font-size: 0.74rem;
  line-height: 1.4;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-trace-section-body {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
}

.agent-trace-detail-title {
  margin-bottom: 8px;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.agent-trace-eval-question {
  margin-bottom: 8px;
  font-size: 0.78rem;
  line-height: 1.55;
  color: var(--text-secondary);
}

.agent-trace-detail-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.agent-trace-detail-card {
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
}

.agent-trace-detail-card.is-relevant {
  border-color: rgba(22, 163, 74, 0.28);
}

.agent-trace-detail-card.is-irrelevant {
  border-color: rgba(217, 119, 6, 0.24);
}

.agent-trace-detail-card--clickable {
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.agent-trace-detail-card--clickable:hover,
.agent-trace-detail-card--clickable:focus-visible {
  border-color: rgba(37, 99, 235, 0.35);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08);
  outline: none;
}

.agent-trace-detail-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  font-size: 0.78rem;
  line-height: 1.45;
}

.agent-trace-detail-index {
  font-weight: 700;
  color: var(--text-primary);
}

.agent-trace-detail-doc {
  font-weight: 600;
  color: var(--text-primary);
}

.agent-trace-kb-badge {
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(37, 99, 235, 0.1);
  color: var(--brand-primary);
}

.agent-trace-source-badge {
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 600;
}

.agent-trace-source-badge.is-vector {
  background: rgba(13, 148, 136, 0.12);
  color: #0f766e;
}

.agent-trace-source-badge.is-graph {
  background: rgba(124, 58, 237, 0.12);
  color: #6d28d9;
}

.agent-trace-path-candidates {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  display: grid;
  gap: 4px;
}

.agent-trace-path-candidates li {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  font-size: 0.76rem;
}

.agent-trace-merge-line,
.agent-trace-merge-meta,
.agent-trace-merge-desc {
  margin: 0;
  font-size: 0.78rem;
  line-height: 1.55;
  color: var(--text-secondary);
}

.agent-trace-merge-meta {
  margin-top: 4px;
  color: var(--text-tertiary);
}

.agent-trace-merge-desc {
  margin-top: 8px;
}

.agent-trace-merge-steps {
  margin: 8px 0 0;
  padding-left: 1.1rem;
  font-size: 0.76rem;
  line-height: 1.6;
  color: var(--text-secondary);
}

.agent-trace-merge-steps li + li {
  margin-top: 4px;
}

.agent-trace-detail-meta,
.agent-trace-detail-score {
  color: var(--text-tertiary);
}

.agent-trace-grade-badge {
  margin-left: auto;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
}

.agent-trace-grade-badge.is-relevant {
  background: rgba(22, 163, 74, 0.12);
  color: #15803d;
}

.agent-trace-grade-badge.is-irrelevant {
  background: rgba(217, 119, 6, 0.12);
  color: #b45309;
}

.agent-trace-grade-reason {
  margin: 8px 0 0;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 0.78rem;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.agent-trace-grade-reason.is-relevant {
  background: rgba(22, 163, 74, 0.1);
  color: #15803d;
}

.agent-trace-grade-reason.is-irrelevant {
  background: rgba(217, 119, 6, 0.1);
  color: #b45309;
}

.agent-trace-grade-reason--muted {
  background: rgba(148, 163, 184, 0.08);
  color: var(--text-tertiary);
  font-style: italic;
}

.agent-trace-grade-preview {
  margin: 8px 0 0;
  padding-top: 8px;
  border-top: 1px dashed var(--border-color);
  font-size: 0.78rem;
  line-height: 1.6;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

.agent-trace-detail-preview,
.agent-trace-detail-reason {
  margin: 6px 0 0;
  font-size: 0.78rem;
  line-height: 1.6;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

.agent-trace-detail-reason--muted {
  color: var(--text-tertiary);
  font-style: italic;
}
</style>
