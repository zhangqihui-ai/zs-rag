<template>
  <Layout>
    <div class="page-shell retrieval-view">
      <PageHeader
        eyebrow="Retrieval Lab"
        title="知识检索工作台"
        description="从真实知识库发起 vector / keyword / hybrid 检索，观察引用来源、分数分布与召回效果。"
      >
        <template #meta>
          <span class="chip chip-brand">真实联调</span>
          <span class="chip">{{ retrievalModeLabelMap[mode] }}</span>
          <span class="chip">Top {{ topK }}</span>
        </template>
        <template #actions>
          <button class="btn btn-ghost" type="button" @click="resetFilters">
            <AppIcon name="refresh" :size="16" />
            重置
          </button>
        </template>
      </PageHeader>

      <div class="page-grid retrieval-layout">
        <section class="surface-card search-panel">
          <div class="section-heading">
            <div>
              <h3>检索输入与策略</h3>
              <p>选择目标知识库，输入查询问题，切换不同检索模式进行对比。</p>
            </div>
          </div>

          <div class="form-grid">
            <div class="form-grid two">
              <label class="field">
                <span class="field-label">知识库</span>
                <select v-model.number="selectedKbId" class="select">
                  <option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">
                    {{ kb.name }}
                  </option>
                </select>
              </label>

              <label class="field">
                <span class="field-label">检索模式</span>
                <select v-model="mode" class="select">
                  <option value="hybrid">Hybrid</option>
                  <option value="vector">Vector</option>
                  <option value="keyword">Keyword</option>
                </select>
              </label>
            </div>

            <label class="field">
              <span class="field-label">检索问题</span>
              <textarea
                v-model.trim="query"
                class="textarea"
                rows="5"
                placeholder="例如：如何为企业空间配置默认 embedding 模型，并打通知识库上传、索引与检索链路？"
              />
            </label>

            <div class="form-grid three">
              <label class="field">
                <span class="field-label">召回数量</span>
                <input v-model.number="topK" class="input" type="number" min="1" max="20" />
              </label>
              <label class="field">
                <span class="field-label">相似度阈值</span>
                <input v-model.number="scoreThreshold" class="input" type="number" min="0" max="1" step="0.01" placeholder="可选" />
              </label>
              <label class="field">
                <span class="field-label">文档范围</span>
                <input v-model.trim="documentIdsInput" class="input" type="text" placeholder="如 1,2,3；可选" />
              </label>
            </div>

            <label v-if="mode === 'hybrid'" class="field">
              <span class="field-label">向量权重（混合） {{ vectorWeight.toFixed(2) }} / 全文 {{ (1 - vectorWeight).toFixed(2) }}</span>
              <input v-model.number="vectorWeight" class="input-range" type="range" min="0" max="1" step="0.01" />
            </label>
          </div>

          <div class="preset-group">
            <button v-for="preset in presets" :key="preset" class="chip preset-chip" type="button" @click="applyPreset(preset)">
              {{ preset }}
            </button>
          </div>

          <div v-if="searchError" class="status-box error">{{ searchError }}</div>

          <div class="action-row">
            <button class="btn btn-primary" type="button" :disabled="searching || !selectedKbId" @click="submitSearch">
              {{ searching ? '检索中...' : '开始检索' }}
            </button>
          </div>
        </section>

        <section class="surface-card result-panel">
          <div class="section-heading">
            <div>
              <h3>检索结果</h3>
              <p>{{ resultSummary }}</p>
            </div>
            <span class="status-pill info">{{ results.length }} 条结果</span>
          </div>

          <EmptyState
            v-if="!searching && results.length === 0"
            title="暂无检索结果"
            description="请输入查询问题并执行检索，结果会展示真实 chunk 内容与引用来源。"
          >
            <template #icon>
              <AppIcon name="retrieval" :size="20" />
            </template>
          </EmptyState>

          <div v-else-if="searching" class="loading-skeleton result-skeleton"></div>

          <div v-else class="result-list">
            <article v-for="item in results" :key="item.chunk_uid" class="result-card">
              <div class="result-card-header">
                <div>
                  <h4>{{ item.document_name }}</h4>
                  <p>
                    Chunk #{{ item.chunk_index }}
                    <span v-if="item.citation.page_no"> · 第 {{ item.citation.page_no }} 页</span>
                  </p>
                </div>
                <span :class="['status-pill', item.score >= 0.85 ? 'success' : item.score >= 0.6 ? 'info' : 'warning']">
                  得分 {{ item.score.toFixed(3) }}
                </span>
              </div>

              <div class="score-bar">
                <span class="score-bar-fill" :style="{ width: `${Math.min(item.score * 100, 100)}%` }"></span>
              </div>

              <p class="result-summary">{{ item.content }}</p>

              <div class="result-meta">
                <span class="chip">{{ retrievalModeLabelMap[responseMode] }}</span>
                <span class="chip" v-if="item.vector_score !== null">向量 {{ item.vector_score.toFixed(3) }}</span>
                <span class="chip" v-if="item.keyword_score !== null">关键词 {{ item.keyword_score.toFixed(3) }}</span>
                <span class="chip" v-if="item.metadata?.heading_path">{{ String(item.metadata.heading_path) }}</span>
              </div>
            </article>
          </div>
        </section>

        <aside class="side-panel">
          <section class="surface-card">
            <div class="section-heading compact-heading">
              <div>
                <h4>检索质量指标</h4>
                <p>基于当前真实检索结果计算。</p>
              </div>
            </div>
            <div class="quality-list">
              <div class="quality-item">
                <strong>平均得分</strong>
                <span>{{ averageScore }}</span>
              </div>
              <div class="quality-item">
                <strong>高相关结果</strong>
                <span>{{ highConfidenceCount }} 条</span>
              </div>
              <div class="quality-item">
                <strong>当前知识库</strong>
                <span>{{ selectedKnowledgeBase?.name || '未选择' }}</span>
              </div>
            </div>
          </section>

          <section class="surface-card">
            <div class="section-heading compact-heading">
              <div>
                <h4>引用与排查建议</h4>
                <p>用于快速判断召回是否符合预期。</p>
              </div>
            </div>
            <div class="guideline-list">
              <div class="guideline-item">
                <AppIcon name="sliders" :size="16" />
                <span>优先观察高分结果是否来自正确文档，再判断是否需要调整 chunk 大小或 overlap。</span>
              </div>
              <div class="guideline-item">
                <AppIcon name="knowledge" :size="16" />
                <span>如果关键词模式结果为空，优先确认文档是否已完成 indexed 状态并成功生成 chunk。</span>
              </div>
              <div class="guideline-item">
                <AppIcon name="status" :size="16" />
                <span>若向量检索报错，请优先检查默认 embedding 模型、Milvus 配置维度与文档索引状态。</span>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  </Layout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  getKnowledgeBaseErrorMessage,
  knowledgeBaseApi,
  type KnowledgeBase,
  type KnowledgeSearchResponse,
  type RetrievalMode,
} from '../api/knowledge-base'
import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import Layout from '../components/Layout.vue'
import PageHeader from '../components/PageHeader.vue'

