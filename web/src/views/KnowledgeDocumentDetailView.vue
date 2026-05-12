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
            <div class="doc-split-pane-body">
              <DocumentPdfMineruLayout
                v-if="showPdfMineruSync"
                ref="pdfMineruLayoutRef"
                :kb-id="kbId"
                :document-id="document.id"
                :items="mineruContentList"
                v-model="selectedMineruBlockIndex"
                @page-change="onPdfMineruPageChange"
              />
              <DocumentOriginalPreview
                v-else
                :kb-id="kbId"
                :document-id="document.id"
                :file-name="document.file_name"
                :file-ext="document.file_ext"
                :mime-type="document.mime_type"
              />
            </div>
          </section>

          <section class="surface-card doc-split-pane doc-split-chunks">
            <header class="doc-split-pane-head doc-split-chunks-head">
              <div class="doc-split-chunks-head-top">
                <div class="doc-split-chunks-head-text">
                  <h2 class="doc-split-title">{{ rightPaneTitle }}</h2>
                  <p class="doc-split-sub">{{ rightPaneSub }}</p>
                </div>
                <div class="doc-view-mode-segment" role="tablist" aria-label="右侧内容视图">
                  <button
                    type="button"
                    role="tab"
                    :aria-selected="rightView === 'chunks'"
                    :class="['doc-view-mode-btn', { active: rightView === 'chunks' }]"
                    @click="rightView = 'chunks'"
                  >
                    切片
                  </button>
                  <button
                    type="button"
                    role="tab"
                    :aria-selected="rightView === 'markdown'"
                    :class="['doc-view-mode-btn', { active: rightView === 'markdown' }]"
                    :disabled="!mineruViewEnabled"
                    :title="mineruViewDisabledTitle"
                    @click="selectMineruMarkdown"
                  >
                    Markdown
                  </button>
                  <button
                    type="button"
                    role="tab"
                    :aria-selected="rightView === 'json'"
                    :class="['doc-view-mode-btn', { active: rightView === 'json' }]"
                    :disabled="!mineruViewEnabled"
                    :title="mineruViewDisabledTitle"
                    @click="selectMineruJson"
                  >
                    JSON
                  </button>
                </div>
              </div>
              <div v-show="rightView === 'chunks'" class="doc-split-chunks-toolbar">
                <div class="doc-split-tabs" role="tablist" aria-label="切片展示方式">
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
                <div v-if="chunkTotal > 0" class="doc-split-pagination-top">
                  <span class="doc-split-total-top">共 {{ chunkTotal }} 条</span>
                  <div class="doc-split-page-controls-top">
                    <button
                      type="button"
                      class="btn btn-ghost btn-row-compact"
                      :disabled="chunkPage <= 1"
                      @click="chunkPage -= 1"
                    >
                      上一页
                    </button>
                    <span class="doc-split-page-num-top">{{ chunkPage }} / {{ chunkTotalPages }}</span>
                    <button
                      type="button"
                      class="btn btn-ghost btn-row-compact"
                      :disabled="chunkPage >= chunkTotalPages"
                      @click="chunkPage += 1"
                    >
                      下一页
                    </button>
                  </div>
                </div>
              </div>
            </header>

            <div class="doc-split-pane-body">
              <ScrollRowWithVSlider
                v-if="rightView === 'markdown'"
                scroll-class="doc-mineru-scroll doc-split-scroll-inner"
              >
                <div v-if="mineruMdLoading" class="loading-skeleton document-skeleton"></div>
                <div v-else-if="mineruMdError" class="status-box error">{{ mineruMdError }}</div>
                <div v-else-if="mineruMarkdownPages.length" class="doc-mineru-md-book">
                  <section v-for="pg in mineruMarkdownPages" :key="'mdp-' + pg.pageIdx0" class="doc-mineru-md-page">
                    <div class="doc-mineru-page-rule" aria-hidden="true">
                      <span class="doc-mineru-page-pill">第 {{ pg.pageNo }} 页</span>
                    </div>
                    <div
                      v-for="ent in pg.entries"
                      :key="'mdb-' + ent.index"
                      :id="'mv-block-' + ent.index"
                      class="doc-mineru-md-block"
                      :class="{ active: selectedMineruBlockIndex === ent.index }"
                      role="button"
                      tabindex="0"
                      @click="selectMineruBlock(ent.index)"
                      @keydown.enter.prevent="selectMineruBlock(ent.index)"
                    >
                      <span class="doc-mineru-block-type">{{ String(ent.item.type || 'text') }}</span>
                      <pre class="doc-mineru-block-text">{{ mineruBlockPlainText(ent.item) }}</pre>
                    </div>
                  </section>
                </div>
                <pre v-else class="doc-mineru-md-pre">{{ mineruMdText }}</pre>
              </ScrollRowWithVSlider>

              <ScrollRowWithVSlider
                v-else-if="rightView === 'json'"
                scroll-class="doc-mineru-scroll doc-split-scroll-inner"
              >
                <div v-if="mineruJsonLoading" class="loading-skeleton document-skeleton"></div>
                <div v-else-if="mineruJsonError" class="status-box error">{{ mineruJsonError }}</div>
                <pre v-else class="doc-mineru-json-pre">{{ mineruJsonText }}</pre>
              </ScrollRowWithVSlider>

              <template v-else>
                <div v-if="!hasChunksAvailable" class="doc-split-empty doc-split-empty-fill">
                  <p v-if="document.status === 'indexed' && document.chunk_count === 0">暂无切片数据。</p>
                  <p v-else>请先完成「开始解析」并等待索引完成后再查看切片。</p>
                </div>

                <div v-else class="doc-split-chunks-stack">
                  <div v-if="chunksLoading" class="loading-skeleton document-skeleton doc-split-scroll-inner"></div>
                  <div v-else-if="chunksError" class="status-box error doc-split-scroll-inner">{{ chunksError }}</div>
                  <template v-else>
                    <ScrollRowWithVSlider
                      ref="chunkScrollSliderRef"
                      scroll-class="doc-chunk-scroll-slider"
                      @scroll="onChunkListScroll"
                    >
                      <div class="doc-chunk-list">
                        <article
                          v-for="chunk in chunkItems"
                          :key="chunk.id"
                          class="doc-chunk-card"
                          :data-page-no="chunkPageNoAttr(chunk)"
                          :data-chunk-index="chunk.chunk_index"
                        >
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
                    </ScrollRowWithVSlider>
                  </template>
                </div>
              </template>
            </div>
          </section>
        </div>
        </div>
      </template>
    </div>
  </Layout>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
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
const DocumentPdfMineruLayout = defineAsyncComponent(() => import('../components/DocumentPdfMineruLayout.vue'))
import Layout from '../components/Layout.vue'
import ScrollRowWithVSlider from '../components/ScrollRowWithVSlider.vue'
import { groupMineruItemsByPage, mineruBlockPlainText, type MineruContentItem } from '../lib/mineruContentDisplay'

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

