<template>
  <Layout>
    <div class="page-shell doc-split-page">
      <div v-if="loading" class="surface-card loading-skeleton panel-skeleton"></div>

      <div v-else-if="error" class="surface-card error-panel">
        <div>
          <h3>无法打开文档</h3>
          <p>{{ error }}</p>
        </div>
        <div class="action-row">
          <router-link :to="{ name: 'knowledge-base-detail', params: { id: kbId } }" class="btn btn-ghost">
            返回知识库
          </router-link>
        </div>
      </div>

      <template v-else-if="document && knowledgeBase">
        <div ref="docSplitRootRef" class="doc-split-main">
          <div class="doc-split-topbar">
            <nav class="doc-split-breadcrumb" aria-label="面包屑">
              <router-link to="/knowledge-bases">知识库</router-link>
              <span class="doc-split-bc-sep">/</span>
              <router-link :to="{ name: 'knowledge-base-detail', params: { id: kbId } }">{{ knowledgeBase.name }}</router-link>
              <span class="doc-split-bc-sep">/</span>
              <span class="doc-split-bc-current">{{ document.document_name }}</span>
            </nav>
            <button type="button" class="btn btn-ghost doc-split-fs-btn" @click="toggleDocSplitFullscreen">
              <AppIcon :name="isDocSplitFullscreen ? 'fullscreen-exit' : 'fullscreen'" :size="16" />
              {{ isDocSplitFullscreen ? '退出全屏' : '全屏' }}
            </button>
          </div>

          <div class="doc-split-grid">
          <section class="surface-card doc-split-pane doc-split-original">
            <header class="doc-split-pane-head">
              <h2 class="doc-split-title">{{ document.file_name }}</h2>
              <p class="doc-split-meta">
                <span>大小：{{ formatFileSize(document.file_size) }}</span>
                <span>上传时间：{{ formatDate(document.created_at) }}</span>
              </p>
            </header>
            <DocumentOriginalPreview
              :kb-id="kbId"
              :document-id="document.id"
              :file-name="document.file_name"
              :file-ext="document.file_ext"
              :mime-type="document.mime_type"
            />
          </section>

          <section class="surface-card doc-split-pane doc-split-chunks">
            <header class="doc-split-pane-head doc-split-chunks-head">
              <div>
                <h2 class="doc-split-title">切片结果</h2>
                <p class="doc-split-sub">将用于嵌入和召回的切片段落</p>
              </div>
              <div class="doc-split-chunks-toolbar">
                <div class="doc-split-tabs" role="tablist">
                  <button
                    type="button"
                    role="tab"
                    :class="['doc-split-tab', { active: chunkDisplayMode === 'full' }]"
                    @click="chunkDisplayMode = 'full'"
                  >
                    全文
                  </button>
                  <button
                    type="button"
                    role="tab"
                    :class="['doc-split-tab', { active: chunkDisplayMode === 'preview' }]"
                    @click="chunkDisplayMode = 'preview'"
                  >
                    省略
                  </button>
                </div>
                <label class="doc-split-search">
                  <AppIcon name="search" class="doc-split-search-icon" :size="16" />
                  <input
                    v-model.trim="chunkKeywordInput"
                    class="input doc-split-search-input"
                    type="search"
                    placeholder="搜索切片正文"
                    @keydown.enter.prevent="applyChunkKeyword"
                  />
                </label>
              </div>
            </header>

            <div v-if="!hasChunksAvailable" class="doc-split-empty">
              <p v-if="document.status === 'indexed' && document.chunk_count === 0">暂无切片数据。</p>
              <p v-else>请先完成「开始解析」并等待索引完成后再查看切片。</p>
            </div>

            <template v-else>
              <div v-if="chunksLoading" class="loading-skeleton document-skeleton"></div>
              <div v-else-if="chunksError" class="status-box error">{{ chunksError }}</div>
              <div v-else class="doc-chunk-list">
                <article v-for="chunk in chunkItems" :key="chunk.id" class="doc-chunk-card">
                  <div class="doc-chunk-card-head">
                    <AppIcon name="grip" class="doc-chunk-grip" :size="16" />
                    <div class="doc-chunk-head-main">
                      <span class="doc-chunk-title-line"
                        >Chunk-{{ chunk.chunk_index + 1 }} · {{ chunkCharCount(chunk) }} 字符</span
                      >
                      <div class="doc-chunk-head-badges">
                        <span class="doc-chunk-kind">{{ chunkKindLabel(chunk) }}</span>
                        <span
                          :class="['doc-chunk-vec', chunk.vector_status === 'indexed' ? 'indexed' : 'pending']"
                        >
                          {{ chunk.vector_status === 'indexed' ? '已向量化' : '待向量' }}
                        </span>
                      </div>
                    </div>
                  </div>
                  <p class="doc-chunk-body">{{ chunkDisplayText(chunk) }}</p>
                </article>
              </div>

              <footer v-if="chunkTotal > 0" class="doc-split-pagination">
                <span class="doc-split-total">共 {{ chunkTotal }} 条</span>
                <div class="doc-split-page-controls">
                  <button
                    type="button"
                    class="btn btn-ghost btn-row-compact"
                    :disabled="chunkPage <= 1"
                    @click="chunkPage -= 1"
                  >
                    上一页
                  </button>
                  <span class="doc-split-page-num">{{ chunkPage }} / {{ chunkTotalPages }}</span>
                  <button
                    type="button"
                    class="btn btn-ghost btn-row-compact"
                    :disabled="chunkPage >= chunkTotalPages"
                    @click="chunkPage += 1"
                  >
                    下一页
                  </button>
                  <select v-model.number="chunkPageSize" class="select doc-split-page-size">
                    <option :value="20">20 条/页</option>
                    <option :value="50">50 条/页</option>
                    <option :value="100">100 条/页</option>
                  </select>
                </div>
              </footer>
            </template>
          </section>
        </div>
        </div>
      </template>
    </div>
  </Layout>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import {
  getKnowledgeBaseErrorMessage,
  knowledgeBaseApi,
  type KnowledgeBase,
  type KnowledgeChunk,
  type KnowledgeDocument,
} from '../api/knowledge-base'
import AppIcon from '../components/AppIcon.vue'
import DocumentOriginalPreview from '../components/DocumentOriginalPreview.vue'
import Layout from '../components/Layout.vue'

