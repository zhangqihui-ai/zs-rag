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
                v-if="isPdfDocument"
                ref="pdfMineruLayoutRef"
                :kb-id="kbId"
                :document-id="document.id"
                :items="mineruContentList"
                v-model="selectedMineruBlockIndex"
                :citation-focus-index="citationFocusMineruIndex"
                @page-change="onPdfMineruPageChange"
                @ready="onPdfViewerReady"
              />
              <DocumentOriginalPreview
                v-else-if="isDocxDocument"
                ref="docxOriginalPreviewRef"
                :kb-id="kbId"
                :document-id="document.id"
                :file-name="document.file_name"
                :file-ext="document.file_ext"
                :mime-type="document.mime_type"
                :initial-page="focusedPageNo"
                :highlight-query="docxOriginalHighlightText"
                :sync-page="docxSyncPage"
                :page-anchor-texts="docxPageAnchorTexts"
                @page-visible="onDocxPageVisible"
                @scroll-ratio="onDocxOriginalScrollRatio"
              />
              <DocumentOriginalPreview
                v-else
                :kb-id="kbId"
                :document-id="document.id"
                :file-name="document.file_name"
                :file-ext="document.file_ext"
                :mime-type="document.mime_type"
                :initial-page="focusedPageNo"
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
                <div class="doc-split-chunks-head-actions">
                  <button
                    v-if="parseViewCopyVisible"
                    class="btn btn-ghost btn-row-compact doc-parse-copy-btn"
                    type="button"
                    :disabled="parseViewCopyDisabled"
                    :title="parseViewCopyDisabled ? '暂无可复制内容' : '复制全部解析内容'"
                    @click="copyParseViewContent"
                  >
                    <AppIcon name="copy" :size="14" />
                    {{ parseViewCopyLabel }}
                  </button>
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
                    :disabled="!parseViewEnabled"
                    :title="parseViewDisabledTitle"
                    @click="selectParseMarkdown"
                  >
                    Markdown
                  </button>
                  <button
                    type="button"
                    role="tab"
                    :aria-selected="rightView === 'json'"
                    :class="['doc-view-mode-btn', { active: rightView === 'json' }]"
                    :disabled="!parseViewEnabled"
                    :title="parseViewDisabledTitle"
                    @click="selectParseJson"
                  >
                    JSON
                  </button>
                  <button
                    v-if="docxViewEnabled"
                    type="button"
                    role="tab"
                    :aria-selected="rightView === 'tables'"
                    :class="['doc-view-mode-btn', { active: rightView === 'tables' }]"
                    @click="selectDocxTables"
                  >
                    表格
                  </button>
                </div>
                </div>
              </div>
              <div v-show="rightView === 'chunks'" class="doc-split-chunks-toolbar">
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
                  <span class="doc-split-total-top">共 {{ chunkTotal }} 切片</span>
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
                <div v-else-if="docxViewEnabled && docxMarkdownPages.length" class="doc-mineru-md-book">
                  <section
                    v-for="pg in docxMarkdownPages"
                    :key="'dmdp-' + pg.pageIdx0"
                    class="doc-mineru-md-page"
                  >
                    <div class="doc-mineru-page-rule" aria-hidden="true">
                      <span class="doc-mineru-page-pill">第 {{ pg.pageNo }} 页</span>
                    </div>
                    <div
                      v-for="ent in pg.entries"
                      :key="'dmdb-' + ent.index"
                      :id="'dv-block-' + ent.index"
                      class="doc-mineru-md-block"
                      :class="{ active: selectedMineruBlockIndex === ent.index }"
                      role="button"
                      tabindex="0"
                      @click="selectParseBlock(ent.index)"
                      @keydown.enter.prevent="selectParseBlock(ent.index)"
                    >
                      <span class="doc-mineru-block-type">{{ docxBlockTypeLabel(ent.item) }}</span>
                      <div class="doc-mineru-block-md" v-html="docxBlockDisplayHtml(ent.item)" />
                    </div>
                  </section>
                </div>
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
                      <div
                        v-if="mineruBlockIsTableRenderable(ent.item)"
                        class="doc-mineru-table-wrap"
                        v-html="mineruBlockTableHtml(ent.item)"
                      />
                      <pre v-else class="doc-mineru-block-text">{{ mineruBlockPlainText(ent.item) }}</pre>
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

              <ScrollRowWithVSlider
                v-else-if="rightView === 'tables'"
                scroll-class="doc-mineru-scroll doc-split-scroll-inner"
              >
                <div v-if="!docxTableBlocks.length" class="doc-split-empty doc-split-empty-fill">
                  <p>本文档未识别到表格块。</p>
                </div>
                <div v-else class="doc-docx-tables-list">
                  <article
                    v-for="item in docxTableBlocks"
                    :key="'tbl-' + item.block_index"
                    :id="'dv-block-' + item.block_index"
                    class="doc-docx-table-card"
                    :class="{ active: selectedMineruBlockIndex === item.block_index }"
                    role="button"
                    tabindex="0"
                    @click="selectParseBlock(item.block_index)"
                    @keydown.enter.prevent="selectParseBlock(item.block_index)"
                  >
                    <header class="doc-docx-table-head">
                      <span>表格 · 块 #{{ item.block_index + 1 }}</span>
                      <span v-if="item.heading_path" class="doc-docx-table-path">{{ item.heading_path }}</span>
                    </header>
                    <div class="doc-chunk-table-wrap" v-html="tableBlockPreviewHtml(item)" />
                    <pre class="doc-mineru-block-text">{{ docxBlockPlainText(item) }}</pre>
                  </article>
                </div>
              </ScrollRowWithVSlider>

              <template v-else>
                <div v-if="!hasChunksAvailable" class="doc-split-empty doc-split-empty-fill">
                  <p v-if="document.status === 'indexed' && document.chunk_count === 0">暂无切片数据。</p>
                  <p v-else-if="document.status === 'graph_indexed' && isLightragKb && document.chunk_count === 0">
                    图知识库已完成图谱入库，但暂无分块记录；PDF/图片可切换至「Markdown / JSON」查看 MinerU 解析结果。
                  </p>
                  <p v-else-if="document.status === 'graph_indexing' || document.status === 'parsing'">
                    解析或图谱入库进行中，请稍候…
                  </p>
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
                          :class="{
                            'doc-chunk-card--focused': chunk.chunk_index === focusedChunkIndex,
                            'doc-chunk-card--block-active':
                              selectedMineruBlockIndex != null && chunkMatchesDocxBlock(chunk, selectedMineruBlockIndex),
                            'doc-chunk-card--linkable': isDocxDocument && docxViewEnabled,
                          }"
                          :data-page-no="chunkPageNoAttr(chunk)"
                          :data-chunk-index="chunk.chunk_index"
                          @click="onChunkCardClick(chunk)"
                        >
                          <div class="doc-chunk-card-head">
                            <AppIcon name="grip" class="doc-chunk-grip" :size="16" />
                            <div class="doc-chunk-head-main">
                              <span class="doc-chunk-title-line"
                                >Chunk-{{ chunk.chunk_index + 1 }} · {{ chunkCharCount(chunk) }} 字符</span
                              >
                              <div class="doc-chunk-head-badges">
                                <span
                                  :class="[
                                    'doc-chunk-kind',
                                    {
                                      'doc-chunk-kind--table': chunkBlockType(chunk) === 'table',
                                      'doc-chunk-kind--image': chunkBlockType(chunk) === 'image',
                                      'doc-chunk-kind--heading': chunkBlockType(chunk) === 'heading',
                                    },
                                  ]"
                                >
                                  {{ chunkKindLabel(chunk) }}
                                </span>
                                <span
                                  :class="['doc-chunk-vec', chunk.vector_status === 'indexed' ? 'indexed' : 'pending']"
                                >
                                  {{ chunkVectorLabel(chunk) }}
                                </span>
                                <button
                                  v-if="chunkEnrichmentEditable(chunk)"
                                  class="btn btn-ghost btn-row-compact doc-chunk-edit-btn"
                                  type="button"
                                  title="编辑关键词与假设问题"
                                  @click.stop="openChunkEditModal(chunk)"
                                >
                                  编辑
                                </button>
                              </div>
                            </div>
                          </div>
                          <p v-if="chunkEnrichmentSummary(chunk)" class="doc-chunk-enrich-summary">
                            关键词：{{ chunkEnrichmentSummary(chunk) }}
                          </p>
                          <template v-if="chunkTableHtmlForDisplay(chunk)">
                            <p v-if="chunkTableContextForDisplay(chunk)" class="doc-chunk-context">
                              {{ chunkTableContextForDisplay(chunk) }}
                            </p>
                            <div class="doc-chunk-table-wrap" v-html="chunkTableHtmlForDisplay(chunk)" />
                          </template>
                          <p v-else class="doc-chunk-body">{{ chunkDisplayText(chunk) }}</p>
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

    <ChunkEnrichmentEditModal
      :open="chunkEditOpen"
      :kb-id="kbId"
      :chunk="chunkEditTarget"
      :kind-label="chunkEditTarget ? chunkKindLabel(chunkEditTarget) : undefined"
      :table-html="chunkEditTarget ? chunkTableHtmlForDisplay(chunkEditTarget) : undefined"
      @close="closeChunkEditModal"
      @saved="onChunkEnrichmentSaved"
    />
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
import ChunkEnrichmentEditModal from '../components/ChunkEnrichmentEditModal.vue'
import DocumentOriginalPreview from '../components/DocumentOriginalPreview.vue'
const DocumentPdfMineruLayout = defineAsyncComponent(() => import('../components/DocumentPdfMineruLayout.vue'))
import Layout from '../components/Layout.vue'
import ScrollRowWithVSlider from '../components/ScrollRowWithVSlider.vue'
import { groupMineruItemsByPage, chunkTableContextPrefix, chunkTableHtml, mineruBlockPlainText, mineruBlockTableHtml, mineruBlockIsTableRenderable, shouldShowMineruBlock, type MineruContentItem } from '../lib/mineruContentDisplay'
import {
  buildDocxPageAnchorTexts,
  chunkMatchesDocxBlock,
  chunkOriginalScrollProbe,
  countDocxPages,
  docxBlockDisplayHtml,
  docxBlockPlainText,
  docxBlockTypeLabel,
  docxHighlightTextForBlock,
  findDocxBlockForChunk,
  groupDocxBlocksByPage,
  isDocxTableBlock,
  resolveChunkWordPage,
  tableBlockPreviewHtml,
  type DocxContentBlock,
} from '../lib/docxContentDisplay'
import { findMineruBlockForChunk, parseRouteFocusInt } from '../lib/documentCitationFocus'
import { copyToClipboard } from '../lib/copy-to-clipboard'

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