type RightView = 'chunks' | 'markdown' | 'json'
const rightView = ref<RightView>('chunks')
const mineruMdText = ref('')
const mineruMdLoading = ref(false)
const mineruMdError = ref('')
const mineruMdLoaded = ref(false)
const mineruJsonText = ref('')
const mineruJsonLoading = ref(false)
const mineruJsonError = ref('')
const mineruJsonLoaded = ref(false)

const mineruContentList = ref<MineruContentItem[]>([])
const selectedMineruBlockIndex = ref<number | null>(null)

const docSplitRootRef = ref<HTMLElement | null>(null)
const isDocSplitFullscreen = ref(false)

/** MinerU 左侧 PDF：供切片列表联动翻页 */
const pdfMineruLayoutRef = ref<{
  goToPage: (n: number) => Promise<void>
  getPageNum: () => number
} | null>(null)
const chunkScrollSliderRef = ref<{
  getScrollEl: () => HTMLElement | null
  syncThumb: () => void
} | null>(null)

function getChunkListScrollEl(): HTMLElement | null {
  return chunkScrollSliderRef.value?.getScrollEl() ?? null
}

let ignoreChunkScrollForPdf = false
let ignorePdfPageForChunkScroll = false
let chunkScrollRaf = 0

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
  cancelAnimationFrame(chunkScrollRaf)
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

function docMetadata(): Record<string, unknown> | null {
  const m = document.value?.metadata
  return m && typeof m === 'object' ? (m as Record<string, unknown>) : null
}

const mineruViewEnabled = computed(() => {
  const d = document.value
  if (!d) {
    return false
  }
  if (d.parser_type === 'mineru') {
    return true
  }
  const meta = docMetadata()
  return meta?.parser_backend === 'mineru'
})

const mineruViewDisabledTitle = '仅 MinerU 解析的 PDF / 图片可使用 Markdown 与 JSON 视图'

