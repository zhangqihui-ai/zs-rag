<template>
  <div
    v-if="open"
    class="modal-overlay agent-trace-chunk-modal-overlay"
    role="presentation"
    @click.self="emit('close')"
  >
    <div
      class="modal-content agent-trace-chunk-modal"
      :class="{ 'agent-trace-chunk-modal--wide': showsTable }"
      @click.stop
    >
      <div class="modal-header agent-trace-chunk-modal-head">
        <div>
          <h3>评估片段 · 切片正文</h3>
          <p v-if="row" class="agent-trace-chunk-modal-sub">
            {{ row.document_name
            }}<template v-if="chunkLabel"> · {{ chunkLabel }}</template>
          </p>
        </div>
        <button type="button" class="btn btn-text" aria-label="关闭" @click="emit('close')">
          <AppIcon name="close" :size="20" />
        </button>
      </div>
      <div class="modal-body agent-trace-chunk-modal-base">
        <div v-if="loading" class="loading-inline">加载切片正文…</div>
        <p v-else-if="error" class="status-box error agent-trace-chunk-modal-err">{{ error }}</p>
        <InboundChunkBodyDisplay
          v-else-if="displayChunk || fallbackContent"
          :chunk="displayChunk"
          :fallback-content="fallbackContent"
        />
      </div>
      <div class="modal-footer agent-trace-chunk-modal-footer">
        <button
          type="button"
          class="btn"
          style="background: var(--bg-secondary); border: 1px solid var(--border-color)"
          @click="emit('close')"
        >
          关闭
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { AgentTraceGradeSummary } from '../../api/chat'
import type { KnowledgeChunk } from '../../api/knowledge-base'
import { formatChunkLabel } from '../../lib/agentTraceDisplay'
import { isTableKnowledgeChunk } from '../../lib/mineruContentDisplay'
import { loadTraceChunkBody, type TraceKbResolver } from '../../lib/traceChunkDetail'
import InboundChunkBodyDisplay from '../knowledge-base/InboundChunkBodyDisplay.vue'
import AppIcon from '../AppIcon.vue'

const props = defineProps<{
  open: boolean
  row: AgentTraceGradeSummary | null
  resolveKbId?: TraceKbResolver
}>()

const emit = defineEmits<{
  close: []
}>()

const loading = ref(false)
const error = ref('')
const displayChunk = ref<KnowledgeChunk | null>(null)
const fallbackContent = ref<string | null>(null)

const chunkLabel = computed(() => {
  if (!props.row) {
    return ''
  }
  return formatChunkLabel(props.row.page_no, props.row.chunk_index)
})

const showsTable = computed(() => {
  const chunk = displayChunk.value
  if (chunk) {
    return isTableKnowledgeChunk(chunk)
  }
  const fallback = fallbackContent.value
  if (!fallback) {
    return false
  }
  return isTableKnowledgeChunk({ content: fallback, metadata: null })
})

watch(
  () => [props.open, props.row, props.resolveKbId] as const,
  async ([open, row]) => {
    if (!open || !row) {
      loading.value = false
      error.value = ''
      displayChunk.value = null
      fallbackContent.value = null
      return
    }

    loading.value = true
    error.value = ''
    displayChunk.value = null
    fallbackContent.value = null

    const result = await loadTraceChunkBody(row, props.resolveKbId)
    displayChunk.value = result.chunk
    fallbackContent.value = result.fallbackContent
    error.value = result.error || ''
    loading.value = false
  },
  { immediate: true },
)
</script>

<style scoped>
.agent-trace-chunk-modal-overlay {
  z-index: 1200;
}

.agent-trace-chunk-modal {
  width: min(760px, calc(100vw - 32px));
  max-height: min(82vh, 860px);
  display: flex;
  flex-direction: column;
}

.agent-trace-chunk-modal--wide {
  width: min(960px, calc(100vw - 32px));
}

.agent-trace-chunk-modal-head {
  flex-shrink: 0;
}

.agent-trace-chunk-modal-head h3 {
  margin: 0;
}

.agent-trace-chunk-modal-sub {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 0.85rem;
}

.agent-trace-chunk-modal-base {
  overflow: auto;
  min-height: 120px;
}

.agent-trace-chunk-modal-err {
  margin: 0;
}

.agent-trace-chunk-modal-footer {
  flex-shrink: 0;
}
</style>