const retrievalModeLabelMap: Record<RetrievalMode, string> = {
  hybrid: '混合检索',
  vector: '向量检索',
  keyword: '关键词检索',
}

const presets = [
  '如何配置默认 embedding 模型',
  'Milvus 维度不匹配如何处理',
  '知识库上传后索引流程',
  '关键词检索与混合检索的区别',
]

const knowledgeBases = ref<KnowledgeBase[]>([])
const selectedKbId = ref<number | null>(null)
const query = ref('如何为企业空间配置默认 embedding 模型，并打通知识库上传、索引与检索链路？')
const mode = ref<RetrievalMode>('hybrid')
const responseMode = ref<RetrievalMode>('hybrid')
const topK = ref(5)
const scoreThreshold = ref<number | undefined>(undefined)
/** 混合检索：向量分支权重（0~1），缺省 0.5 */
const vectorWeight = ref(0.5)
const documentIdsInput = ref('')
const results = ref<KnowledgeSearchResponse['results']>([])
const searching = ref(false)
const searchError = ref('')

const selectedKnowledgeBase = computed(() => knowledgeBases.value.find((item) => item.id === selectedKbId.value) || null)
const averageScore = computed(() => {
  if (!results.value.length) {
    return '0.000'
  }
  const total = results.value.reduce((sum, item) => sum + item.score, 0)
  return (total / results.value.length).toFixed(3)
})
const highConfidenceCount = computed(() => results.value.filter((item) => item.score >= 0.85).length)
const resultSummary = computed(() => {
  if (!selectedKnowledgeBase.value) {
    return '请选择一个知识库并发起真实检索。'
  }
  return `当前知识库：${selectedKnowledgeBase.value.name} · 模式：${retrievalModeLabelMap[responseMode.value]}。`
})