const showPdfMineruSync = computed(() => {
  const d = document.value
  if (!d) {
    return false
  }
  if ((d.file_ext || '').toLowerCase() !== 'pdf') {
    return false
  }
  return mineruContentList.value.length > 0
})

function chunkPageNoAttr(chunk: KnowledgeChunk): string | undefined {
  const p = chunk.page_no
  if (typeof p === 'number' && Number.isFinite(p) && p >= 1) {
    return String(p)
  }
  return undefined
}

/** 根据当前视口内切片，取与阅读线最接近的一条的 PDF 页码（1-based） */
function pickVisibleChunkPageNo(container: HTMLElement): number | null {
  const cr = container.getBoundingClientRect()
  if (cr.height < 8) {
    return null
  }
  const anchorY = cr.top + Math.min(96, cr.height * 0.22)
  const articles = container.querySelectorAll<HTMLElement>('.doc-chunk-card[data-page-no]')
  let best: { dist: number; page: number } | null = null
  for (const el of articles) {
    const r = el.getBoundingClientRect()
    if (r.bottom <= cr.top + 2 || r.top >= cr.bottom - 2) {
      continue
    }
    const raw = el.dataset.pageNo
    if (!raw) {
      continue
    }
    const page = Number(raw)
    if (!Number.isFinite(page) || page < 1) {
      continue
    }
    const mid = r.top + r.height / 2
    const dist = Math.abs(mid - anchorY)
    if (!best || dist < best.dist) {
      best = { dist, page }
    }
  }
  return best?.page ?? null
}

function onChunkListScroll() {
  if (!showPdfMineruSync.value || rightView.value !== 'chunks') {
    return
  }
  if (ignoreChunkScrollForPdf) {
    return
  }
  cancelAnimationFrame(chunkScrollRaf)
  chunkScrollRaf = requestAnimationFrame(() => {
    const el = getChunkListScrollEl()
    const pdf = pdfMineruLayoutRef.value
    if (!el || !pdf?.goToPage || !pdf.getPageNum) {
      return
    }
    const p = pickVisibleChunkPageNo(el)
    if (p == null) {
      return
    }
    const cur = pdf.getPageNum()
    if (cur === p) {
      return
    }
    ignorePdfPageForChunkScroll = true
    void pdf.goToPage(p).finally(() => {
      requestAnimationFrame(() => {
        ignorePdfPageForChunkScroll = false
      })
    })
  })
}

async function onPdfMineruPageChange(page: number) {
  if (!showPdfMineruSync.value || rightView.value !== 'chunks') {
    return
  }
  if (ignorePdfPageForChunkScroll) {
    return
  }
  const container = getChunkListScrollEl()
  if (!container) {
    return
  }
  const card = container.querySelector<HTMLElement>(`.doc-chunk-card[data-page-no="${page}"]`)
  if (!card) {
    return
  }
  ignoreChunkScrollForPdf = true
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  await nextTick()
  window.setTimeout(() => {
    ignoreChunkScrollForPdf = false
  }, 420)
}

const mineruMarkdownPages = computed(() => groupMineruItemsByPage(mineruContentList.value))

const rightPaneTitle = computed(() => {
  if (rightView.value === 'markdown') {
    return 'MinerU · Markdown'
  }
  if (rightView.value === 'json') {
    return 'MinerU · JSON'
  }
  return '切片结果'
})

const rightPaneSub = computed(() => {
  if (rightView.value === 'markdown') {
    if (mineruMarkdownPages.value.length) {
      return '按 content_list 分页展示；点击左侧 PDF 色块或右侧段落可双向联动高亮'
    }
    return '与 MinerU 返回的 md_content 一致（侧车文件 mineru_markdown.md）'
  }
  if (rightView.value === 'json') {
    return '与 MinerU 返回的 content_list 一致（侧车文件 mineru_content_list.json）'
  }
  return '将用于嵌入和召回的切片段落'
})

function resetMineruViewCache() {
  rightView.value = 'chunks'
  mineruMdText.value = ''
  mineruMdError.value = ''
  mineruMdLoaded.value = false
  mineruJsonText.value = ''
  mineruJsonError.value = ''
  mineruJsonLoaded.value = false
  mineruContentList.value = []
  selectedMineruBlockIndex.value = null
}