const chunkEditOpen = ref(false)
const chunkEditTarget = ref<KnowledgeChunk | null>(null)

type RightView = 'chunks' | 'markdown' | 'json' | 'tables'
const rightView = ref<RightView>('chunks')
const mineruMdText = ref('')
const mineruMdLoading = ref(false)
const mineruMdError = ref('')
const mineruMdLoaded = ref(false)
const mineruJsonText = ref('')
const mineruJsonLoading = ref(false)
const mineruJsonError = ref('')
const mineruJsonLoaded = ref(false)
const parseViewCopyLabel = ref('全选复制')
let parseViewCopyResetTimer: ReturnType<typeof window.setTimeout> | null = null

const mineruContentList = ref<MineruContentItem[]>([])
const docxContentList = ref<DocxContentBlock[]>([])
const selectedMineruBlockIndex = ref<number | null>(null)
const focusedChunkIndex = ref<number | null>(null)
const focusedPageNo = ref<number | null>(null)
const citationFocusMineruIndex = ref<number | null>(null)
const focusedChunkData = ref<KnowledgeChunk | null>(null)
let citationFocusApplying = false

const docSplitRootRef = ref<HTMLElement | null>(null)
const isDocSplitFullscreen = ref(false)

/** MinerU 左侧 PDF：供切片列表联动翻页 */
const pdfMineruLayoutRef = ref<{
  whenReady: () => Promise<void>
  goToCitationPage: (page: number, blockIndex?: number | null) => Promise<void>
  goToPage: (n: number) => Promise<void>
  getPageNum: () => number
  focusBlock: (index: number | null) => Promise<void>
} | null>(null)
const docxOriginalPreviewRef = ref<{
  scrollToPage: (page: number) => Promise<void>
  scrollToText: (query: string, options?: { highlight?: boolean }) => Promise<boolean>
  getHtmlRoot: () => HTMLElement | null
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
let ignoreChunkScrollForDocx = false
let ignoreDocxPageForChunkScroll = false
let chunkScrollRaf = 0
const docxSyncPage = ref<number | null>(null)
const docxCurrentPage = ref<number | null>(null)
const docxHighlightOverride = ref<string | null>(null)
const lastSyncedChunkIndex = ref<number | null>(null)
let docxScrollRatioRaf = 0

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
  if (parseViewCopyResetTimer != null) {
    window.clearTimeout(parseViewCopyResetTimer)
    parseViewCopyResetTimer = null
  }
  const doc = window.document
  doc.removeEventListener('fullscreenchange', syncDocSplitFullscreen)
  doc.removeEventListener('webkitfullscreenchange', syncDocSplitFullscreen)
})

const isLightragKb = computed(() => knowledgeBase.value?.kb_type === 'lightrag')

