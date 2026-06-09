<template>
  <div class="retrieval-page">
      <section
        class="surface-card content-card retrieval-card"
        :class="{ 'retrieval-card--kb-open': retrievalKbDropdownOpen }"
      >
        <div class="section-heading retrieval-section-head">
          <div>
            <h3>检索测试</h3>
            <p>跨库查询时，经典库与图知识库分别召回后按 Score 合并排序，再取 Top K。</p>
          </div>
          <div class="retrieval-head-actions">
            <button class="btn btn-ghost" type="button" @click="selectAllKbs">全选知识库</button>
            <button class="btn btn-ghost" type="button" @click="clearKbSelection">清空选择</button>
          </div>
        </div>

        <div class="retrieval-layout">
          <form class="retrieval-form retrieval-panel retrieval-panel--left" @submit.prevent="submitSearch">
            <div class="field kb-multi-field kb-multiselect-field">
              <span class="field-label">知识库上下文</span>
              <div v-if="knowledgeBases.length === 0" class="kb-multi-empty">暂无知识库，请先在「知识库管理」中创建。</div>
              <KnowledgeBaseMultiSelect
                v-else
                v-model="selectedKbIds"
                v-model:open="retrievalKbDropdownOpen"
                :knowledge-bases="knowledgeBases"
              />
              <p v-if="knowledgeBases.length > 0" class="kb-multi-summary">已选 {{ selectedKbIds.length }} 个</p>
            </div>

            <div class="retrieval-query-block">
              <label class="field retrieval-search-field">
                <span class="field-label retrieval-query-label">检索问题</span>
                <textarea
                  v-model.trim="searchQuery"
                  class="textarea"
                  rows="4"
                  placeholder="例如：合同审批流程需要哪些材料？"
                />
              </label>
              <div class="retrieval-query-actions">
                <button class="btn btn-primary" type="submit" :disabled="searching || !canSearch">
                  {{ searching ? '检索中...' : '开始检索' }}
                </button>
              </div>
            </div>

            <RetrievalConfigForm v-model="searchForm" />

            <div class="retrieval-submit-row">
              <button class="btn btn-ghost" type="button" :disabled="searching" @click="resetSearchForm">
                重置表单
              </button>
            </div>
          </form>

          <div class="retrieval-panel retrieval-panel--right">
            <div class="retrieval-result-head">
              <div class="retrieval-result-head-title">
                <h4>检索结果</h4>
                <p v-if="!searchResults && !searching && !searchError">
                  选择知识库、输入问题并点击「开始检索」以查看召回片段。
                </p>
              </div>
              <div v-if="searchResults" class="retrieval-result-meta">
                <span class="chip chip-brand">{{ retrievalModeLabelMap[searchResults.mode] }}</span>
                <span class="chip">共 {{ searchResults.total }} 条结果</span>
                <span v-if="searchResults.knowledge_base_ids?.length" class="chip">
                  {{ searchResults.knowledge_base_ids.length }} 个知识库
                </span>
              </div>
            </div>

            <div class="retrieval-result-body">
              <div v-if="searching" class="loading-skeleton document-skeleton" />
              <div v-else-if="searchError" class="status-box error">{{ searchError }}</div>
              <EmptyState
                v-else-if="!searchResults || searchResults.results.length === 0"
                title="暂无检索结果"
                description="请检查是否已选择知识库并输入检索问题。"
                compact
              >
                <template #icon>
                  <AppIcon name="retrieval" :size="18" />
                </template>
              </EmptyState>
              <RetrievalSearchResultList
                v-else
                :results="searchResults.results"
                :mode="searchResults.mode"
              />
            </div>
          </div>
        </div>
      </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import {
  getKnowledgeBaseErrorMessage,
  knowledgeBaseApi,
  type KnowledgeBase,
  type MultiKnowledgeSearchResponse,
  type RetrievalMode,
} from '../api/knowledge-base'
import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import RetrievalConfigForm from '../components/knowledge-base/RetrievalConfigForm.vue'
import RetrievalSearchResultList from '../components/knowledge-base/RetrievalSearchResultList.vue'
import KnowledgeBaseMultiSelect from '../components/knowledge-base/KnowledgeBaseMultiSelect.vue'
import { defaultRetrievalFormState, retrievalFormFromKnowledgeBase, type RetrievalFormState } from '../components/knowledge-base/retrieval-form'
import { loadRetrievalKbPreference, saveRetrievalKbPreference } from '../lib/retrieval-kb-preference'
import { useAuthStore } from '../stores/auth'