async function loadMineruMarkdown() {
  if (!mineruViewEnabled.value) {
    return
  }
  if (mineruContentList.value.length > 0) {
    mineruMdError.value = ''
    mineruMdLoaded.value = true
    return
  }
  if (mineruMdLoaded.value) {
    return
  }
  mineruMdLoading.value = true
  mineruMdError.value = ''
  try {
    mineruMdText.value = await knowledgeBaseApi.getDocumentMineruMarkdown(kbId.value, docId.value)
    mineruMdLoaded.value = true
  } catch (e) {
    mineruMdError.value = getKnowledgeBaseErrorMessage(e, '加载 MinerU Markdown 失败')
  } finally {
    mineruMdLoading.value = false
  }
}

async function loadMineruJson() {
  if (!mineruViewEnabled.value) {
    return
  }
  if (mineruContentList.value.length > 0) {
    mineruJsonText.value = JSON.stringify(mineruContentList.value, null, 2)
    mineruJsonError.value = ''
    mineruJsonLoaded.value = true
    return
  }
  if (mineruJsonLoaded.value) {
    return
  }
  mineruJsonLoading.value = true
  mineruJsonError.value = ''
  try {
    const raw = await knowledgeBaseApi.getDocumentMineruContentListText(kbId.value, docId.value)
    try {
      mineruJsonText.value = JSON.stringify(JSON.parse(raw) as unknown, null, 2)
    } catch {
      mineruJsonText.value = raw
    }
    mineruJsonLoaded.value = true
  } catch (e) {
    mineruJsonError.value = getKnowledgeBaseErrorMessage(e, '加载 MinerU JSON 失败')
  } finally {
    mineruJsonLoading.value = false
  }
}

function selectMineruBlock(index: number) {
  selectedMineruBlockIndex.value = selectedMineruBlockIndex.value === index ? null : index
}

function selectMineruMarkdown() {
  if (!mineruViewEnabled.value) {
    return
  }
  rightView.value = 'markdown'
  void loadMineruMarkdown()
}

function selectMineruJson() {
  if (!mineruViewEnabled.value) {
    return
  }
  rightView.value = 'json'
  void loadMineruJson()
}

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
    mineruContentList.value = []
    selectedMineruBlockIndex.value = null
    const d = document.value
    const meta = d?.metadata && typeof d.metadata === 'object' ? (d.metadata as Record<string, unknown>) : null
    const isMineru = d?.parser_type === 'mineru' || meta?.parser_backend === 'mineru'
    if (d && isMineru) {
      try {
        const raw = await knowledgeBaseApi.getDocumentMineruContentListText(kbId.value, docId.value)
        mineruContentList.value = JSON.parse(raw) as MineruContentItem[]
      } catch {
        mineruContentList.value = []
      }
    }
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
    void syncRouteFocusChunk()
  }
}

function desiredPageForChunkIndex(idx: number): number {
  if (chunkTotal.value <= 0) {
    return 1
  }
  const pages = Math.max(1, Math.ceil(chunkTotal.value / chunkPageSize.value))
  return Math.min(pages, Math.floor(idx / chunkPageSize.value) + 1)
}

async function syncRouteFocusChunk() {
  const raw = route.query.focus_chunk_index
  if (raw == null || Array.isArray(raw) || rightView.value !== 'chunks') {
    return
  }
  const target = Number(raw)
  if (!Number.isFinite(target)) {
    return
  }
  if (chunkTotal.value > 0) {
    const wantPage = desiredPageForChunkIndex(target)
    if (wantPage !== chunkPage.value) {
      chunkPage.value = wantPage
      return
    }
  }
  await nextTick()
  const el = getChunkListScrollEl()
  const card = el?.querySelector<HTMLElement>(`.doc-chunk-card[data-chunk-index="${target}"]`)
  if (card) {
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    card.classList.add('doc-chunk-card--flash')
    window.setTimeout(() => card.classList.remove('doc-chunk-card--flash'), 2200)
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
    resetMineruViewCache()
    void loadPage()
  },
  { immediate: true },
)

watch(mineruViewEnabled, (on) => {
  if (!on && rightView.value !== 'chunks') {
    rightView.value = 'chunks'
  }
  if (!on) {
    selectedMineruBlockIndex.value = null
  }
})

