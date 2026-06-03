<template>
  <Teleport to="body">
    <div v-if="open" class="retrieval-chunk-modal-overlay" role="presentation" @click.self="emit('close')">
      <div
        class="retrieval-chunk-modal"
        :class="{ 'retrieval-chunk-modal--wide': showPdfPreview }"
        role="dialog"
        aria-modal="true"
        aria-labelledby="retrieval-chunk-modal-title"
        @click.stop
        @dblclick.stop
      >
        <header class="retrieval-chunk-modal-head">
          <div>
            <h3 id="retrieval-chunk-modal-title">切片详情</h3>
            <p v-if="result" class="retrieval-chunk-modal-sub">
              {{ result.document_name }} · {{ chunkLabel }}
            </p>
          </div>
          <button type="button" class="icon-button" aria-label="关闭" @click="emit('close')">
            <AppIcon name="close" :size="18" />
          </button>
        </header>

        <div class="retrieval-chunk-modal-body">
          <div v-if="loading" class="loading-inline">加载切片详情…</div>
          <p v-else-if="loadError" class="status-box error">{{ loadError }}</p>
          <template v-else>
            <section class="retrieval-chunk-section">
              <h4>原文位置</h4>
              <div class="retrieval-chunk-meta-grid">
                <span v-if="locationText" class="chip chip-soft">{{ locationText }}</span>
                <span v-if="blockLabel" class="chip">{{ blockLabel }}</span>
                <span v-if="offsetText" class="chip chip-soft">{{ offsetText }}</span>
                <span v-if="charCount != null" class="chip chip-soft">{{ charCount }} 字符</span>
                <span class="chip">Score {{ formatSearchScore(result?.score) }}</span>
              </div>
            </section>

            <section class="retrieval-chunk-section">
              <h4>原文片段</h4>
              <template v-if="showPdfPreview && documentInfo && previewKbId != null">
                <p class="retrieval-chunk-note">
                  原始 PDF 页面预览；<strong class="retrieval-chunk-note-em">蓝框</strong>为本切片对应的版面区块。
                </p>
                <div class="retrieval-chunk-pdf-wrap">
                  <DocumentPdfMineruLayout
                    ref="pdfLayoutRef"
                    :kb-id="previewKbId"
                    :document-id="documentInfo.id"
                    :items="mineruItems"
                    v-model="pdfActiveIndex"
                    :citation-focus-index="pdfChunkBlock"
                    :chunk-indices="pdfChunkBlocks"
                    @ready="onPdfReady"
                  />
                </div>
              </template>
              <template v-else>
                <p class="retrieval-chunk-note">
                  解析原文中与本切片对应的片段，<strong class="retrieval-chunk-note-em">高亮</strong>部分为本切片正文。
                </p>
                <p
                  v-if="sourceContext && (sourceContext.truncated_before || sourceContext.truncated_after)"
                  class="retrieval-chunk-note"
                >
                  已省略前后文。
                </p>
                <div v-if="excerptHtml" class="retrieval-chunk-excerpt" v-html="excerptHtml" />
                <p v-else class="retrieval-chunk-note">暂无原文片段</p>
              </template>
            </section>

            <section v-if="keywords.length" class="retrieval-chunk-section">
              <h4>入库关键词</h4>
              <div class="retrieval-chunk-tags">
                <span v-for="item in keywords" :key="item" class="chip chip-brand">{{ item }}</span>
              </div>
            </section>

            <section v-if="questions.length" class="retrieval-chunk-section">
              <h4>推荐问题</h4>
              <ul class="retrieval-chunk-questions">
                <li v-for="item in questions" :key="item">{{ item }}</li>
              </ul>
            </section>

            <section class="retrieval-chunk-section">
              <h4>入库切片正文</h4>
              <pre class="retrieval-chunk-content">{{ displayContent }}</pre>
            </section>
          </template>
        </div>

        <footer class="retrieval-chunk-modal-foot">
          <button type="button" class="btn btn-primary" @click="emit('close')">关闭</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'

import type {
  ChunkSourceContext,
  KnowledgeChunk,
  KnowledgeDocument,
  KnowledgeSearchResult,
} from '../../api/knowledge-base'
import { knowledgeBaseApi } from '../../api/knowledge-base'
import { findMineruBlocksForChunk } from '../../lib/documentCitationFocus'
import { renderExcerptHtml } from '../../lib/excerptRender'
import type { MineruContentItem } from '../../lib/mineruContentDisplay'
import {
  formatSearchScore,
  searchResultBlockLabel,
  searchResultChunkLabel,
  searchResultKeywords,
  searchResultLocationText,
  searchResultOffsetText,
  searchResultQuestions,
} from '../../lib/retrieval-result-display'
import AppIcon from '../AppIcon.vue'

