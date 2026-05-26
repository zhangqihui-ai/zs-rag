<template>
  <div class="docx-origin-layout">
    <ScrollRowWithVSlider scroll-class="docx-origin-scroll">
      <div class="docx-origin-book">
        <section
          v-for="pg in pages"
          :key="'dop-' + pg.pageIdx0"
          class="docx-origin-page"
          :data-docx-page="pg.pageNo"
        >
          <div class="docx-origin-page-rule" aria-hidden="true">
            <span class="docx-origin-page-pill">第 {{ pg.pageNo }} 页</span>
          </div>
          <button
            v-for="ent in pg.entries"
            :key="'dob-' + ent.index"
            type="button"
            class="docx-origin-block"
            :class="{ active: modelValue === ent.index, 'citation-focus': citationFocusIndex === ent.index }"
            :data-docx-block-index="ent.index"
            @click="onBlockClick(ent.index)"
          >
            <div class="docx-origin-block-inner" v-html="docxBlockDisplayHtml(ent.item)" />
          </button>
        </section>
      </div>
    </ScrollRowWithVSlider>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'

import { docxBlockDisplayHtml, groupDocxBlocksByPage, type DocxContentBlock } from '../lib/docxContentDisplay'
import ScrollRowWithVSlider from './ScrollRowWithVSlider.vue'

const props = defineProps<{
  blocks: DocxContentBlock[]
  citationFocusIndex?: number | null
}>()

const modelValue = defineModel<number | null>({ default: null })

const pages = computed(() => groupDocxBlocksByPage(props.blocks))

function onBlockClick(index: number) {
  modelValue.value = modelValue.value === index ? null : index
}

watch(
  () => modelValue.value,
  async (idx) => {
    if (idx == null) {
      return
    }
    await nextTick()
    const el = window.document.querySelector<HTMLElement>(`[data-docx-block-index="${idx}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  },
)
</script>

<style scoped>
.docx-origin-layout {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.docx-origin-scroll {
  flex: 1;
  min-height: 0;
}

.docx-origin-book {
  padding: 8px 12px 20px;
}

.docx-origin-page {
  margin-bottom: 8px;
}

.docx-origin-page-rule {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 12px 0 10px;
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.docx-origin-page:first-child .docx-origin-page-rule {
  margin-top: 4px;
}

.docx-origin-page-rule::before,
.docx-origin-page-rule::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-color);
}

.docx-origin-page-pill {
  flex-shrink: 0;
  padding: 2px 10px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  font-weight: 600;
  color: var(--text-primary);
}

.docx-origin-block {
  display: block;
  width: 100%;
  text-align: left;
  border: 1px solid color-mix(in srgb, var(--brand) 22%, var(--border-color));
  border-radius: 6px;
  background: var(--bg-primary);
  padding: 6px 10px;
  margin: 0 0 4px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}

.docx-origin-block:hover {
  border-color: color-mix(in srgb, var(--brand) 45%, var(--border-color));
}

.docx-origin-block.active,
.docx-origin-block.citation-focus {
  border-color: var(--brand);
  background: color-mix(in srgb, var(--brand) 10%, var(--bg-primary));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--brand) 35%, transparent);
}

.docx-origin-block-inner :deep(.docx-block-h2) {
  margin: 0 0 4px;
  font-size: 1.05rem;
  font-weight: 700;
  line-height: 1.45;
}

.docx-origin-block-inner :deep(.docx-block-h3) {
  margin: 0 0 4px;
  font-size: 0.95rem;
  font-weight: 650;
  line-height: 1.45;
}

.docx-origin-block-inner :deep(.docx-block-p) {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.docx-origin-block-inner :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.docx-origin-block-inner :deep(th),
.docx-origin-block-inner :deep(td) {
  border: 1px solid var(--border-color);
  padding: 3px 6px;
}
</style>
