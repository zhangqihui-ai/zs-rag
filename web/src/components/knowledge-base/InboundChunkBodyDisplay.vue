<template>
  <section class="inbound-chunk-body">
    <h4 v-if="showHeading" class="inbound-chunk-body-title">入库切片正文</h4>
    <ChunkDataTableDisplay
      v-if="tableHtml"
      :html="tableHtml"
      wrap-class="retrieval-chunk-content-table"
    />
    <pre v-else-if="plainContent" class="retrieval-chunk-content">{{ plainContent }}</pre>
    <p v-else class="inbound-chunk-body-empty">暂无切片正文</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { KnowledgeChunk } from '../../api/knowledge-base'
import { isTableKnowledgeChunk, resolveChunkTableHtml } from '../../lib/mineruContentDisplay'
import ChunkDataTableDisplay from './ChunkDataTableDisplay.vue'

const props = withDefaults(
  defineProps<{
    chunk: KnowledgeChunk | null
    fallbackContent?: string | null
    showHeading?: boolean
  }>(),
  {
    fallbackContent: null,
    showHeading: true,
  },
)

const tableHtml = computed(() => {
  const chunk = props.chunk
  if (!chunk || !isTableKnowledgeChunk(chunk)) {
    return ''
  }
  return resolveChunkTableHtml(chunk)
})

const plainContent = computed(() => {
  if (tableHtml.value) {
    return ''
  }
  const fromChunk = (props.chunk?.content || '').trim()
  if (fromChunk) {
    return fromChunk
  }
  return (props.fallbackContent || '').trim()
})
</script>

<style scoped>
.inbound-chunk-body {
  display: grid;
  gap: 10px;
}

.inbound-chunk-body-title {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--text-primary);
}

.inbound-chunk-body-empty {
  margin: 0;
  font-size: 0.86rem;
  color: var(--text-tertiary);
}

.retrieval-chunk-content {
  margin: 0;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  font-family: inherit;
  font-size: 0.84rem;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-primary);
}
</style>