const DocumentPdfMineruLayout = defineAsyncComponent(() => import('../DocumentPdfMineruLayout.vue'))

const props = defineProps<{
  open: boolean
  result: KnowledgeSearchResult | null
  kbId?: number | null
}>()

const emit = defineEmits<{
  close: []
}>()

const loading = ref(false)
const loadError = ref('')
const loadedChunk = ref<KnowledgeChunk | null>(null)
const sourceContext = ref<ChunkSourceContext | null>(null)
const documentInfo = ref<KnowledgeDocument | null>(null)
const mineruItems = ref<MineruContentItem[]>([])
const pdfChunkBlocks = ref<number[]>([])
const pdfChunkBlock = computed(() => pdfChunkBlocks.value[0] ?? null)
const pdfActiveIndex = ref<number | null>(null)
const pdfFocusPage = ref<number | null>(null)
const pdfLayoutRef = ref<{
  whenReady: () => Promise<void>
  goToCitationPage: (page: number, blockIndex?: number | null) => Promise<void>
  focusBlock: (index: number | null) => Promise<void>
} | null>(null)

const previewKbId = computed(() => resolveKbId())
const isPdfDocument = computed(() => (documentInfo.value?.file_ext || '').toLowerCase() === 'pdf')
const showPdfPreview = computed(() => isPdfDocument.value && mineruItems.value.length > 0)

const chunkLabel = computed(() => (props.result ? searchResultChunkLabel(props.result) : ''))
const locationText = computed(() => (props.result ? searchResultLocationText(props.result) : null))
const blockLabel = computed(() => (props.result ? searchResultBlockLabel(props.result) : null))
const offsetText = computed(() => (props.result ? searchResultOffsetText(props.result) : null))
const keywords = computed(() => (props.result ? searchResultKeywords(props.result) : []))
const questions = computed(() => (props.result ? searchResultQuestions(props.result) : []))
const charCount = computed(() => loadedChunk.value?.char_count ?? props.result?.char_count ?? null)
const displayContent = computed(() => loadedChunk.value?.content ?? props.result?.content ?? '')

const excerptHtml = computed(() => {
  const ctx = sourceContext.value
  if (!ctx || !ctx.text) return ''
  return renderExcerptHtml(ctx.text, ctx.highlight_start, ctx.highlight_end)
})

function resolveKbId() {
  return props.kbId ?? props.result?.knowledge_base_id ?? null
}

function resetState() {
  loadedChunk.value = null
  sourceContext.value = null
  documentInfo.value = null
  mineruItems.value = []
  pdfChunkBlocks.value = []
  pdfActiveIndex.value = null
  pdfFocusPage.value = null
  loadError.value = ''
}

async function loadMineruItems(kbId: number, documentId: number): Promise<MineruContentItem[]> {
  try {
    const raw = await knowledgeBaseApi.getDocumentMineruContentListText(kbId, documentId)
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? (parsed as MineruContentItem[]) : []
  } catch {
    return []
  }
}

function resolvePdfFocusPage(chunk: KnowledgeChunk, blockIdx: number | null, items: MineruContentItem[]): number | null {
  if (typeof chunk.page_no === 'number' && Number.isFinite(chunk.page_no) && chunk.page_no >= 1) {
    return chunk.page_no
  }
  if (blockIdx != null) {
    const it = items[blockIdx]
    if (it && typeof it.page_idx === 'number') {
      return it.page_idx + 1
    }
  }
  return null
}

async function loadChunkDetail() {
  resetState()
  const result = props.result
  const kbId = resolveKbId()
  if (!props.open || !result || !kbId) return

  const isLightragResult =
    result.metadata?.source === 'lightrag' || result.chunk_uid.startsWith('lightrag:')
  if (isLightragResult) {
    return
  }

  loading.value = true
  try {
    const [chunk, document] = await Promise.all([
      knowledgeBaseApi.getChunk(kbId, result.chunk_id),
      knowledgeBaseApi.getDocument(kbId, result.document_id),
    ])
    loadedChunk.value = chunk
    documentInfo.value = document

    if ((document.file_ext || '').toLowerCase() === 'pdf') {
      const items = await loadMineruItems(kbId, document.id)
      mineruItems.value = items
      if (items.length) {
        const blocks = findMineruBlocksForChunk(chunk, items)
        pdfChunkBlocks.value = blocks
        const firstBlock = blocks[0] ?? null
        pdfActiveIndex.value = firstBlock
        pdfFocusPage.value = resolvePdfFocusPage(chunk, firstBlock, items)
      }
    }

    if (!showPdfPreview.value) {
      sourceContext.value = await knowledgeBaseApi.getChunkSourceContext(kbId, result.chunk_id)
    }
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : '加载切片详情失败'
  } finally {
    loading.value = false
  }
}

