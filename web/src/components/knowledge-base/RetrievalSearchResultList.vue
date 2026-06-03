<template>
  <div class="search-result-list">
    <article
      v-for="result in results"
      :key="resultKey(result)"
      class="search-result-card"
      tabindex="0"
      title="双击查看切片详情"
      @dblclick="openDetail(result)"
      @keydown.enter="openDetail(result)"
    >
      <div class="search-result-header">
        <div class="search-result-titles">
          <strong>{{ result.document_name }}</strong>
          <span v-if="result.knowledge_base_name" class="chip chip-soft">{{ result.knowledge_base_name }}</span>
          <span v-if="isGraphSearchResult(result)" class="search-result-graph-badge">
            <AppIcon name="graph" :size="11" />
            图检索
          </span>
        </div>
        <span class="chip">Score {{ formatSearchScore(result.score) }}</span>
      </div>
      <p class="search-result-body">{{ searchResultPreview(result) }}</p>
      <div class="search-result-meta-row">
        <span>{{ searchResultChunkLabel(result) }}</span>
        <span v-if="searchResultLocationText(result)">{{ searchResultLocationText(result) }}</span>
        <span v-else-if="result.citation.page_no != null">页码 {{ result.citation.page_no }}</span>
        <span v-if="searchResultBlockLabel(result)" class="chip chip-soft chip-mini">{{
          searchResultBlockLabel(result)
        }}</span>
        <span
          v-if="mode === 'hybrid' && (result.vector_score != null || result.keyword_score != null)"
          class="search-result-scores"
        >
          向量 {{ formatSearchScore(result.vector_score ?? 0) }} · 全文
          {{ formatSearchScore(result.keyword_score ?? 0) }}
        </span>
      </div>
      <p class="search-result-hint">双击查看正文、章节位置与入库增强</p>
    </article>

    <RetrievalResultDetailModal
      :open="detailOpen"
      :result="selectedResult"
      :kb-id="detailKbId"
      @close="closeDetail"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import type { KnowledgeSearchResult, RetrievalMode } from '../../api/knowledge-base'
import {
  formatSearchScore,
  isGraphSearchResult,
  searchResultBlockLabel,
  searchResultChunkLabel,
  searchResultLocationText,
  searchResultPreview,
} from '../../lib/retrieval-result-display'
import AppIcon from '../AppIcon.vue'
import RetrievalResultDetailModal from './RetrievalResultDetailModal.vue'

const props = defineProps<{
  results: KnowledgeSearchResult[]
  mode: RetrievalMode
  kbId?: number | null
}>()

const detailOpen = ref(false)
const selectedResult = ref<KnowledgeSearchResult | null>(null)
const detailKbId = ref<number | null>(null)

function resultKey(result: KnowledgeSearchResult) {
  const kb = result.knowledge_base_id ?? props.kbId ?? 0
  return `${kb}:${result.chunk_uid}`
}

function resolveKbId(result: KnowledgeSearchResult) {
  return props.kbId ?? result.knowledge_base_id ?? null
}

function openDetail(result: KnowledgeSearchResult) {
  selectedResult.value = result
  detailKbId.value = resolveKbId(result)
  detailOpen.value = true
}

function closeDetail() {
  detailOpen.value = false
  selectedResult.value = null
}
</script>

<style scoped>
.search-result-list {
  display: grid;
  gap: 14px;
}

.search-result-card {
  padding: 16px 18px;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--bg-primary);
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.search-result-card:hover,
.search-result-card:focus-visible {
  border-color: color-mix(in srgb, var(--brand-primary) 45%, var(--border-color));
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
  outline: none;
}

.search-result-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.search-result-titles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.search-result-body {
  margin: 12px 0 10px;
  color: var(--text-secondary);
  line-height: 1.65;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.search-result-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.search-result-scores {
  margin-left: auto;
}

.search-result-hint {
  margin: 10px 0 0;
  color: var(--text-tertiary);
  font-size: 0.78rem;
}

.chip-mini {
  font-size: 0.74rem;
  padding: 2px 8px;
}

.search-result-graph-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  line-height: 1.5;
  color: #7c3aed;
  background: rgba(168, 85, 247, 0.12);
  border: 1px solid rgba(168, 85, 247, 0.32);
}
</style>