const route = useRoute()

const kbId = computed(() => Number(route.params.kbId))
const docId = computed(() => Number(route.params.docId))

const loading = ref(true)
const error = ref('')
const knowledgeBase = ref<KnowledgeBase | null>(null)
const document = ref<KnowledgeDocument | null>(null)

const chunksLoading = ref(false)
const chunksError = ref('')
const chunkItems = ref<KnowledgeChunk[]>([])
const chunkTotal = ref(0)
const chunkPage = ref(1)
const chunkPageSize = ref(50)
const chunkKeyword = ref('')
const chunkKeywordInput = ref('')
const chunkDisplayMode = ref<'full' | 'preview'>('full')

const docSplitRootRef = ref<HTMLElement | null>(null)
const isDocSplitFullscreen = ref(false)

function syncDocSplitFullscreen() {
  const doc = window.document
  const fs =
    doc.fullscreenElement ||
    (doc as Document & { webkitFullscreenElement?: Element | null }).webkitFullscreenElement
  isDocSplitFullscreen.value = fs === docSplitRootRef.value
}

async function toggleDocSplitFullscreen() {
  const el = docSplitRootRef.value
  if (!el) {
    return
  }
  const doc = window.document
  try {
    const fs =
      doc.fullscreenElement ||
      (doc as Document & { webkitFullscreenElement?: Element | null }).webkitFullscreenElement
    if (!fs) {
      const req =
        el.requestFullscreen?.bind(el) ||
        (el as HTMLElement & { webkitRequestFullscreen?: () => void }).webkitRequestFullscreen?.bind(el)
      if (req) {
        await Promise.resolve(req())
      }
    } else {
      const exit =
        doc.exitFullscreen?.bind(doc) ||
        (doc as Document & { webkitExitFullscreen?: () => void }).webkitExitFullscreen?.bind(doc)
      if (exit) {
        await Promise.resolve(exit())
      }
    }
  } catch {
    /* 浏览器拒绝全屏或不支持 */
  }
}

