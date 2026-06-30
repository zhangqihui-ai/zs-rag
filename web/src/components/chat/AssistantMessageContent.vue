<template>
  <div
    ref="rootRef"
    class="msg-text msg-text--assistant chat-markdown-body"
    :class="{ 'is-streaming': streaming }"
    v-html="html"
  />
  <CitationHoverCard
    :visible="hoverVisible"
    :citation="hoverCitation"
    :excerpt="hoverExcerpt"
    :loading="hoverLoading"
    :anchor-rect="hoverAnchorRect"
  />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import type { ChatCitation, ChatMessage } from '../../api/chat'
import CitationHoverCard from './CitationHoverCard.vue'
import { citationExcerpt } from '../../lib/citationPreview'
import { loadCitationPreviewText } from '../../lib/citationPreviewLoader'
import { renderAssistantMessageHtml } from '../../lib/chatMarkdown'

const props = defineProps<{
  content: string
  streaming: boolean
  showCitations: boolean
  message: ChatMessage
  citationTitleForRef: (refNum: number, message: ChatMessage) => string
  resolveCitationKbId?: (citation: ChatCitation) => number | null
}>()

const emit = defineEmits<{
  citationClick: [refNum: number]
}>()

const rootRef = ref<HTMLElement | null>(null)
const hoverVisible = ref(false)
const hoverCitation = ref<ChatCitation | null>(null)
const hoverExcerpt = ref('')
const hoverLoading = ref(false)
const hoverAnchorRect = ref<DOMRect | null>(null)

let showTimer: ReturnType<typeof setTimeout> | null = null
let previewToken = 0
let activeBadge: HTMLElement | null = null

const html = computed(() =>
  renderAssistantMessageHtml(props.content, {
    showCitations: props.showCitations,
    streaming: props.streaming,
    citationTitleForRef: (refNum) => props.citationTitleForRef(refNum, props.message),
  }),
)

function clearShowTimer() {
  if (showTimer) {
    clearTimeout(showTimer)
    showTimer = null
  }
}

function hideHoverPreview() {
  clearShowTimer()
  hoverVisible.value = false
  hoverCitation.value = null
  hoverExcerpt.value = ''
  hoverLoading.value = false
  hoverAnchorRect.value = null
  activeBadge = null
}

function resolveKbId(citation: ChatCitation): number | null {
  if (props.resolveCitationKbId) {
    return props.resolveCitationKbId(citation)
  }
  if (citation.knowledge_base_id != null && Number.isFinite(citation.knowledge_base_id)) {
    return citation.knowledge_base_id
  }
  return null
}

async function showHoverPreview(badge: HTMLElement, refNum: number) {
  const citation = props.message.citations?.find((row) => row.ref === refNum)
  if (!citation) {
    return
  }
  activeBadge = badge
  hoverCitation.value = citation
  hoverAnchorRect.value = badge.getBoundingClientRect()
  hoverVisible.value = true
  hoverExcerpt.value = citation.content?.trim() ? citationExcerpt(citation.content) : ''
  hoverLoading.value = !hoverExcerpt.value

  const token = ++previewToken
  const excerpt = await loadCitationPreviewText(citation, resolveKbId)
  if (token !== previewToken || activeBadge !== badge) {
    return
  }
  hoverExcerpt.value = excerpt
  hoverLoading.value = false
  if (activeBadge) {
    hoverAnchorRect.value = activeBadge.getBoundingClientRect()
  }
}

function onBadgeEnter(badge: HTMLElement) {
  if (props.streaming || !props.showCitations) {
    return
  }
  const raw = badge.dataset.citationRef
  const refNum = raw != null ? parseInt(raw, 10) : NaN
  if (!Number.isFinite(refNum)) {
    return
  }
  if (hoverVisible.value && hoverCitation.value?.ref === refNum) {
    return
  }
  if (hoverVisible.value) {
    hideHoverPreview()
  }
  clearShowTimer()
  showTimer = setTimeout(() => {
    void showHoverPreview(badge, refNum)
  }, 220)
}

function onRootMouseOver(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof HTMLElement)) {
    return
  }
  const badge = target.closest('[data-citation-ref]')
  if (badge instanceof HTMLElement) {
    onBadgeEnter(badge)
    return
  }
  hideHoverPreview()
}

function onRootMouseOut(event: MouseEvent) {
  const related = event.relatedTarget
  if (related instanceof Node && rootRef.value?.contains(related)) {
    return
  }
  hideHoverPreview()
}

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
  hideHoverPreview()
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
    hideHoverPreview()
    emit('citationClick', refNum)
  }
}

function onScrollOrResize() {
  if (hoverVisible.value) {
    hideHoverPreview()
  }
}

watch(
  rootRef,
  (el, prev) => {
    prev?.removeEventListener('click', onRootClick)
    prev?.removeEventListener('keydown', onRootKeydown)
    prev?.removeEventListener('mouseover', onRootMouseOver)
    prev?.removeEventListener('mouseout', onRootMouseOut)
    el?.addEventListener('click', onRootClick)
    el?.addEventListener('keydown', onRootKeydown)
    el?.addEventListener('mouseover', onRootMouseOver)
    el?.addEventListener('mouseout', onRootMouseOut)
  },
  { immediate: true },
)

watch(
  () => props.streaming,
  (streaming) => {
    if (streaming) {
      hideHoverPreview()
    }
  },
)

onBeforeUnmount(() => {
  hideHoverPreview()
  window.removeEventListener('scroll', onScrollOrResize, true)
  window.removeEventListener('resize', onScrollOrResize)
})

window.addEventListener('scroll', onScrollOrResize, true)
window.addEventListener('resize', onScrollOrResize)
</script>