const usesGraphSegmentPreview = computed(() => {
  if (!isLightragKb.value || document.value?.status !== 'graph_indexed' || !mineruViewEnabled.value) {
    return false
  }
  return mineruContentList.value.some(shouldShowMineruBlock)
})

const usesLightragChunkList = computed(() => {
  const d = document.value
  if (!d || !isLightragKb.value) {
    return false
  }
  return d.status === 'graph_indexed' && d.chunk_count > 0 && !usesGraphSegmentPreview.value
})

const hasChunksAvailable = computed(() => {
  const d = document.value
  if (!d) {
    return false
  }
  if (d.status === 'indexed' && d.chunk_count > 0) {
    return true
  }
  if (usesLightragChunkList.value) {
    return true
  }
  return usesGraphSegmentPreview.value
})

function docMetadata(): Record<string, unknown> | null {
  const m = document.value?.metadata
  return m && typeof m === 'object' ? (m as Record<string, unknown>) : null
}

const parseViewEnabled = computed(() => {
  if (docxViewEnabled.value) {
    return true
  }
  const d = document.value
  if (!d) {
    return false
  }
  if (d.parser_type === 'mineru' || d.parser_type === 'pdf') {
    const meta = docMetadata()
    const backend = meta?.parser_backend
    if (backend === 'mineru' || backend === 'opendataloader') {
      return true
    }
  }
  const meta = docMetadata()
  return meta?.parser_backend === 'mineru' || meta?.parser_backend === 'opendataloader'
})

const parseViewDisabledTitle = '请先完成解析/重建索引；Word 需当前版本重新索引后才有 Markdown/JSON/表格视图'

const mineruViewEnabled = parseViewEnabled
const mineruViewDisabledTitle = parseViewDisabledTitle

const showPdfMineruSync = computed(() => isPdfDocument.value && mineruContentList.value.length > 0)

const isPdfDocument = computed(() => {
  const d = document.value
  if (!d) {
    return false
  }
  return (d.file_ext || '').toLowerCase() === 'pdf'
})

const isDocxDocument = computed(() => {
  const d = document.value
  if (!d) {
    return false
  }
  return (d.file_ext || '').toLowerCase() === 'docx'
})

/** python-docx 解析：侧车 docx_content_list.json */
const docxViewEnabled = computed(() => isDocxDocument.value && docxContentList.value.length > 0)

/** docx 走 MinerU 引擎：侧车 mineru_content_list.json，Markdown/JSON 走 MinerU 接口 */
const docxMineruViewEnabled = computed(
  () => isDocxDocument.value && mineruContentList.value.length > 0 && !docxViewEnabled.value,
)

const docxTableBlocks = computed(() => docxContentList.value.filter(isDocxTableBlock))

const docxMarkdownPages = computed(() => groupDocxBlocksByPage(docxContentList.value))

const docxPageAnchorTexts = computed(() =>
  docxViewEnabled.value ? buildDocxPageAnchorTexts(docxContentList.value) : null,
)

const hasMultipleDocxPages = computed(() => countDocxPages(docxContentList.value) > 1)

const docxOriginalHighlightText = computed(() => {
  if (docxHighlightOverride.value) {
    return docxHighlightOverride.value
  }
  const idx = selectedMineruBlockIndex.value
  if (idx == null || !docxContentList.value.length) {
    return null
  }
  const block = docxContentList.value.find((b) => b.block_index === idx)
  return block ? docxBlockPlainText(block) : null
})