onMounted(() => {
  const doc = window.document
  doc.addEventListener('fullscreenchange', syncDocSplitFullscreen)
  doc.addEventListener('webkitfullscreenchange', syncDocSplitFullscreen)
})

onUnmounted(() => {
  const doc = window.document
  doc.removeEventListener('fullscreenchange', syncDocSplitFullscreen)
  doc.removeEventListener('webkitfullscreenchange', syncDocSplitFullscreen)
})

const hasChunksAvailable = computed(() => {
  const d = document.value
  if (!d) {
    return false
  }
  return d.status === 'indexed' && d.chunk_count > 0
})

const chunkTotalPages = computed(() => Math.max(1, Math.ceil(chunkTotal.value / chunkPageSize.value)))

function formatDate(value: string) {
  return new Date(value).toLocaleString('zh-CN')
}

function formatFileSize(value: number | null) {
  if (!value) {
    return '0 B'
  }
  if (value < 1024) {
    return `${value} B`
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function chunkKindLabel(chunk: KnowledgeChunk): string {
  const m = chunk.metadata
  if (m && typeof m === 'object') {
    const block = (m as { block?: string }).block
    if (block === 'table') {
      return '表格'
    }
    if (block === 'document_preamble') {
      return '文前'
    }
  }
  return '文本'
}

function chunkCharCount(chunk: KnowledgeChunk): number {
  if (typeof chunk.char_count === 'number' && chunk.char_count >= 0) {
    return chunk.char_count
  }
  return [...chunk.content].length
}

function chunkDisplayText(chunk: KnowledgeChunk): string {
  if (chunkDisplayMode.value === 'preview') {
    const prev = chunk.content_preview?.trim()
    if (prev) {
      return prev
    }
    const t = chunk.content
    return t.length > 400 ? `${t.slice(0, 400)}…` : t
  }
  return chunk.content
}

function applyChunkKeyword() {
  chunkKeyword.value = chunkKeywordInput.value
  chunkPage.value = 1
}

watch(chunkPage, () => {
  void loadChunks()
})

watch(chunkPageSize, () => {
  chunkPage.value = 1
  void loadChunks()
})

watch(chunkKeyword, () => {
  void loadChunks()
})

let keywordDebounce: ReturnType<typeof setTimeout> | null = null
watch(chunkKeywordInput, () => {
  if (keywordDebounce) {
    clearTimeout(keywordDebounce)
  }
  keywordDebounce = setTimeout(() => {
    keywordDebounce = null
    const next = chunkKeywordInput.value.trim()
    if (next !== chunkKeyword.value) {
      chunkKeyword.value = next
      chunkPage.value = 1
    }
  }, 400)
})

async function loadPage() {
  if (Number.isNaN(kbId.value) || Number.isNaN(docId.value)) {
    error.value = '无效的链接'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    knowledgeBase.value = await knowledgeBaseApi.get(kbId.value)
    document.value = await knowledgeBaseApi.getDocument(kbId.value, docId.value)
    if (hasChunksAvailable.value) {
      await loadChunks()
    }
  } catch (value) {
    error.value = getKnowledgeBaseErrorMessage(value, '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadChunks() {
  if (!document.value || !hasChunksAvailable.value) {
    return
  }
  chunksLoading.value = true
  chunksError.value = ''
  try {
    const data = await knowledgeBaseApi.listChunks(kbId.value, docId.value, {
      page: chunkPage.value,
      page_size: chunkPageSize.value,
      keyword: chunkKeyword.value || undefined,
    })
    chunkItems.value = data.items
    chunkTotal.value = data.total
  } catch (value) {
    chunksError.value = getKnowledgeBaseErrorMessage(value, '加载切片失败')
    chunkItems.value = []
    chunkTotal.value = 0
  } finally {
    chunksLoading.value = false
  }
}

watch(
  () => [route.params.kbId, route.params.docId],
  () => {
    chunkPage.value = 1
    chunkKeyword.value = ''
    chunkKeywordInput.value = ''
    chunkItems.value = []
    chunkTotal.value = 0
    chunksError.value = ''
    void loadPage()
  },
  { immediate: true },
)
</script>

<style scoped>
.doc-split-page {
  max-width: 1600px;
  margin: 0 auto;
}

.doc-split-main {
  min-width: 0;
}

.doc-split-main:fullscreen {
  max-width: none;
  margin: 0;
  padding: 16px 20px 20px;
  box-sizing: border-box;
  min-height: 100vh;
  overflow: auto;
  background: var(--bg-primary);
}

.doc-split-main:fullscreen .doc-split-grid {
  min-height: min(calc(100vh - 120px), 2000px);
}

.doc-split-topbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.doc-split-fs-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  padding: 6px 12px;
}

.doc-split-breadcrumb {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
  font-size: 0.88rem;
  color: var(--text-secondary);
}

.doc-split-breadcrumb a {
  color: var(--brand-primary);
  text-decoration: none;
}

.doc-split-breadcrumb a:hover {
  text-decoration: underline;
}

.doc-split-bc-sep {
  opacity: 0.6;
}

.doc-split-bc-current {
  color: var(--text-primary);
  font-weight: 600;
  max-width: min(480px, 100%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-split-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

@media (max-width: 1100px) {
  .doc-split-grid {
    grid-template-columns: 1fr;
  }
}

.doc-split-pane {
  padding: 20px 22px;
  min-width: 0;
}

.doc-split-pane-head {
  margin-bottom: 14px;
}

.doc-split-title {
  margin: 0 0 6px;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text-primary);
  word-break: break-word;
}

.doc-split-meta {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.doc-split-sub {
  margin: 4px 0 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.doc-split-chunks-head {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.doc-split-chunks-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.doc-split-tabs {
  display: inline-flex;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  overflow: hidden;
  background: var(--bg-tertiary);
}

.doc-split-tab {
  padding: 6px 14px;
  font-size: 0.8rem;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.doc-split-tab.active {
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-weight: 600;
}

.doc-split-search {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 160px;
  max-width: 320px;
  padding: 0 10px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.doc-split-search-input {
  border: none;
  background: transparent;
  flex: 1;
  min-width: 0;
  padding: 8px 0;
  font-size: 0.85rem;
}

.doc-split-search-input:focus {
  outline: none;
}

.doc-split-empty {
  padding: 32px 12px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.doc-chunk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: min(72vh, 720px);
  overflow: auto;
  padding-right: 4px;
}

.doc-chunk-card {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.doc-chunk-card-head {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.doc-chunk-grip {
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--text-tertiary);
  opacity: 0.55;
}

.doc-chunk-head-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  justify-content: space-between;
}

.doc-chunk-title-line {
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--text-tertiary);
  letter-spacing: 0.01em;
}

.doc-chunk-head-badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.doc-chunk-kind {
  padding: 2px 8px;
  border-radius: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.doc-chunk-vec {
  margin-left: auto;
  padding: 2px 8px;
  border-radius: 8px;
  font-size: 0.72rem;
}

.doc-chunk-vec.indexed {
  background: var(--success-soft);
  color: var(--success-color);
}

.doc-chunk-vec.pending {
  background: var(--bg-secondary);
  color: var(--text-tertiary);
}

.doc-chunk-body {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.55;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.doc-split-pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--border-color);
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.doc-split-page-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.doc-split-page-num {
  min-width: 72px;
  text-align: center;
}

.doc-split-page-size {
  font-size: 0.78rem;
  padding: 4px 8px;
}
</style>
