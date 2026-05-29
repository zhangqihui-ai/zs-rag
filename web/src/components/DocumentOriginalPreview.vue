<template>
  <div class="document-original-preview">
    <div v-if="loading" class="document-original-preview-loading">正在加载原文…</div>
    <div v-else-if="error" class="status-box error">{{ error }}</div>
    <iframe v-else-if="mode === 'iframe' && iframeUrl" class="document-original-iframe" title="原文预览" :src="iframeUrl" />
    <div
      v-else-if="mode === 'html'"
      ref="htmlRootRef"
      class="document-original-html"
      v-html="html"
      @scroll.passive="onHtmlScroll"
    />
    <pre v-else-if="mode === 'text'" class="document-original-text">{{ text }}</pre>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { getKnowledgeBaseErrorMessage, knowledgeBaseApi } from '../api/knowledge-base'
import {
  clearHtmlHighlights,
  highlightAndScrollHtmlText,
  installDocxPageSentinels,
  pickVisibleDocxPage,
  scrollDocxPageSentinel,
  scrollHtmlToText,
} from '../lib/htmlTextHighlight'

const props = defineProps<{
  kbId: number
  documentId: number
  fileName: string
  fileExt: string | null
  mimeType: string | null
  /** PDF iframe 预览时跳转到指定页（1-based） */
  initialPage?: number | null
  /** Word 等 HTML 原文：联动高亮并滚动到匹配段落 */
  highlightQuery?: string | null
  /** Word 页码同步滚动（1-based） */
  syncPage?: number | null
  /** 每页首段文本，用于插入页锚点 */
  pageAnchorTexts?: Record<number, string> | null
}>()

const emit = defineEmits<{
  'page-visible': [page: number]
  'scroll-ratio': [ratio: number]
}>()

const loading = ref(true)
const error = ref('')
const mode = ref<'html' | 'iframe' | 'text'>('text')
const html = ref('')
const text = ref('')
const iframeUrl = ref<string | null>(null)
const htmlRootRef = ref<HTMLElement | null>(null)

let ignorePageVisibleEmit = false
let htmlScrollRaf = 0
let currentVisiblePage: number | null = null

async function refreshPageSentinels() {
  await nextTick()
  if (!htmlRootRef.value || !props.pageAnchorTexts || Object.keys(props.pageAnchorTexts).length === 0) {
    return
  }
  installDocxPageSentinels(htmlRootRef.value, props.pageAnchorTexts)
}

async function applyHighlight() {
  if (loading.value || mode.value !== 'html') {
    return
  }
  await nextTick()
  if (!props.highlightQuery?.trim()) {
    clearHtmlHighlights(htmlRootRef.value)
    return
  }
  highlightAndScrollHtmlText(htmlRootRef.value, props.highlightQuery)
}

async function scrollToText(query: string, options?: { highlight?: boolean }) {
  if (loading.value || mode.value !== 'html') {
    return false
  }
  await nextTick()
  ignorePageVisibleEmit = true
  const ok = scrollHtmlToText(htmlRootRef.value, query, options)
  window.setTimeout(() => {
    ignorePageVisibleEmit = false
  }, 420)
  return ok
}

async function scrollToPage(page: number) {
  if (loading.value || mode.value !== 'html' || page < 1) {
    return
  }
  await nextTick()
  ignorePageVisibleEmit = true
  scrollDocxPageSentinel(htmlRootRef.value, page, props.pageAnchorTexts)
  currentVisiblePage = page
  window.setTimeout(() => {
    ignorePageVisibleEmit = false
  }, 420)
}

function onHtmlScroll() {
  if (mode.value !== 'html') {
    return
  }
  const root = htmlRootRef.value
  if (root) {
    const max = root.scrollHeight - root.clientHeight
    const ratio = max > 8 ? root.scrollTop / max : 0
    emit('scroll-ratio', Math.min(1, Math.max(0, ratio)))
  }
  if (ignorePageVisibleEmit || mode.value !== 'html') {
    return
  }
  cancelAnimationFrame(htmlScrollRaf)
  htmlScrollRaf = requestAnimationFrame(() => {
    const page = pickVisibleDocxPage(htmlRootRef.value)
    if (page == null || page === currentVisiblePage) {
      return
    }
    currentVisiblePage = page
    emit('page-visible', page)
  })
}