function chunkPageNoAttr(chunk: KnowledgeChunk): string | undefined {
  const p = resolveChunkWordPage(chunk, docxContentList.value)
  return p != null ? String(p) : undefined
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

function pickVisibleChunk(container: HTMLElement): KnowledgeChunk | null {
  const cr = container.getBoundingClientRect()
  if (cr.height < 8) {
    return null
  }
  const anchorY = cr.top + Math.min(96, cr.height * 0.22)
  const articles = container.querySelectorAll<HTMLElement>('.doc-chunk-card[data-chunk-index]')
  let best: { dist: number; chunk: KnowledgeChunk } | null = null
  for (const el of articles) {
    const r = el.getBoundingClientRect()
    if (r.bottom <= cr.top + 2 || r.top >= cr.bottom - 2) {
      continue
    }
    const idx = Number(el.dataset.chunkIndex)
    if (!Number.isFinite(idx)) {
      continue
    }
    const chunk = chunkItems.value.find((c) => c.chunk_index === idx)
    if (!chunk) {
      continue
    }
    const mid = r.top + r.height / 2
    const dist = Math.abs(mid - anchorY)
    if (!best || dist < best.dist) {
      best = { dist, chunk }
    }
  }
  return best?.chunk ?? null
}

async function focusDocxFromChunk(chunk: KnowledgeChunk) {
  if (!isDocxDocument.value || !docxViewEnabled.value) {
    return
  }

  lastSyncedChunkIndex.value = chunk.chunk_index
  docxHighlightOverride.value = null

  const blockIdx = findDocxBlockForChunk(chunk, docxContentList.value)
  let probe: string | null = null

  if (blockIdx != null) {
    selectedMineruBlockIndex.value = blockIdx
    probe = docxHighlightTextForBlock(docxContentList.value, blockIdx)
  } else {
    selectedMineruBlockIndex.value = null
    probe = chunkOriginalScrollProbe(chunk, docxContentList.value)
    if (probe) {
      docxHighlightOverride.value = probe
    }
  }

  if (!probe) {
    return
  }

  const page = resolveChunkWordPage(chunk, docxContentList.value)
  if (page != null && hasMultipleDocxPages.value) {
    docxCurrentPage.value = page
    docxSyncPage.value = page
  }

  ignoreDocxPageForChunkScroll = true
  await docxOriginalPreviewRef.value?.scrollToText(probe)
  window.setTimeout(() => {
    ignoreDocxPageForChunkScroll = false
  }, 420)
}

async function scrollChunkIntoViewByIndex(chunkIndex: number) {
  const wantPage = desiredPageForChunkIndex(chunkIndex, chunkTotal.value)
  if (wantPage !== chunkPage.value) {
    chunkPage.value = wantPage
    await loadChunks()
  }
  await nextTick()
  const container = getChunkListScrollEl()
  const card = container?.querySelector<HTMLElement>(`[data-chunk-index="${chunkIndex}"]`)
  if (!card) {
    return
  }
  ignoreChunkScrollForDocx = true
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  window.setTimeout(() => {
    ignoreChunkScrollForDocx = false
  }, 420)
}

function onChunkListScroll() {
  if (rightView.value !== 'chunks') {
    return
  }
  cancelAnimationFrame(chunkScrollRaf)
  chunkScrollRaf = requestAnimationFrame(() => {
    const el = getChunkListScrollEl()
    if (!el) {
      return
    }

    if (isPdfDocument.value) {
      const p = pickVisibleChunkPageNo(el)
      if (p == null) {
        return
      }
      if (ignoreChunkScrollForPdf) {
        return
      }
      const pdf = pdfMineruLayoutRef.value
      if (!pdf?.goToPage || !pdf.getPageNum) {
        return
      }
      if (pdf.getPageNum() === p) {
        return
      }
      ignorePdfPageForChunkScroll = true
      void pdf.goToPage(p).finally(() => {
        requestAnimationFrame(() => {
          ignorePdfPageForChunkScroll = false
        })
      })
      return
    }

    if (isDocxDocument.value && docxViewEnabled.value) {
      if (ignoreChunkScrollForDocx) {
        return
      }
      const chunk = pickVisibleChunk(el)
      if (!chunk) {
        return
      }
      if (lastSyncedChunkIndex.value === chunk.chunk_index) {
        return
      }
      lastSyncedChunkIndex.value = chunk.chunk_index
      const page = resolveChunkWordPage(chunk, docxContentList.value)
      if (page != null && hasMultipleDocxPages.value && page !== docxCurrentPage.value) {
        docxCurrentPage.value = page
        ignoreDocxPageForChunkScroll = true
        void docxOriginalPreviewRef.value?.scrollToPage(page)
        window.setTimeout(() => {
          ignoreDocxPageForChunkScroll = false
        }, 420)
      }
    }
  })
}

function onDocxOriginalScrollRatio(ratio: number) {
  if (!isDocxDocument.value || !docxViewEnabled.value || rightView.value !== 'chunks') {
    return
  }
  if (ignoreChunkScrollForDocx || chunkTotal.value <= 0) {
    return
  }
  if (hasMultipleDocxPages.value) {
    return
  }
  cancelAnimationFrame(docxScrollRatioRaf)
  docxScrollRatioRaf = requestAnimationFrame(() => {
    const targetIdx = Math.min(
      Math.max(0, chunkTotal.value - 1),
      Math.round(ratio * Math.max(0, chunkTotal.value - 1)),
    )
    if (lastSyncedChunkIndex.value === targetIdx) {
      return
    }
    lastSyncedChunkIndex.value = targetIdx
    ignoreChunkScrollForDocx = true
    void scrollChunkIntoViewByIndex(targetIdx).finally(() => {
      window.setTimeout(() => {
        ignoreChunkScrollForDocx = false
      }, 420)
    })
  })
}

function onDocxPageVisible(page: number) {
  if (!isDocxDocument.value || !docxViewEnabled.value || rightView.value !== 'chunks') {
    return
  }
  if (ignoreDocxPageForChunkScroll || !hasMultipleDocxPages.value) {
    return
  }
  if (docxCurrentPage.value === page) {
    return
  }
  docxCurrentPage.value = page
  const container = getChunkListScrollEl()
  if (!container) {
    return
  }
  const card = container.querySelector<HTMLElement>(`.doc-chunk-card[data-page-no="${page}"]`)
  if (!card) {
    return
  }
  ignoreChunkScrollForDocx = true
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  window.setTimeout(() => {
    ignoreChunkScrollForDocx = false
  }, 420)
}

function onChunkCardClick(chunk: KnowledgeChunk) {
  void focusDocxFromChunk(chunk)
}

async function onPdfMineruPageChange(page: number) {
  if (!isPdfDocument.value || rightView.value !== 'chunks') {
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
    return '解析 · Markdown'
  }
  if (rightView.value === 'json') {
    return '解析 · JSON'
  }
  if (rightView.value === 'tables') {
    return '解析 · 表格'
  }
  return '切片结果'
})

const parseViewCopyVisible = computed(() => rightView.value === 'markdown' || rightView.value === 'json')

const parseViewCopyText = computed(() => {
  if (rightView.value === 'json') {
    return mineruJsonText.value.trim()
  }
  if (rightView.value === 'markdown') {
    const raw = mineruMdText.value.trim()
    if (raw) {
      return raw
    }
    if (docxContentList.value.length) {
      return docxContentList.value.map(docxBlockPlainText).filter(Boolean).join('\n\n')
    }
    if (mineruContentList.value.length) {
      return mineruContentList.value
        .filter(shouldShowMineruBlock)
        .map(mineruBlockPlainText)
        .filter(Boolean)
        .join('\n\n')
    }
  }
  return ''
})

const parseViewCopyBusy = computed(() => {
  if (rightView.value === 'markdown') {
    return mineruMdLoading.value
  }
  if (rightView.value === 'json') {
    return mineruJsonLoading.value
  }
  return false
})

const parseViewCopyDisabled = computed(() => {
  if (parseViewCopyBusy.value) {
    return true
  }
  if (rightView.value === 'markdown' && mineruMdError.value) {
    return true
  }
  if (rightView.value === 'json' && mineruJsonError.value) {
    return true
  }
  return !parseViewCopyText.value
})

const rightPaneSub = computed(() => {
  if (rightView.value === 'markdown') {
    if (docxViewEnabled.value) {
      return '左侧为 Word 原文预览（含图片）；右侧按 Word 页码展示解析块，点击可联动高亮'
    }
    if (mineruMarkdownPages.value.length) {
      if (docxMineruViewEnabled.value) {
        return 'Word 经 MinerU 解析；按 content_list 分页展示解析块'
      }
      return '按 content_list 分页展示；点击左侧 PDF 色块或右侧段落可双向联动高亮'
    }
    return '与解析引擎返回的 md_content 一致（侧车文件 mineru_markdown.md）'
  }
  if (rightView.value === 'json') {
    if (docxViewEnabled.value) {
      return '与 Word 解析 content_list 一致（侧车文件 docx_content_list.json）'
    }
    if (docxMineruViewEnabled.value) {
      return 'Word 经 MinerU 解析（侧车文件 mineru_content_list.json）'
    }
    return '与解析引擎返回的 content_list 一致（侧车文件 mineru_content_list.json）'
  }
  if (rightView.value === 'tables') {
    return '从 content_list 筛选表格类块；点击可与左侧块、切片联动'
  }
  if (usesGraphSegmentPreview.value) {
    return '图知识库使用 LightRAG 图谱索引；此处展示 PDF 解析段落供预览（非经典向量切片）'
  }
  if (usesLightragChunkList.value) {
    return '图知识库 LightRAG 索引分块，用于实体抽取与图谱检索'
  }
  if (docxViewEnabled.value) {
    return '点击切片定位左侧原文；滚动任一侧按正文/页码同步另一侧'
  }
  return '将用于嵌入和召回的切片段落'
})

