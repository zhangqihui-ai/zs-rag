<template>
  <Teleport to="body">
    <div
      v-if="visible && citation"
      ref="cardRef"
      class="citation-hover-card"
      :style="cardStyle"
      role="tooltip"
    >
      <div class="citation-hover-card__head">
        <span class="citation-hover-card__ref">{{ formatCitationDisplayRef(citation.ref) }}</span>
        <div class="citation-hover-card__title-wrap">
          <div class="citation-hover-card__title">{{ citation.document_name }}</div>
          <div v-if="meta" class="citation-hover-card__meta">{{ meta }}</div>
        </div>
      </div>
      <div v-if="loading" class="citation-hover-card__loading">加载预览…</div>
      <p v-else class="citation-hover-card__excerpt">{{ excerpt || '暂无预览内容' }}</p>
      <div class="citation-hover-card__hint">点击查看完整切片</div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch, type CSSProperties } from 'vue'

import type { ChatCitation } from '../../api/chat'
import { citationPreviewMeta } from '../../lib/citationPreview'
import { formatCitationDisplayRef } from '../../lib/chatMarkdown'

const props = defineProps<{
  visible: boolean
  citation: ChatCitation | null
  excerpt: string
  loading: boolean
  anchorRect: DOMRect | null
}>()

const cardRef = ref<HTMLElement | null>(null)
const cardStyle = ref<CSSProperties>({})

const meta = computed(() => (props.citation ? citationPreviewMeta(props.citation) : ''))

async function updatePosition() {
  await nextTick()
  const anchor = props.anchorRect
  const card = cardRef.value
  if (!anchor || !card) {
    return
  }
  const margin = 10
  const cardRect = card.getBoundingClientRect()
  const cardWidth = Math.min(380, Math.max(cardRect.width, 280))
  let left = anchor.left + anchor.width / 2 - cardWidth / 2
  left = Math.max(margin, Math.min(left, window.innerWidth - cardWidth - margin))

  let top = anchor.top - cardRect.height - margin
  if (top < margin) {
    top = anchor.bottom + margin
  }

  cardStyle.value = {
    top: `${top}px`,
    left: `${left}px`,
    width: `${cardWidth}px`,
  }
}

watch(
  () => [props.visible, props.anchorRect, props.excerpt, props.loading] as const,
  () => {
    if (props.visible) {
      void updatePosition()
    }
  },
  { flush: 'post' },
)
</script>

<style scoped>
.citation-hover-card {
  position: fixed;
  z-index: 2500;
  max-width: min(380px, calc(100vw - 20px));
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid color-mix(in srgb, var(--border-color) 80%, #fff);
  background: var(--bg-primary, #fff);
  box-shadow:
    0 12px 32px rgba(15, 23, 42, 0.12),
    0 2px 8px rgba(15, 23, 42, 0.06);
  pointer-events: none;
}

.citation-hover-card__head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}

.citation-hover-card__ref {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 500;
  background: var(--citation-badge-bg);
  color: var(--citation-badge-text);
  border: 1px solid var(--citation-badge-border);
}

.citation-hover-card__title-wrap {
  min-width: 0;
}

.citation-hover-card__title {
  font-size: 0.92rem;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-primary);
  word-break: break-word;
}

.citation-hover-card__meta {
  margin-top: 2px;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.citation-hover-card__loading,
.citation-hover-card__excerpt {
  margin: 0;
  font-size: 0.84rem;
  line-height: 1.65;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 5;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.citation-hover-card__hint {
  margin-top: 10px;
  font-size: 0.72rem;
  color: var(--text-tertiary, #94a3b8);
}
</style>
