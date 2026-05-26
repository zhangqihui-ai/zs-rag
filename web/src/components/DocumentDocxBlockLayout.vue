<template>
  <div class="docx-block-layout">
    <div v-if="loading" class="docx-block-loading">正在加载 Word 解析块…</div>
    <div v-else-if="error" class="status-box error">{{ error }}</div>
    <ScrollRowWithVSlider v-else scroll-class="docx-block-scroll">
      <div class="docx-block-list">
        <button
          v-for="item in blocks"
          :key="'db-' + item.block_index"
          type="button"
          class="docx-block-card"
          :class="{ active: modelValue === item.block_index, 'citation-focus': citationFocusIndex === item.block_index }"
          :data-docx-block-index="item.block_index"
          @click="onBlockClick(item.block_index)"
        >
          <span class="docx-block-type">{{ docxBlockTypeLabel(item) }} · #{{ item.block_index + 1 }}</span>
          <pre class="docx-block-text">{{ docxBlockPlainText(item) }}</pre>
        </button>
      </div>
    </ScrollRowWithVSlider>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { getKnowledgeBaseErrorMessage, knowledgeBaseApi } from '../api/knowledge-base'
import { docxBlockPlainText, docxBlockTypeLabel, type DocxContentBlock } from '../lib/docxContentDisplay'
import ScrollRowWithVSlider from './ScrollRowWithVSlider.vue'

const props = defineProps<{
  kbId: number
  documentId: number
  blocks?: DocxContentBlock[]
  citationFocusIndex?: number | null
}>()

const modelValue = defineModel<number | null>({ default: null })

const loading = ref(false)
const error = ref('')
const localBlocks = ref<DocxContentBlock[]>([])

const blocks = ref<DocxContentBlock[]>([])

async function loadBlocks() {
  if (props.blocks?.length) {
    blocks.value = props.blocks
    return
  }
  loading.value = true
  error.value = ''
  try {
    const raw = await knowledgeBaseApi.getDocumentDocxContentListText(props.kbId, props.documentId)
    const parsed = JSON.parse(raw) as DocxContentBlock[]
    localBlocks.value = Array.isArray(parsed) ? parsed : []
    blocks.value = localBlocks.value
  } catch (e) {
    error.value = getKnowledgeBaseErrorMessage(e, '加载 Word 解析块失败')
    blocks.value = []
  } finally {
    loading.value = false
  }
}

function onBlockClick(index: number) {
  modelValue.value = modelValue.value === index ? null : index
}

onMounted(() => {
  void loadBlocks()
})

watch(
  () => [props.kbId, props.documentId, props.blocks],
  () => {
    void loadBlocks()
  },
)

defineExpose({
  blocks,
  reload: loadBlocks,
})
</script>

<style scoped>
.docx-block-layout {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.docx-block-loading {
  padding: 48px 16px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.docx-block-scroll {
  flex: 1;
  min-height: 0;
}

.docx-block-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 4px 16px;
}

.docx-block-card {
  text-align: left;
  width: 100%;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-primary);
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}

.docx-block-card:hover {
  border-color: color-mix(in srgb, var(--brand) 40%, var(--border-color));
}

.docx-block-card.active,
.docx-block-card.citation-focus {
  border-color: var(--brand);
  background: color-mix(in srgb, var(--brand) 8%, var(--bg-primary));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--brand) 35%, transparent);
}

.docx-block-type {
  display: inline-block;
  font-size: 0.72rem;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.docx-block-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 0.84rem;
  line-height: 1.5;
  color: var(--text-primary);
  max-height: 8.5em;
  overflow: hidden;
}
</style>