function resetMineruViewCache() {
  rightView.value = 'chunks'
  parseViewCopyLabel.value = '全选复制'
  if (parseViewCopyResetTimer != null) {
    window.clearTimeout(parseViewCopyResetTimer)
    parseViewCopyResetTimer = null
  }
  mineruMdText.value = ''
  mineruMdError.value = ''
  mineruMdLoaded.value = false
  mineruJsonText.value = ''
  mineruJsonError.value = ''
  mineruJsonLoaded.value = false
  mineruContentList.value = []
  docxContentList.value = []
  selectedMineruBlockIndex.value = null
  docxSyncPage.value = null
  docxCurrentPage.value = null
  docxHighlightOverride.value = null
  lastSyncedChunkIndex.value = null
}

async function loadDocxContentList() {
  if (!isDocxDocument.value) {
    docxContentList.value = []
    return
  }
  try {
    const raw = await knowledgeBaseApi.getDocumentDocxContentListText(kbId.value, docId.value)
    docxContentList.value = JSON.parse(raw) as DocxContentBlock[]
  } catch {
    docxContentList.value = []
  }
}

async function loadParseMarkdown() {
  if (!parseViewEnabled.value) {
    return
  }
  if (docxViewEnabled.value) {
    mineruMdError.value = ''
    mineruMdLoaded.value = true
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
    if (isDocxDocument.value && docMetadata()?.parser_backend !== 'mineru') {
      mineruMdText.value = await knowledgeBaseApi.getDocumentDocxMarkdown(kbId.value, docId.value)
    } else {
      mineruMdText.value = await knowledgeBaseApi.getDocumentMineruMarkdown(kbId.value, docId.value)
    }
    mineruMdLoaded.value = true
  } catch (e) {
    mineruMdError.value = getKnowledgeBaseErrorMessage(e, '加载 Markdown 失败')
  } finally {
    mineruMdLoading.value = false
  }
}

async function loadParseJson() {
  if (!parseViewEnabled.value) {
    return
  }
  if (docxViewEnabled.value) {
    mineruJsonText.value = JSON.stringify(docxContentList.value, null, 2)
    mineruJsonError.value = ''
    mineruJsonLoaded.value = true
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
    let raw: string
    if (isDocxDocument.value && docMetadata()?.parser_backend !== 'mineru') {
      raw = await knowledgeBaseApi.getDocumentDocxContentListText(kbId.value, docId.value)
    } else {
      raw = await knowledgeBaseApi.getDocumentMineruContentListText(kbId.value, docId.value)
    }
    try {
      mineruJsonText.value = JSON.stringify(JSON.parse(raw) as unknown, null, 2)
    } catch {
      mineruJsonText.value = raw
    }
    mineruJsonLoaded.value = true
  } catch (e) {
    mineruJsonError.value = getKnowledgeBaseErrorMessage(e, '加载 JSON 失败')
  } finally {
    mineruJsonLoading.value = false
  }
}

async function loadMineruMarkdown() {
  await loadParseMarkdown()
}

async function loadMineruJson() {
  await loadParseJson()
}

async function copyParseViewContent() {
  const text = parseViewCopyText.value
  if (!text) {
    return
  }
  const ok = await copyToClipboard(text)
  if (!ok) {
    alert('复制失败，请手动选择文本')
    return
  }
  parseViewCopyLabel.value = '已复制'
  if (parseViewCopyResetTimer != null) {
    window.clearTimeout(parseViewCopyResetTimer)
  }
  parseViewCopyResetTimer = window.setTimeout(() => {
    parseViewCopyLabel.value = '全选复制'
    parseViewCopyResetTimer = null
  }, 1600)
}

function selectParseBlock(index: number) {
  docxHighlightOverride.value = null
  if (selectedMineruBlockIndex.value === index) {
    selectedMineruBlockIndex.value = null
    return
  }
  selectedMineruBlockIndex.value = index
  const text = docxHighlightTextForBlock(docxContentList.value, index)
  if (text) {
    void docxOriginalPreviewRef.value?.scrollToText(text)
  }
  const block = docxContentList.value.find((b) => b.block_index === index)
  const page =
    typeof block?.page_no === 'number'
      ? block.page_no
      : typeof block?.page_idx === 'number'
        ? block.page_idx + 1
        : null
  if (page != null) {
    docxCurrentPage.value = page
    docxSyncPage.value = page
  }
  if (rightView.value === 'chunks') {
    void scrollChunkForDocxBlock(index)
  }
}

