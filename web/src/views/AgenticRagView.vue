<template>
  <div class="agentic-page">
      <section class="surface-card content-card agentic-card" :class="{ 'agentic-card--kb-open': kbDropdownOpen }">
        <div class="section-heading agentic-section-head">
          <div>
            <h3>智能体检索问答</h3>
            <p>独立端点执行 route → retrieve → grade → rewrite → generate，并展示每一步决策轨迹。</p>
          </div>
          <div class="agentic-head-actions">
            <button class="btn btn-ghost" type="button" @click="selectAllKbs">全选知识库</button>
            <button class="btn btn-ghost" type="button" @click="clearKbSelection">清空选择</button>
          </div>
        </div>

        <div class="agentic-layout">
          <form class="agentic-panel agentic-panel--left agentic-form" @submit.prevent="submitAgenticRag">
            <label class="field">
              <span class="field-label">LLM 模型</span>
              <LlmModelPicker
                v-model="selectedLlmId"
                :models="llmModels"
                :loading="llmModelsLoading"
                :default-model="defaultLlmModel"
                :disabled="agenticStore.running"
                :show-current-hint="false"
              />
            </label>

            <div class="field kb-multiselect-field">
              <span class="field-label">知识库上下文</span>
              <div v-if="knowledgeBases.length === 0" class="kb-multi-empty">暂无知识库，请先在「知识库管理」中创建。</div>
              <KnowledgeBaseMultiSelect
                v-else
                v-model="selectedKbIds"
                v-model:open="kbDropdownOpen"
                :knowledge-bases="knowledgeBases"
              />
              <p v-if="knowledgeBases.length > 0" class="kb-multi-summary">已选 {{ selectedKbIds.length }} 个</p>
            </div>

            <label class="field">
              <span class="field-label">问题</span>
              <textarea
                v-model="question"
                class="textarea"
                rows="5"
                placeholder="输入你的问题"
              />
            </label>

            <div class="agentic-tuning">
              <label class="field">
                <span class="field-label">最大迭代轮数</span>
                <input v-model.number="maxIterations" class="input" type="number" min="1" max="5" />
              </label>
              <label class="field">
                <span class="field-label">最少相关片段</span>
                <input v-model.number="minRelevantDocs" class="input" type="number" min="1" max="10" />
              </label>
            </div>

            <RetrievalConfigForm v-model="searchForm" />

            <div class="agentic-submit-row">
              <button v-if="agenticStore.running" class="btn btn-secondary" type="button" @click="agenticStore.stop">
                停止
              </button>
              <button class="btn btn-primary" type="submit" :disabled="agenticStore.running || !canSubmit">
                {{ agenticStore.running ? '执行中...' : '开始智能检索' }}
              </button>
            </div>
          </form>

          <div class="agentic-panel agentic-panel--right">
            <div class="agentic-result-head">
              <div>
                <h4>答案与决策轨迹</h4>
                <p v-if="!showTracePanel && !agenticStore.answer && !agenticStore.error">
                  选择知识库并输入问题后，可查看每一步智能体决策。
                </p>
              </div>
              <div class="agentic-result-meta">
                <span v-if="agenticStore.routeDecision" class="chip chip-brand">
                  {{ routeDecisionLabel(agenticStore.routeDecision) }}
                </span>
                <span v-if="agenticStore.iterations" class="chip">{{ agenticStore.iterations }} 轮检索</span>
                <span v-if="agenticStore.citations.length" class="chip">
                  {{ agenticStore.citations.length }} 条引用
                </span>
                <span v-if="effectiveModelLabel" class="chip">{{ effectiveModelLabel }}</span>
              </div>
            </div>

            <div v-if="showTracePanel" class="agentic-trace">
              <h5>决策轨迹</h5>
              <div v-if="agenticStore.trace.length === 0" class="trace-empty">
                {{ agenticStore.running ? '正在执行，等待轨迹…' : '尚未产生轨迹。' }}
              </div>
              <ol v-else class="trace-list">
                <li v-for="(item, index) in agenticStore.trace" :key="`${item.step}-${index}`" class="trace-item">
                  <div class="trace-dot"></div>
                  <div class="trace-body">
                    <div class="trace-title">
                      <strong>{{ stepLabel(item.step) }}</strong>
                      <span v-if="item.elapsed_ms != null">{{ item.elapsed_ms }} ms</span>
                    </div>
                    <p>{{ traceSummary(item) }}</p>
                  </div>
                </li>
              </ol>
            </div>

            <div v-if="agenticStore.error" class="status-box error">{{ agenticStore.error }}</div>

            <div v-if="agenticStore.answer" class="agentic-answer-card">
              <div class="agentic-answer markdown-body chat-markdown-body" v-html="answerHtml" />
            </div>

            <div v-if="agenticStore.citations.length" class="agentic-citations">
              <h5>引用来源</h5>
              <div v-for="cite in agenticStore.citations" :key="cite.ref" class="citation-row">
                <strong>[{{ cite.ref }}] {{ cite.document_name }}</strong>
                <span v-if="cite.score != null">Score {{ formatScore(cite.score) }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { knowledgeBaseApi, type KnowledgeBase } from '../api/knowledge-base'
import {
  defaultModelApi,
  getErrorMessage as getModelErrorMessage,
  modelApi,
  type DefaultModelOption,
  type ModelItem,
} from '../api/model-management'
import LlmModelPicker from '../components/knowledge-base/LlmModelPicker.vue'
import KnowledgeBaseMultiSelect from '../components/knowledge-base/KnowledgeBaseMultiSelect.vue'
import RetrievalConfigForm from '../components/knowledge-base/RetrievalConfigForm.vue'
import { defaultRetrievalFormState, retrievalFormFromKnowledgeBase, type RetrievalFormState } from '../components/knowledge-base/retrieval-form'
import { renderAssistantMessageHtml } from '../lib/chatMarkdown'
import { loadRetrievalKbPreference, saveRetrievalKbPreference } from '../lib/retrieval-kb-preference'
import { useAgenticRagStore } from '../stores/agentic-rag'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const agenticStore = useAgenticRagStore()

const knowledgeBases = ref<KnowledgeBase[]>([])
const kbListReady = ref(false)
const selectedKbIds = ref<number[]>([])
const kbDropdownOpen = ref(false)
const question = ref('新生儿医保办理需要哪些材料？')
const searchForm = ref<RetrievalFormState>(defaultRetrievalFormState())
const maxIterations = ref(2)
const minRelevantDocs = ref(1)
const llmModels = ref<ModelItem[]>([])
const llmModelsLoading = ref(false)
const defaultLlmModel = ref<DefaultModelOption | null>(null)
const selectedLlmId = ref<number | null>(null)

const effectiveModelLabel = computed(() => {
  if (selectedLlmId.value != null) {
    const picked = llmModels.value.find((model) => model.id === selectedLlmId.value)
    if (picked) {
      return `${picked.model_name}（${picked.provider_name}）`
    }
  }
  if (defaultLlmModel.value) {
    return `${defaultLlmModel.value.model_name}（${defaultLlmModel.value.provider_name}）`
  }
  return ''
})

const canSubmit = computed(
  () =>
    selectedKbIds.value.length > 0 &&
    question.value.trim().length > 0 &&
    !llmModelsLoading.value &&
    (llmModels.value.length > 0 || defaultLlmModel.value != null),
)
const answerHtml = computed(() =>
  renderAssistantMessageHtml(agenticStore.answer, {
    showCitations: true,
    streaming: agenticStore.running,
    citationTitleForRef: (refNum) => {
      const cite = agenticStore.citations.find((row) => row.ref === refNum)
      return cite ? cite.document_name : `引用 ${refNum}`
    },
  }),
)

const showTracePanel = computed(
  () => agenticStore.running || agenticStore.trace.length > 0 || Boolean(agenticStore.answer),
)

function syncKbSelectionFromList() {
  const valid = new Set(knowledgeBases.value.map((k) => k.id))
  selectedKbIds.value = selectedKbIds.value.filter((id) => valid.has(id))
  if (selectedKbIds.value.length === 0) {
    const spaceId = authStore.currentSpace?.id ?? 0
    selectedKbIds.value = loadRetrievalKbPreference(spaceId, authStore.currentSpaceSlug).filter((id) => valid.has(id))
  }
  if (selectedKbIds.value.length === 0 && knowledgeBases.value[0]) {
    selectedKbIds.value = [knowledgeBases.value[0].id]
  }
  const primary = knowledgeBases.value.find((k) => k.id === selectedKbIds.value[0])
  searchForm.value = primary ? retrievalFormFromKnowledgeBase(primary) : defaultRetrievalFormState()
}

async function loadKnowledgeBases() {
  kbListReady.value = false
  knowledgeBases.value = await knowledgeBaseApi.list()
  syncKbSelectionFromList()
  kbListReady.value = true
}

async function loadLlmModels() {
  llmModelsLoading.value = true
  try {
    const [modelsData, defaultsData] = await Promise.all([
      modelApi.getModels({ model_type: 'llm', is_enabled: true, view: 'flat' }),
      defaultModelApi.getDefaults(),
    ])
    llmModels.value = modelsData as ModelItem[]
    defaultLlmModel.value = defaultsData.llm
  } catch (e) {
    console.error(getModelErrorMessage(e, '加载 LLM 列表失败'))
  } finally {
    llmModelsLoading.value = false
  }
}

function selectAllKbs() {
  selectedKbIds.value = knowledgeBases.value.map((k) => k.id)
}

function clearKbSelection() {
  selectedKbIds.value = []
}

async function submitAgenticRag() {
  if (!canSubmit.value) return
  const f = searchForm.value
  await agenticStore.run({
    question: question.value.trim(),
    knowledge_base_ids: [...selectedKbIds.value],
    model_id: selectedLlmId.value ?? undefined,
    top_k: f.top_k,
    mode: f.mode,
    score_threshold: f.score_threshold_enabled ? f.score_threshold : null,
    vector_weight: f.mode === 'hybrid' && f.hybrid_strategy === 'weight' ? f.vector_weight : null,
    fusion_method: f.mode === 'hybrid' && f.hybrid_strategy === 'weight' ? f.fusion_method : null,
    include_image_ocr: f.include_image_ocr,
    max_iterations: maxIterations.value,
    min_relevant_docs: minRelevantDocs.value,
  })
}

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

function traceSummary(item: Record<string, unknown>) {
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

function formatScore(value: number) {
  return Number.isFinite(value) ? value.toFixed(3) : '—'
}

onMounted(() => {
  void Promise.all([loadKnowledgeBases(), loadLlmModels()])
})

watch(
  selectedKbIds,
  (ids) => {
    if (!kbListReady.value) return
    const spaceId = authStore.currentSpace?.id ?? 0
    saveRetrievalKbPreference(spaceId, authStore.currentSpaceSlug, ids)
  },
  { deep: true },
)
</script>

<style scoped>
.agentic-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.agentic-section-head,
.agentic-result-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.agentic-head-actions,
.agentic-result-meta,
.agentic-submit-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.agentic-card {
  padding: 0;
  overflow: hidden;
}

.agentic-card--kb-open {
  position: relative;
  z-index: 40;
  overflow: visible;
}

.agentic-card .section-heading {
  padding: 20px 22px 0;
}

.agentic-layout {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.25fr);
  min-height: 620px;
  border-top: 1px solid var(--border-color);
}

.agentic-panel {
  padding: 20px 22px 22px;
  min-width: 0;
}

.agentic-panel--left {
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
}

.agentic-panel--right {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 16px;
  background: var(--bg-primary);
}

.agentic-trace {
  flex-shrink: 0;
}

.agentic-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.agentic-tuning {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
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

.agentic-answer-card,
.agentic-citations,
.agentic-trace {
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-secondary);
  padding: 16px;
}

.agentic-answer {
  color: var(--text-primary);
  line-height: 1.75;
}

.agentic-citations h5,
.agentic-trace h5 {
  margin: 0 0 12px;
  font-size: 0.95rem;
}

.citation-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.citation-row:first-of-type {
  border-top: 0;
}

.trace-empty {
  color: var(--text-tertiary);
  font-size: 0.9rem;
}

.trace-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
}

.trace-item {
  display: grid;
  grid-template-columns: 14px 1fr;
  gap: 10px;
}

.trace-dot {
  width: 10px;
  height: 10px;
  margin-top: 6px;
  border-radius: 999px;
  background: var(--brand-primary);
  box-shadow: 0 0 0 5px rgba(37, 99, 235, 0.12);
}

.trace-body {
  min-width: 0;
}

.trace-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-primary);
}

.trace-title span,
.trace-body p {
  color: var(--text-tertiary);
  font-size: 0.85rem;
}

.trace-body p {
  margin: 4px 0 0;
  line-height: 1.6;
}

@media (max-width: 1080px) {
  .agentic-layout {
    grid-template-columns: 1fr;
  }

  .agentic-panel--left {
    border-right: none;
    border-bottom: 1px solid var(--border-color);
  }
}
</style>