async function onPdfReady() {
  const layout = pdfLayoutRef.value
  if (!layout) return
  const page = pdfFocusPage.value
  if (page != null && page >= 1) {
    await layout.goToCitationPage(page, pdfChunkBlock.value)
  } else if (pdfChunkBlock.value != null) {
    await layout.focusBlock(pdfChunkBlock.value)
  }
}

watch(
  () => [props.open, props.result?.chunk_id, props.kbId, props.result?.knowledge_base_id],
  () => {
    if (props.open && props.result) {
      void loadChunkDetail()
    } else {
      resetState()
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.retrieval-chunk-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.48);
  backdrop-filter: blur(4px);
}

.retrieval-chunk-modal {
  width: min(760px, calc(100vw - 32px));
  max-height: min(88vh, 900px);
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  box-shadow: var(--card-shadow-lg, 0 24px 48px rgba(15, 23, 42, 0.18));
}

.retrieval-chunk-modal--wide {
  width: min(1040px, calc(100vw - 32px));
}

.retrieval-chunk-pdf-wrap {
  height: min(560px, 68vh);
  min-height: 320px;
  display: flex;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.retrieval-chunk-pdf-wrap :deep(.pdf-mineru-layout) {
  height: 100%;
  border: none;
  border-radius: 0;
}

.retrieval-chunk-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px 12px;
  border-bottom: 1px solid var(--border-color);
}

.retrieval-chunk-modal-head h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text-primary);
}

.retrieval-chunk-modal-sub {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 0.86rem;
}

.retrieval-chunk-modal-body {
  overflow: auto;
  display: grid;
  gap: 18px;
  padding: 16px 22px;
}

.retrieval-chunk-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 14px 22px 20px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.retrieval-chunk-section h4 {
  margin: 0 0 10px;
  font-size: 0.92rem;
  color: var(--text-primary);
}

.retrieval-chunk-note {
  margin: 0 0 8px;
  color: var(--text-tertiary);
  font-size: 0.8rem;
}

.retrieval-chunk-note-em {
  color: #dc2626;
  font-weight: 600;
}

.retrieval-chunk-meta-grid,
.retrieval-chunk-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.retrieval-chunk-questions {
  margin: 0;
  padding-left: 1.2rem;
  color: var(--text-secondary);
  display: grid;
  gap: 8px;
}

.retrieval-chunk-content {
  margin: 0;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  white-space: pre-wrap;
  word-break: break-word;
  font: inherit;
  color: var(--text-primary);
  max-height: 280px;
  overflow: auto;
}

.retrieval-chunk-excerpt {
  margin: 0;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  max-height: 380px;
  overflow: auto;
  line-height: 1.6;
  word-break: break-word;
}

.retrieval-chunk-excerpt :deep(.exc-block) {
  margin: 0 0 8px;
}

.retrieval-chunk-excerpt :deep(.exc-block:last-child) {
  margin-bottom: 0;
}

.retrieval-chunk-excerpt :deep(h3.exc-block) {
  font-size: 1.12rem;
  font-weight: 700;
  margin: 14px 0 8px;
}

.retrieval-chunk-excerpt :deep(h4.exc-block) {
  font-size: 1.02rem;
  font-weight: 700;
  margin: 12px 0 6px;
}

.retrieval-chunk-excerpt :deep(h5.exc-block) {
  font-size: 0.96rem;
  font-weight: 600;
  margin: 10px 0 6px;
}

.retrieval-chunk-excerpt :deep(h6.exc-block) {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 8px 0 4px;
}

.retrieval-chunk-excerpt :deep(strong) {
  font-weight: 700;
}

.retrieval-chunk-excerpt :deep(.exc-mark) {
  background: #fff3bf;
  color: inherit;
  padding: 1px 2px;
  border-radius: 4px;
  box-shadow: inset 0 -2px 0 rgba(245, 158, 11, 0.55);
}
</style>