async function scrollChunkForDocxBlock(blockIndex: number) {
  await nextTick()
  const container = getChunkListScrollEl()
  if (!container) {
    return
  }
  const cards = container.querySelectorAll<HTMLElement>('.doc-chunk-card')
  for (const card of cards) {
    const idx = Number(card.dataset.chunkIndex)
    const chunk = chunkItems.value.find((c) => c.chunk_index === idx)
    if (chunk && chunkMatchesDocxBlock(chunk, blockIndex)) {
      card.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
  }
}

function selectMineruBlock(index: number) {
  selectParseBlock(index)
}

function selectParseMarkdown() {
  if (!parseViewEnabled.value) {
    return
  }
  rightView.value = 'markdown'
  void loadParseMarkdown()
}

function selectParseJson() {
  if (!parseViewEnabled.value) {
    return
  }
  rightView.value = 'json'
  void loadParseJson()
}

function selectDocxTables() {
  if (!docxViewEnabled.value) {
    return
  }
  rightView.value = 'tables'
}

function selectMineruMarkdown() {
  selectParseMarkdown()
}

function selectMineruJson() {
  selectParseJson()
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

function chunkBlockType(chunk: KnowledgeChunk): string | null {
  const m = chunk.metadata
  if (!m || typeof m !== 'object') {
    return null
  }
  if ((m as { source?: string }).source === 'mineru_graph_preview') {
    const t = String((m as { type?: string }).type || '').toLowerCase()
    return t || null
  }
  const block = (m as { block?: string }).block
  return block || null
}

function chunkKindLabel(chunk: KnowledgeChunk): string {
  const m = chunk.metadata
  if (m && typeof m === 'object') {
    if ((m as { source?: string }).source === 'mineru_graph_preview') {
      const typeMap: Record<string, string> = {
        text: '文本',
        title: '标题',
        table: '表格',
        image: '图片',
        code: '代码',
        list: '列表',
        equation: '公式',
      }
      const t = String((m as { type?: string }).type || 'text').toLowerCase()
      return typeMap[t] || t
    }
    const block = chunkBlockType(chunk)
    if (block === 'table') {
      return '表格'
    }
    if (block === 'image') {
      return '图片'
    }
    if (block === 'heading') {
      return '标题'
    }
    if (block === 'document_preamble') {
      return '文前'
    }
  }
  return '文本'
}

function chunkVectorLabel(chunk: KnowledgeChunk): string {
  const m = chunk.metadata
  if (m && typeof m === 'object') {
    const source = (m as { source?: string }).source
    if (source === 'mineru_graph_preview' || source === 'lightrag_text_chunk') {
      return '图谱索引'
    }
  }
  return chunk.vector_status === 'indexed' ? '已向量化' : '待向量'
}

function buildGraphPreviewChunks(items: MineruContentItem[], documentId: number): KnowledgeChunk[] {
  const now = new Date().toISOString()
  const shown = items.filter(shouldShowMineruBlock)
  return shown.map((item, index) => {
    const text = mineruBlockPlainText(item)
    const pageIdx = typeof item.page_idx === 'number' ? item.page_idx : 0
    const preview = text.length > 240 ? `${text.slice(0, 240)}…` : text
    return {
      id: -(index + 1),
      chunk_uid: `graph-preview-${documentId}-${index}`,
      document_id: documentId,
      chunk_index: index,
      content: text,
      content_preview: preview,
      char_count: [...text].length,
      token_count: null,
      start_offset: null,
      end_offset: null,
      page_no: pageIdx + 1,
      heading_path: null,
      vector_status: 'indexed',
      vector_id: null,
      metadata: {
        source: 'mineru_graph_preview',
        type: item.type,
        mineru_index: typeof item._index === 'number' ? item._index : index,
      },
      created_at: now,
      updated_at: now,
    }
  })
}

function loadGraphPreviewChunksPage() {
  if (!document.value) {
    chunkItems.value = []
    chunkTotal.value = 0
    return
  }
  let all = buildGraphPreviewChunks(mineruContentList.value, document.value.id)
  const kw = chunkKeyword.value.trim()
  if (kw) {
    all = all.filter((chunk) => chunk.content.includes(kw))
  }
  chunkTotal.value = all.length
  const start = (chunkPage.value - 1) * chunkPageSize.value
  chunkItems.value = all.slice(start, start + chunkPageSize.value)
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

function chunkTableHtmlForDisplay(chunk: KnowledgeChunk): string {
  return chunkTableHtml(chunk, mineruContentList.value)
}

function chunkTableContextForDisplay(chunk: KnowledgeChunk): string {
  return chunkTableContextPrefix(chunk)
}

function chunkEnrichmentKeywords(chunk: KnowledgeChunk): string[] {
  if (Array.isArray(chunk.enrichment_keywords) && chunk.enrichment_keywords.length > 0) {
    return chunk.enrichment_keywords
  }
  const raw = chunk.metadata?.enrichment_keywords
  if (Array.isArray(raw)) {
    return raw.map((item) => String(item).trim()).filter(Boolean)
  }
  return []
}

function chunkEnrichmentEditable(chunk: KnowledgeChunk): boolean {
  if (chunk.id <= 0 || usesGraphSegmentPreview.value) {
    return false
  }
  const source = String(chunk.metadata?.source ?? '')
  return source !== 'mineru_graph_preview' && source !== 'lightrag_text_chunk'
}

function chunkEnrichmentSummary(chunk: KnowledgeChunk): string {
  const kw = chunkEnrichmentKeywords(chunk)
  if (kw.length === 0) {
    return ''
  }
  const preview = kw.slice(0, 4).join('、')
  return kw.length > 4 ? `${preview}…` : preview
}

function closeChunkEditModal() {
  chunkEditOpen.value = false
  chunkEditTarget.value = null
}

async function openChunkEditModal(chunk: KnowledgeChunk) {
  if (!chunkEnrichmentEditable(chunk) || Number.isNaN(kbId.value)) {
    return
  }
  try {
    const fresh = await knowledgeBaseApi.getChunk(kbId.value, chunk.id)
    chunkEditTarget.value = fresh
    chunkEditOpen.value = true
  } catch (value) {
    chunksError.value = getKnowledgeBaseErrorMessage(value, '加载切片失败')
  }
}

function onChunkEnrichmentSaved(updated: KnowledgeChunk) {
  const index = chunkItems.value.findIndex((item) => item.id === updated.id)
  if (index >= 0) {
    chunkItems.value[index] = updated
  }
  if (focusedChunkData.value?.id === updated.id) {
    focusedChunkData.value = updated
  }
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
    docxContentList.value = []
    selectedMineruBlockIndex.value = null
    const d = document.value
    const meta = d?.metadata && typeof d.metadata === 'object' ? (d.metadata as Record<string, unknown>) : null
    const isParseViewDoc =
      d?.parser_type === 'mineru' ||
      d?.parser_type === 'pdf' ||
      meta?.parser_backend === 'mineru' ||
      meta?.parser_backend === 'opendataloader'
    if (d && isParseViewDoc) {
      try {
        const raw = await knowledgeBaseApi.getDocumentMineruContentListText(kbId.value, docId.value)
        mineruContentList.value = JSON.parse(raw) as MineruContentItem[]
      } catch {
        mineruContentList.value = []
      }
    }
    if (d && (d.file_ext || '').toLowerCase() === 'docx') {
      await loadDocxContentList()
    }
    if (hasChunksAvailable.value) {
      await resolveCitationFocusChunk()
      const chunkTotalHint = usesGraphSegmentPreview.value
        ? mineruContentList.value.filter(shouldShowMineruBlock).length
        : d.chunk_count
      if (focusedChunkIndex.value != null && chunkTotalHint > 0) {
        chunkPage.value = desiredPageForChunkIndex(focusedChunkIndex.value, chunkTotalHint)
      }
      await loadChunks()
    } else {
      await resolveCitationFocusChunk()
      await applyCitationFocus()
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
    if (usesGraphSegmentPreview.value) {
      loadGraphPreviewChunksPage()
    } else {
      const data = await knowledgeBaseApi.listChunks(kbId.value, docId.value, {
        page: chunkPage.value,
        page_size: chunkPageSize.value,
        keyword: chunkKeyword.value || undefined,
      })
      chunkItems.value = data.items
      chunkTotal.value = data.total
    }
  } catch (value) {
    chunksError.value = getKnowledgeBaseErrorMessage(value, '加载切片失败')
    chunkItems.value = []
    chunkTotal.value = 0
  } finally {
    chunksLoading.value = false
    void applyCitationFocus()
  }
}

function desiredPageForChunkIndex(idx: number, total = chunkTotal.value): number {
  if (total <= 0) {
    return 1
  }
  const pages = Math.max(1, Math.ceil(total / chunkPageSize.value))
  return Math.min(pages, Math.floor(idx / chunkPageSize.value) + 1)
}

function hasCitationFocusQuery(): boolean {
  return (
    route.query.focus_chunk_index != null ||
    route.query.focus_page_no != null ||
    route.query.focus_chunk_id != null
  )
}

function onPdfViewerReady() {
  if (hasCitationFocusQuery()) {
    void applyCitationFocus()
  }
}

async function scrollFocusedChunkIntoView(retry = 0): Promise<boolean> {
  if (focusedChunkIndex.value == null) {
    return true
  }
  await nextTick()
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  const el = getChunkListScrollEl()
  const card = el?.querySelector<HTMLElement>(
    `.doc-chunk-card[data-chunk-index="${focusedChunkIndex.value}"]`,
  )
  if (card) {
    card.scrollIntoView({ behavior: 'auto', block: 'center' })
    return true
  }
  if (retry < 12) {
    await new Promise<void>((resolve) => window.setTimeout(resolve, 100))
    return scrollFocusedChunkIntoView(retry + 1)
  }
  return false
}

async function focusPdfOnCitation(page: number | null, blockIdx: number | null) {
  if (page == null || page < 1 || !isPdfDocument.value) {
    return
  }
  const pdf = pdfMineruLayoutRef.value
  if (!pdf?.goToCitationPage) {
    return
  }
  await pdf.whenReady()
  if (blockIdx != null) {
    citationFocusMineruIndex.value = blockIdx
    selectedMineruBlockIndex.value = blockIdx
  }
  await pdf.goToCitationPage(page, blockIdx)
}

function resetCitationFocusState() {
  focusedChunkIndex.value = null
  focusedPageNo.value = null
  citationFocusMineruIndex.value = null
  focusedChunkData.value = null
  selectedMineruBlockIndex.value = null
}

function readCitationFocusFromRoute() {
  focusedChunkIndex.value = parseRouteFocusInt(route.query.focus_chunk_index)
  focusedPageNo.value = parseRouteFocusInt(route.query.focus_page_no)
}

async function resolveCitationFocusChunk() {
  readCitationFocusFromRoute()
  const chunkId = parseRouteFocusInt(route.query.focus_chunk_id)
  if (chunkId == null || Number.isNaN(kbId.value)) {
    return
  }
  try {
    const chunk = await knowledgeBaseApi.getChunk(kbId.value, chunkId)
    focusedChunkData.value = chunk
    if (focusedChunkIndex.value == null) {
      focusedChunkIndex.value = chunk.chunk_index
    }
    if (focusedPageNo.value == null && chunk.page_no != null) {
      focusedPageNo.value = chunk.page_no
    }
  } catch {
    /* 引文切片可能已删除，仍尝试按 index / page 定位 */
  }
}

function focusedChunkInCurrentList(): KnowledgeChunk | null {
  if (focusedChunkIndex.value == null) {
    return focusedChunkData.value
  }
  const hit = chunkItems.value.find((c) => c.chunk_index === focusedChunkIndex.value)
  return hit ?? focusedChunkData.value
}

async function applyCitationFocus() {
  if (citationFocusApplying) {
    return
  }
  if (focusedChunkIndex.value == null && focusedPageNo.value == null) {
    return
  }
  if (loading.value || !document.value) {
    return
  }

  citationFocusApplying = true
  try {
    rightView.value = 'chunks'
    chunkDisplayMode.value = 'full'
    chunkKeyword.value = ''
    chunkKeywordInput.value = ''

    const chunkTotalHint = document.value.chunk_count || chunkTotal.value
    if (focusedChunkIndex.value != null && chunkTotalHint > 0) {
      const wantPage = desiredPageForChunkIndex(focusedChunkIndex.value, chunkTotalHint)
      if (hasChunksAvailable.value && wantPage !== chunkPage.value) {
        chunkPage.value = wantPage
        return
      }
    }

    if (chunksLoading.value) {
      return
    }

    await nextTick()

    const chunk = focusedChunkInCurrentList()
    const page =
      focusedPageNo.value ??
      (chunk?.page_no != null && Number.isFinite(chunk.page_no) ? chunk.page_no : null)

    await scrollFocusedChunkIntoView()

    let blockIdx: number | null = null
    if (chunk && docxViewEnabled.value && docxContentList.value.length > 0) {
      blockIdx = findDocxBlockForChunk(chunk, docxContentList.value)
    } else if (chunk && mineruContentList.value.length > 0) {
      blockIdx = findMineruBlockForChunk(chunk, mineruContentList.value)
    }

    if (blockIdx != null) {
      selectedMineruBlockIndex.value = blockIdx
    }

    await focusPdfOnCitation(page, blockIdx)
  } finally {
    citationFocusApplying = false
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
    resetCitationFocusState()
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
  if (idx === null) {
    return
  }
  if (rv === 'chunks' && docxViewEnabled.value) {
    await scrollChunkForDocxBlock(idx)
  }
  if (rv === 'markdown' || rv === 'tables') {
    await nextTick()
    window.document.getElementById(`dv-block-${idx}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }
  if (rv === 'markdown' && mineruMarkdownPages.value.length && !docxViewEnabled.value) {
    await nextTick()
    window.document.getElementById(`mv-block-${idx}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }
})

watch(
  () => [route.query.focus_chunk_index, route.query.focus_page_no, route.query.focus_chunk_id],
  () => {
    void (async () => {
      await resolveCitationFocusChunk()
      await applyCitationFocus()
    })()
  },
)

watch(isPdfDocument, (pdf) => {
  if (pdf && hasCitationFocusQuery()) {
    void applyCitationFocus()
  }
})
</script>

<style scoped>
.doc-split-page {
  max-width: 100%;
  margin: 0;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.doc-split-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
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
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
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
  margin-bottom: 0;
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
  flex: 1;
  min-height: 0;
}

@media (max-width: 1100px) {
  .doc-split-grid {
    grid-template-columns: 1fr;
    flex: none;
    height: auto;
  }

  .doc-split-pane {
    min-height: 70vh;
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

.doc-split-chunks-head-actions {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 10px;
}

.doc-parse-copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  white-space: nowrap;
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

.doc-mineru-block-md :deep(.docx-block-h2) {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.5;
}

.doc-mineru-block-md :deep(.docx-block-h3) {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 650;
  line-height: 1.5;
}

.doc-mineru-block-md :deep(.docx-block-p) {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.doc-mineru-block-md :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.doc-mineru-block-md :deep(th),
.doc-mineru-block-md :deep(td) {
  border: 1px solid var(--border-color);
  padding: 3px 6px;
}

.doc-mineru-table-wrap,
.doc-chunk-table-wrap {
  margin-top: 6px;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-primary);
  -webkit-overflow-scrolling: touch;
}

.doc-mineru-table-wrap :deep(table),
.doc-chunk-table-wrap :deep(table) {
  width: max-content;
  min-width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: auto;
  font-size: 0.78rem;
  line-height: 1.4;
}

.doc-mineru-table-wrap :deep(th),
.doc-mineru-table-wrap :deep(td),
.doc-chunk-table-wrap :deep(th),
.doc-chunk-table-wrap :deep(td) {
  border: 1px solid var(--border-color);
  padding: 8px 10px;
  vertical-align: middle;
  white-space: nowrap;
  word-break: keep-all;
  overflow-wrap: normal;
  hyphens: none;
  min-width: 2.8em;
  max-width: 240px;
}

.doc-mineru-table-wrap :deep(th),
.doc-chunk-table-wrap :deep(th) {
  background: var(--bg-secondary);
  font-weight: 600;
  text-align: center;
  white-space: normal;
  line-height: 1.35;
  min-width: 3.2em;
}

.doc-mineru-table-wrap :deep(thead th),
.doc-chunk-table-wrap :deep(thead th) {
  position: sticky;
  top: 0;
  z-index: 2;
  box-shadow: 0 1px 0 var(--border-color);
}

.doc-mineru-table-wrap :deep(tr:nth-child(even) td),
.doc-chunk-table-wrap :deep(tr:nth-child(even) td) {
  background: color-mix(in srgb, var(--accent-soft, #eef4ff) 35%, transparent);
}

.doc-mineru-table-wrap :deep(td),
.doc-chunk-table-wrap :deep(td) {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.doc-mineru-table-wrap :deep(td:first-child),
.doc-mineru-table-wrap :deep(th:first-child),
.doc-chunk-table-wrap :deep(td:first-child),
.doc-chunk-table-wrap :deep(th:first-child) {
  text-align: left;
  position: sticky;
  left: 0;
  z-index: 1;
  background: var(--bg-primary);
  box-shadow: 2px 0 4px color-mix(in srgb, var(--border-color) 60%, transparent);
}

.doc-mineru-table-wrap :deep(thead th:first-child),
.doc-chunk-table-wrap :deep(thead th:first-child),
.doc-mineru-table-wrap :deep(table > tr:first-child > td:first-child),
.doc-chunk-table-wrap :deep(table > tr:first-child > td:first-child) {
  z-index: 4;
}

.doc-mineru-table-wrap :deep(tr:nth-child(even) td:first-child),
.doc-chunk-table-wrap :deep(tr:nth-child(even) td:first-child) {
  background: color-mix(in srgb, var(--accent-soft, #eef4ff) 35%, var(--bg-primary));
}

/* MinerU HTML 表头常为 td + rowspan，前两行按表头样式 */
.doc-mineru-table-wrap :deep(table > tr:nth-child(-n+2) > td),
.doc-mineru-table-wrap :deep(table > tbody > tr:nth-child(-n+2) > td),
.doc-chunk-table-wrap :deep(table > tr:nth-child(-n+2) > td),
.doc-chunk-table-wrap :deep(table > tbody > tr:nth-child(-n+2) > td) {
  background: var(--bg-secondary);
  font-weight: 600;
  text-align: center;
  white-space: normal;
  line-height: 1.35;
}

.doc-mineru-table-wrap :deep(table > tr:nth-child(-n+2) > td:first-child),
.doc-mineru-table-wrap :deep(table > tbody > tr:nth-child(-n+2) > td:first-child),
.doc-chunk-table-wrap :deep(table > tr:nth-child(-n+2) > td:first-child),
.doc-chunk-table-wrap :deep(table > tbody > tr:nth-child(-n+2) > td:first-child) {
  background: var(--bg-secondary);
}

.doc-mineru-table-wrap :deep(table > tr:first-child > td),
.doc-mineru-table-wrap :deep(table > tr:first-child > th),
.doc-mineru-table-wrap :deep(table > tbody > tr:first-child > td),
.doc-mineru-table-wrap :deep(table > tbody > tr:first-child > th),
.doc-chunk-table-wrap :deep(table > tr:first-child > td),
.doc-chunk-table-wrap :deep(table > tr:first-child > th),
.doc-chunk-table-wrap :deep(table > tbody > tr:first-child > td),
.doc-chunk-table-wrap :deep(table > tbody > tr:first-child > th) {
  position: sticky;
  top: 0;
  z-index: 2;
  box-shadow: 0 1px 0 var(--border-color);
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
  gap: 6px;
  flex: 0 1 auto;
  min-width: 160px;
  max-width: 240px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.doc-split-search-input {
  border: none;
  background: transparent;
  flex: 1;
  min-width: 0;
  padding: 4px 0;
  font-size: 0.8rem;
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

.doc-chunk-card--focused {
  border-color: rgba(245, 158, 11, 0.75);
  background: rgba(254, 243, 199, 0.45);
  box-shadow:
    0 0 0 2px rgba(245, 158, 11, 0.28),
    inset 4px 0 0 #f59e0b;
}

.doc-chunk-card--focused .doc-chunk-title-line {
  color: #b45309;
  font-weight: 700;
}

.doc-chunk-card--block-active {
  border-color: rgba(37, 99, 235, 0.65);
  background: color-mix(in srgb, rgba(37, 99, 235, 0.08) 60%, var(--bg-tertiary));
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.18);
}

.doc-chunk-card--linkable {
  cursor: pointer;
}

.doc-chunk-card--linkable:hover {
  border-color: color-mix(in srgb, var(--brand) 35%, var(--border-color));
}

.doc-docx-tables-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 4px 16px;
}

.doc-docx-table-card {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 12px;
  background: var(--bg-primary);
  cursor: pointer;
}

.doc-docx-table-card.active {
  border-color: rgba(37, 99, 235, 0.65);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}

.doc-docx-table-head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.doc-docx-table-path {
  color: var(--text-tertiary);
  font-size: 0.78rem;
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

.doc-chunk-edit-btn {
  min-width: 0;
  padding: 2px 8px;
  font-size: 0.72rem;
  line-height: 1.3;
}

.doc-chunk-enrich-summary {
  margin: -2px 0 8px 24px;
  font-size: 0.75rem;
  line-height: 1.45;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-chunk-kind {
  padding: 2px 8px;
  border-radius: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.doc-chunk-kind--table {
  background: rgba(59, 130, 246, 0.08);
  border-color: rgba(59, 130, 246, 0.25);
  color: #2563eb;
}

.doc-chunk-kind--image {
  background: rgba(168, 85, 247, 0.1);
  border-color: rgba(168, 85, 247, 0.28);
  color: #9333ea;
}

.doc-chunk-kind--heading {
  background: rgba(245, 158, 11, 0.1);
  border-color: rgba(245, 158, 11, 0.28);
  color: #d97706;
}

.doc-chunk-card:has(.doc-chunk-kind--image) {
  border-color: rgba(168, 85, 247, 0.22);
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

.doc-chunk-context {
  margin: 0 0 10px;
  font-size: 0.82rem;
  line-height: 1.55;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  font-weight: 600;
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
