<template>
  <div class="document-original-preview">
    <div v-if="loading" class="document-original-preview-loading">正在加载原文…</div>
    <div v-else-if="error" class="status-box error">{{ error }}</div>
    <iframe v-else-if="mode === 'iframe' && iframeUrl" class="document-original-iframe" title="原文预览" :src="iframeUrl" />
    <div v-else-if="mode === 'html'" class="document-original-html" v-html="html" />
    <pre v-else-if="mode === 'text'" class="document-original-text">{{ text }}</pre>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'

import { getKnowledgeBaseErrorMessage, knowledgeBaseApi } from '../api/knowledge-base'

const props = defineProps<{
  kbId: number
  documentId: number
  fileName: string
  fileExt: string | null
  mimeType: string | null
}>()

const loading = ref(true)
const error = ref('')
const mode = ref<'html' | 'iframe' | 'text'>('text')
const html = ref('')
const text = ref('')
const iframeUrl = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = ''
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
      iframeUrl.value = URL.createObjectURL(toOpen)
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
  () => [props.kbId, props.documentId, props.fileName, props.fileExt],
  () => {
    void load()
  },
)

onUnmounted(() => {
  if (iframeUrl.value) {
    URL.revokeObjectURL(iframeUrl.value)
  }
})
</script>

<style scoped>
.document-original-preview {
  min-height: 200px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  overflow: hidden;
}

.document-original-preview-loading {
  padding: 48px 16px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.document-original-iframe {
  width: 100%;
  min-height: min(72vh, 720px);
  height: 72vh;
  border: none;
  display: block;
  background: var(--bg-secondary);
}

.document-original-html {
  padding: 16px 18px;
  max-height: min(72vh, 720px);
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

.document-original-text {
  margin: 0;
  padding: 16px 18px;
  max-height: min(72vh, 720px);
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, monospace;
  font-size: 0.82rem;
  line-height: 1.5;
  color: var(--text-primary);
}
</style>