async function load() {
  loading.value = true
  error.value = ''
  currentVisiblePage = null
  if (iframeUrl.value) {
    URL.revokeObjectURL(iframeUrl.value)
    iframeUrl.value = null
  }
  const ext = (props.fileExt || '').toLowerCase()
  try {
    const blob = await knowledgeBaseApi.fetchDocumentFileBlob(props.kbId, props.documentId)
    if (ext === 'docx') {
      const { docxBlobToHtml } = await import('../lib/officePreview')
      html.value = await docxBlobToHtml(blob)
      mode.value = 'html'
      return
    }
    if (['xlsx', 'xlsm', 'xls', 'csv'].includes(ext)) {
      const { spreadsheetBlobToHtml } = await import('../lib/officePreview')
      html.value = await spreadsheetBlobToHtml(blob, props.fileName)
      mode.value = 'html'
      return
    }
    if (ext === 'pdf') {
      const mime = blob.type || props.mimeType || 'application/pdf'
      const toOpen = blob.type ? blob : new Blob([blob], { type: mime })
      let url = URL.createObjectURL(toOpen)
      const page = props.initialPage
      if (typeof page === 'number' && Number.isFinite(page) && page >= 1) {
        url += `#page=${Math.round(page)}`
      }
      iframeUrl.value = url
      mode.value = 'iframe'
      return
    }
    text.value = await blob.text()
    mode.value = 'text'
  } catch (value) {
    error.value = getKnowledgeBaseErrorMessage(value, '加载原文失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})

watch(
  () => [props.kbId, props.documentId, props.fileName, props.fileExt, props.initialPage],
  () => {
    void load()
  },
)

watch(
  () => [html.value, loading.value, props.pageAnchorTexts],
  () => {
    void refreshPageSentinels()
  },
)

watch(
  () => [props.highlightQuery, html.value, loading.value],
  () => {
    void applyHighlight()
  },
)

watch(
  () => props.syncPage,
  (page) => {
    if (typeof page === 'number' && Number.isFinite(page) && page >= 1 && page !== currentVisiblePage) {
      void scrollToPage(page)
    }
  },
)

defineExpose({
  scrollToPage,
  scrollToText,
  getHtmlRoot: () => htmlRootRef.value,
})

onUnmounted(() => {
  if (iframeUrl.value) {
    URL.revokeObjectURL(iframeUrl.value)
  }
})
</script>

<style scoped>
.document-original-preview {
  flex: 1;
  min-height: 0;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  overflow: auto;
}

.document-original-preview-loading {
  padding: 48px 16px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.document-original-iframe {
  flex: 1;
  min-height: 0;
  width: 100%;
  border: none;
  display: block;
  background: var(--bg-secondary);
}

.document-original-html {
  flex: 1;
  min-height: 0;
  padding: 16px 18px;
  overflow: auto;
  font-size: 0.88rem;
  line-height: 1.55;
  color: var(--text-primary);
}

.document-original-html :deep(table) {
  border-collapse: collapse;
  width: 100%;
}

.document-original-html :deep(th),
.document-original-html :deep(td) {
  border: 1px solid var(--border-color);
  padding: 4px 8px;
}

.document-original-html :deep(img) {
  max-width: 100%;
  height: auto;
}

.document-original-html :deep(span.doc-original-highlight),
.document-original-html :deep(mark.doc-original-highlight) {
  display: inline-block;
  background: rgba(254, 242, 242, 0.92);
  border: 2px solid #ef4444;
  border-radius: 6px;
  padding: 2px 6px;
  margin: 1px 0;
  box-shadow:
    0 0 0 3px rgba(239, 68, 68, 0.18),
    0 4px 14px rgba(239, 68, 68, 0.12);
  color: inherit;
}

.document-original-html :deep(.doc-original-highlight-block) {
  background: rgba(254, 242, 242, 0.55) !important;
  border: 2px solid #ef4444 !important;
  border-radius: 8px;
  box-shadow:
    0 0 0 3px rgba(239, 68, 68, 0.16),
    inset 0 0 0 1px rgba(239, 68, 68, 0.08);
  scroll-margin-block: 48px;
}

.document-original-html :deep(.docx-page-sentinel) {
  height: 0;
  margin: 0;
  padding: 0;
  border: 0;
  overflow: hidden;
  pointer-events: none;
}

.document-original-text {
  flex: 1;
  min-height: 0;
  margin: 0;
  padding: 16px 18px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, monospace;
  font-size: 0.82rem;
  line-height: 1.5;
  color: var(--text-primary);
}
</style>
