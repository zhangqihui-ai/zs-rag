<template>
  <div
    ref="rootRef"
    class="msg-text msg-text--assistant chat-markdown-body"
    :class="{ 'is-streaming': streaming }"
    v-html="html"
  />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { ChatMessage } from '../../api/chat'
import { renderAssistantMessageHtml } from '../../lib/chatMarkdown'

const props = defineProps<{
  content: string
  streaming: boolean
  showCitations: boolean
  message: ChatMessage
  citationTitleForRef: (refNum: number, message: ChatMessage) => string
}>()

const emit = defineEmits<{
  citationClick: [refNum: number]
}>()

const rootRef = ref<HTMLElement | null>(null)

const html = computed(() =>
  renderAssistantMessageHtml(props.content, {
    showCitations: props.showCitations,
    streaming: props.streaming,
    citationTitleForRef: (refNum) => props.citationTitleForRef(refNum, props.message),
  }),
)

function onRootClick(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof HTMLElement)) {
    return
  }
  const badge = target.closest('[data-citation-ref]')
  if (!badge || !(badge instanceof HTMLElement)) {
    return
  }
  const raw = badge.dataset.citationRef
  const refNum = raw != null ? parseInt(raw, 10) : NaN
  if (!Number.isFinite(refNum)) {
    return
  }
  event.preventDefault()
  event.stopPropagation()
  emit('citationClick', refNum)
}

function onRootKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' && event.key !== ' ') {
    return
  }
  const target = event.target
  if (!(target instanceof HTMLElement)) {
    return
  }
  if (!target.matches('[data-citation-ref]')) {
    return
  }
  event.preventDefault()
  const raw = target.dataset.citationRef
  const refNum = raw != null ? parseInt(raw, 10) : NaN
  if (Number.isFinite(refNum)) {
    emit('citationClick', refNum)
  }
}

watch(
  rootRef,
  (el, prev) => {
    prev?.removeEventListener('click', onRootClick)
    prev?.removeEventListener('keydown', onRootKeydown)
    el?.addEventListener('click', onRootClick)
    el?.addEventListener('keydown', onRootKeydown)
  },
  { immediate: true },
)
</script>