const parseDocumentIds = () => {
  return documentIdsInput.value
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item) && item > 0)
}

const loadKnowledgeBases = async () => {
  try {
    const data = await knowledgeBaseApi.list()
    knowledgeBases.value = data
    if (!selectedKbId.value && data.length > 0) {
      selectedKbId.value = data[0].id
    }
  } catch (value) {
    searchError.value = getKnowledgeBaseErrorMessage(value, '加载知识库列表失败')
  }
}

const submitSearch = async () => {
  if (!selectedKbId.value) {
    searchError.value = '请先选择知识库'
    return
  }
  if (!query.value.trim()) {
    searchError.value = '请输入检索问题'
    return
  }
  searching.value = true
  searchError.value = ''
  try {
    const body: Parameters<typeof knowledgeBaseApi.search>[1] = {
      query: query.value.trim(),
      mode: mode.value,
      top_k: topK.value,
      score_threshold: scoreThreshold.value,
      document_ids: parseDocumentIds().length ? parseDocumentIds() : undefined,
    }
    if (mode.value === 'hybrid') {
      body.vector_weight = vectorWeight.value
    }
    const response = await knowledgeBaseApi.search(selectedKbId.value, body)
    responseMode.value = response.mode
    results.value = response.results
  } catch (value) {
    results.value = []
    searchError.value = getKnowledgeBaseErrorMessage(value, '执行检索失败')
  } finally {
    searching.value = false
  }
}

const applyPreset = (preset: string) => {
  query.value = preset
}

const resetFilters = () => {
  query.value = ''
  mode.value = 'hybrid'
  responseMode.value = 'hybrid'
  topK.value = 5
  scoreThreshold.value = undefined
  vectorWeight.value = 0.5
  documentIdsInput.value = ''
  results.value = []
  searchError.value = ''
}

onMounted(async () => {
  await loadKnowledgeBases()
})
</script>

<style scoped>
.retrieval-layout {
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.65fr);
  align-items: start;
}

.search-panel,
.result-panel,
.side-panel {
  height: 100%;
}

.search-panel,
.result-panel,
.side-panel {
  display: grid;
  gap: 18px;
}

.input-range {
  width: 100%;
  height: 8px;
  accent-color: var(--brand-secondary);
}

.preset-group,
.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.preset-chip {
  border: none;
  cursor: pointer;
}

.result-list,
.result-meta,
.guideline-list,
.quality-list {
  display: grid;
  gap: 12px;
}

.result-card,
.quality-item,
.guideline-item {
  display: grid;
  gap: 14px;
  padding: 18px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: var(--bg-tertiary);
}

.result-card-header,
.quality-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.result-card-header h4,
.quality-item strong {
  margin: 0;
  color: var(--text-primary);
}

.result-card-header p,
.guideline-item span,
.result-summary,
.quality-item span {
  color: var(--text-secondary);
}

.result-card-header p {
  margin: 6px 0 0;
}

.result-summary {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.75;
}

.guideline-item {
  grid-template-columns: auto 1fr;
  align-items: start;
}

.score-bar {
  position: relative;
  height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.22);
  overflow: hidden;
}

.score-bar-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--brand-primary) 0%, var(--brand-secondary) 100%);
}

.result-skeleton {
  min-height: 240px;
}

@media (max-width: 1180px) {
  .retrieval-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .result-card-header,
  .quality-item {
    flex-direction: column;
  }
}
</style>