const retrievalModeLabelMap: Record<RetrievalMode, string> = {
  hybrid: '混合检索',
  vector: '向量检索',
  keyword: '关键词检索',
}

const authStore = useAuthStore()

const knowledgeBases = ref<KnowledgeBase[]>([])
/** 避免首屏 ref 默认值 [] 同步写穿 localStorage，冲掉已保存的多选 */
const retrievalKbListReady = ref(false)
const selectedKbIds = ref<number[]>([])
const retrievalKbDropdownOpen = ref(false)
const searchQuery = ref('')
const searchForm = ref<RetrievalFormState>(defaultRetrievalFormState())
const searchResults = ref<MultiKnowledgeSearchResponse | null>(null)
const searching = ref(false)
const searchError = ref('')

const canSearch = computed(() => selectedKbIds.value.length > 0 && searchQuery.value.trim().length > 0)

function formatScore(value: number) {
  return Number.isFinite(value) ? value.toFixed(3) : '—'
}

function syncKbSelectionFromList() {
  if (knowledgeBases.value.length === 0) {
    selectedKbIds.value = []
    return
  }
  const valid = new Set(knowledgeBases.value.map((k) => k.id))
  selectedKbIds.value = selectedKbIds.value
    .map((id) => (typeof id === 'string' ? Number(id) : id))
    .filter((id): id is number => Number.isInteger(id) && id > 0 && valid.has(id))

  if (selectedKbIds.value.length === 0) {
    const spaceId = authStore.currentSpace?.id ?? 0
    const fromPref = loadRetrievalKbPreference(spaceId, authStore.currentSpaceSlug)
    selectedKbIds.value = fromPref.filter((id) => valid.has(id))
  }

  if (selectedKbIds.value.length === 0) {
    const first = knowledgeBases.value[0]
    selectedKbIds.value = [first.id]
    searchForm.value = retrievalFormFromKnowledgeBase(first)
    return
  }

  const primary = knowledgeBases.value.find((k) => k.id === selectedKbIds.value[0])
  if (primary) {
    searchForm.value = retrievalFormFromKnowledgeBase(primary)
  }
}

async function loadKnowledgeBases() {
  retrievalKbListReady.value = false
  try {
    const data = await knowledgeBaseApi.list()
    knowledgeBases.value = data
    syncKbSelectionFromList()
    retrievalKbListReady.value = true
  } catch (e) {
    searchError.value = getKnowledgeBaseErrorMessage(e, '加载知识库列表失败')
  }
}

function selectAllKbs() {
  selectedKbIds.value = knowledgeBases.value.map((k) => k.id)
}

function clearKbSelection() {
  selectedKbIds.value = []
}

function resetSearchForm() {
  const first = knowledgeBases.value[0]
  searchForm.value = first ? retrievalFormFromKnowledgeBase(first) : defaultRetrievalFormState()
  searchQuery.value = ''
  searchResults.value = null
  searchError.value = ''
}