watch([selectedMineruBlockIndex, rightView], async ([idx, rv]) => {
  if (idx === null || rv !== 'markdown') {
    return
  }
  await nextTick()
  window.document.getElementById(`mv-block-${idx}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
})

watch(
  () => route.query.focus_chunk_index,
  () => {
    void syncRouteFocusChunk()
  },
)
</script>

<style scoped>
.doc-split-page {
  max-width: 100%;
  margin: 0;
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
  height: min(calc(100vh - 120px), 2000px);
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
  align-items: stretch;
  height: min(78vh, 920px);
}

@media (max-width: 1100px) {
  .doc-split-grid {
    grid-template-columns: 1fr;
  }
}

.doc-split-pane {
  padding: 20px 22px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.doc-split-pane-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.doc-split-scroll-inner {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.doc-split-chunks-stack {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.doc-split-empty-fill {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.doc-split-pane-body :deep(.document-original-preview) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: auto;
}

.doc-split-pane-body :deep(.document-original-iframe) {
  flex: 1;
  min-height: 0;
  width: 100%;
  height: auto !important;
}

.doc-split-pane-body :deep(.document-original-html),
.doc-split-pane-body :deep(.document-original-text) {
  flex: 1;
  min-height: 0;
  overflow: auto;
  max-height: none;
}

.doc-split-pane-head {
  flex-shrink: 0;
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

.doc-split-chunks-head-top {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px 20px;
}

.doc-split-chunks-head-text {
  flex: 1;
  min-width: 0;
}

.doc-view-mode-segment {
  display: inline-flex;
  flex-shrink: 0;
  padding: 4px;
  border-radius: 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  gap: 2px;
}

.doc-view-mode-btn {
  border: none;
  margin: 0;
  padding: 7px 16px;
  border-radius: 9px;
  font-size: 0.84rem;
  font-weight: 500;
  color: var(--text-primary);
  background: transparent;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}

.doc-view-mode-btn:hover:not(:disabled) {
  color: var(--brand-primary);
}

.doc-view-mode-btn.active {
  background: var(--bg-secondary);
  color: var(--brand-primary);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}

.doc-view-mode-btn:disabled {
  opacity: 0.42;
  cursor: not-allowed;
  color: var(--text-tertiary);
}

.doc-chunk-scroll-slider {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.doc-mineru-scroll {
  padding-right: 2px;
}

.doc-mineru-scroll.doc-split-scroll-inner {
  overflow-y: scroll;
  overflow-x: hidden;
}

.doc-mineru-scroll.doc-split-scroll-inner:has(.doc-mineru-json-pre) {
  overflow-x: auto;
}

.doc-mineru-md-book {
  padding: 4px 2px 12px;
}

.doc-mineru-md-page {
  margin-bottom: 8px;
}

.doc-mineru-page-rule {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 18px 0 14px;
}

.doc-mineru-md-page:first-child .doc-mineru-page-rule {
  margin-top: 4px;
}

.doc-mineru-page-rule::before,
.doc-mineru-page-rule::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-color);
}

.doc-mineru-page-pill {
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.doc-mineru-md-block {
  margin: 0 0 10px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.doc-mineru-md-block:hover {
  border-color: rgba(37, 99, 235, 0.35);
  background: rgba(59, 130, 246, 0.06);
}

.doc-mineru-md-block.active {
  border-color: rgba(29, 78, 216, 0.55);
  background: rgba(59, 130, 246, 0.16);
  box-shadow: 0 0 0 2px rgba(29, 78, 216, 0.12);
}

.doc-mineru-md-block:focus-visible {
  outline: 2px solid var(--brand-primary);
  outline-offset: 2px;
}

.doc-mineru-block-type {
  display: block;
  margin-bottom: 8px;
  font-size: 0.72rem;
  letter-spacing: 0.02em;
  color: var(--text-tertiary);
  text-transform: lowercase;
}

.doc-mineru-block-text {
  margin: 0;
  font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 0.88rem;
  line-height: 1.65;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.doc-mineru-md-pre {
  margin: 0;
  padding: 18px 20px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: linear-gradient(180deg, var(--bg-secondary) 0%, #f8fafc 100%);
  font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 0.88rem;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.doc-mineru-json-pre {
  margin: 0;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 0.78rem;
  line-height: 1.5;
  color: var(--text-primary);
  white-space: pre;
  overflow-x: auto;
  word-break: normal;
}

.doc-split-chunks-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.doc-split-pagination-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.doc-split-total-top {
  white-space: nowrap;
}

.doc-split-page-controls-top {
  display: flex;
  align-items: center;
  gap: 4px;
}

.doc-split-page-num-top {
  min-width: 48px;
  text-align: center;
  font-variant-numeric: tabular-nums;
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
  padding-right: 4px;
}

.doc-chunk-card {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.doc-chunk-card--flash {
  border-color: rgba(37, 99, 235, 0.45);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
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
  flex-shrink: 0;
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