async function submitSearch() {
  if (!canSearch.value) {
    searchError.value = !selectedKbIds.value.length ? '请至少选择一个知识库' : '请输入检索问题'
    return
  }
  searching.value = true
  searchError.value = ''
  try {
    const f = searchForm.value
    const payload: Parameters<typeof knowledgeBaseApi.searchMulti>[0] = {
      knowledge_base_ids: [...selectedKbIds.value],
      query: searchQuery.value.trim(),
      mode: f.mode,
      top_k: f.top_k,
      score_threshold: f.score_threshold_enabled ? f.score_threshold : null,
      include_image_ocr: f.include_image_ocr,
    }
    if (f.mode === 'hybrid' && f.hybrid_strategy === 'weight') {
      payload.vector_weight = f.vector_weight
      payload.fusion_method = f.fusion_method
    }
    searchResults.value = await knowledgeBaseApi.searchMulti(payload)
  } catch (e) {
    searchError.value = getKnowledgeBaseErrorMessage(e, '检索失败')
    searchResults.value = null
  } finally {
    searching.value = false
  }
}

onMounted(() => {
  void loadKnowledgeBases()
})

watch(
  selectedKbIds,
  (ids) => {
    if (!retrievalKbListReady.value || knowledgeBases.value.length === 0) {
      return
    }
    const spaceId = authStore.currentSpace?.id ?? 0
    saveRetrievalKbPreference(spaceId, authStore.currentSpaceSlug, ids)
  },
  { deep: true },
)
</script>

<style scoped>
.retrieval-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.retrieval-section-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.retrieval-head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.retrieval-card {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
  overflow: hidden;
}

.retrieval-card.retrieval-card--kb-open {
  overflow: visible;
  z-index: 40;
  position: relative;
}

.retrieval-card.retrieval-card--kb-open :deep(.retrieval-layout) {
  overflow: visible;
}

.retrieval-card.retrieval-card--kb-open :deep(.retrieval-panel--left) {
  overflow: visible;
  z-index: 41;
  position: relative;
}

.retrieval-card .section-heading {
  padding: 20px 22px 0;
}

.retrieval-layout {
  display: grid;
  grid-template-columns: minmax(300px, 1fr) minmax(0, 1.15fr);
  gap: 0;
  align-items: stretch;
  min-height: 520px;
  border-top: 1px solid var(--border-color);
}

.retrieval-panel {
  padding: 20px 22px 22px;
  min-height: 0;
}

.retrieval-panel--left {
  border-right: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.retrieval-panel--right {
  background: var(--bg-primary);
  display: flex;
  flex-direction: column;
  gap: 0;
}

.retrieval-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.retrieval-query-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.retrieval-search-field {
  width: 100%;
}

.retrieval-query-label {
  font-weight: 600;
}

.retrieval-query-actions {
  display: flex;
  justify-content: flex-end;
}

.retrieval-submit-row {
  display: flex;
  justify-content: flex-end;
}

.kb-multi-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kb-multiselect-field {
  position: relative;
  z-index: 1;
}

.kb-multi-empty {
  font-size: 0.9rem;
  color: var(--text-tertiary);
  padding: 12px;
  border-radius: 10px;
  border: 1px dashed var(--border-color);
}

.kb-multi-summary {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.retrieval-result-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.retrieval-result-head-title h4 {
  margin: 0 0 6px;
  font-size: 1rem;
}

.retrieval-result-head-title p {
  margin: 0;
  font-size: 0.88rem;
  color: var(--text-secondary);
}

.retrieval-result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.chip-soft {
  background: rgba(100, 116, 139, 0.18);
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 0.78rem;
}

.retrieval-result-body {
  flex: 1;
  min-height: 280px;
  min-width: 0;
}

.search-result-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.search-result-card {
  padding: 16px 18px;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--bg-tertiary);
}

.search-result-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
}

.search-result-titles {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.search-result-header strong {
  color: var(--text-primary);
}

.search-result-body {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.7;
  color: var(--text-secondary);
  font-size: 0.92rem;
}

.search-result-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  margin-top: 12px;
  font-size: 0.85rem;
  color: var(--text-tertiary);
}

.document-skeleton {
  min-height: 260px;
  border-radius: 12px;
}

@media (max-width: 1024px) {
  .retrieval-layout {
    grid-template-columns: 1fr;
  }

  .retrieval-panel--left {
    border-right: none;
    border-bottom: 1px solid var(--border-color);
  }
}
</style>
