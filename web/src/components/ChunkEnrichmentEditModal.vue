<template>
  <Teleport to="body">
    <div v-if="open" class="chunk-enrich-modal-overlay" @click.self="emit('close')">
      <div class="chunk-enrich-modal" role="dialog" aria-modal="true" :aria-labelledby="titleId">
        <header class="chunk-enrich-modal-head">
          <div>
            <h3 :id="titleId">编辑解析块</h3>
            <p v-if="chunk">Chunk-{{ chunk.chunk_index + 1 }} · {{ chunkCharCount }} 字符</p>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="emit('close')">
            <AppIcon name="close" :size="16" />
          </button>
        </header>

        <div class="chunk-enrich-modal-body">
          <label class="chunk-enrich-field">
            <span class="chunk-enrich-label">解析块</span>
            <div class="chunk-enrich-content-readonly">
              <div
                v-if="tableHtml"
                class="chunk-enrich-table-wrap"
                v-html="tableHtml"
              />
              <p v-else>{{ chunk?.content || '' }}</p>
            </div>
          </label>

          <div v-if="kindLabel" class="chunk-enrich-type-row">
            <span class="chunk-enrich-label">类型</span>
            <span class="chip">{{ kindLabel }}</span>
          </div>

          <TagListEditor
            v-model="draftKeywords"
            label="关键词"
            placeholder="输入关键词后回车"
            add-label="+ 添加关键词"
            :max-items="12"
          />

          <TagListEditor
            v-model="draftQuestions"
            label="问题"
            placeholder="输入假设问题后回车"
            add-label="+ 添加问题"
            :max-items="5"
            help="假设问题是用户可能提出的检索问法，入库增强时也会自动生成，用于提升召回匹配。"
          />

          <details v-if="chunk?.keyword_text" class="chunk-enrich-kw-preview">
            <summary>检索入库文本预览</summary>
            <pre>{{ chunk.keyword_text }}</pre>
          </details>

          <p v-if="errorText" class="chunk-enrich-error">{{ errorText }}</p>
        </div>

        <footer class="chunk-enrich-modal-foot">
          <button class="btn btn-ghost" type="button" :disabled="saving || regenerating" @click="emit('close')">
            取消 <span class="chunk-enrich-kbd">Esc</span>
          </button>
          <button
            class="btn btn-secondary"
            type="button"
            :disabled="saving || regenerating || !chunk"
            @click="onRegenerate"
          >
            {{ regenerating ? 'AI 生成中…' : 'AI 生成' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="saving || regenerating" @click="onSave">
            {{ saving ? '保存中…' : '保存' }} <span class="chunk-enrich-kbd">Ctrl S</span>
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { knowledgeBaseApi, type KnowledgeChunk, getKnowledgeBaseErrorMessage } from '../api/knowledge-base'
import AppIcon from './AppIcon.vue'
import TagListEditor from './TagListEditor.vue'

const props = defineProps<{
  open: boolean
  kbId: number
  chunk: KnowledgeChunk | null
  kindLabel?: string
  tableHtml?: string
}>()

const emit = defineEmits<{
  close: []
  saved: [chunk: KnowledgeChunk]
}>()

const titleId = `chunk-enrich-title-${Math.random().toString(36).slice(2, 9)}`
const draftKeywords = ref<string[]>([])
const draftQuestions = ref<string[]>([])
const saving = ref(false)
const regenerating = ref(false)
const errorText = ref('')

const chunkCharCount = computed(() => {
  if (!props.chunk) {
    return 0
  }
  if (typeof props.chunk.char_count === 'number' && props.chunk.char_count >= 0) {
    return props.chunk.char_count
  }
  return [...(props.chunk.content || '')].length
})

function syncDraftFromChunk() {
  errorText.value = ''
  if (!props.chunk) {
    draftKeywords.value = []
    draftQuestions.value = []
    return
  }
  draftKeywords.value = [...(props.chunk.enrichment_keywords ?? [])]
  draftQuestions.value = [...(props.chunk.enrichment_questions ?? [])]
}

watch(
  () => [props.open, props.chunk?.id, props.chunk?.updated_at] as const,
  () => {
    if (props.open) {
      syncDraftFromChunk()
    }
  },
  { immediate: true },
)

function onKeydown(event: KeyboardEvent) {
  if (!props.open) {
    return
  }
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('close')
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    event.preventDefault()
    void onSave()
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      window.addEventListener('keydown', onKeydown)
    } else {
      window.removeEventListener('keydown', onKeydown)
    }
  },
  { immediate: true },
)

async function onRegenerate() {
  if (!props.chunk) {
    return
  }
  regenerating.value = true
  errorText.value = ''
  try {
    const result = await knowledgeBaseApi.regenerateChunkEnrichment(props.kbId, props.chunk.id)
    draftKeywords.value = [...(result.keywords ?? [])]
    draftQuestions.value = [...(result.questions ?? [])]
  } catch (value) {
    errorText.value = getKnowledgeBaseErrorMessage(value, 'AI 生成失败')
  } finally {
    regenerating.value = false
  }
}

async function onSave() {
  if (!props.chunk) {
    return
  }
  saving.value = true
  errorText.value = ''
  try {
    const updated = await knowledgeBaseApi.updateChunkEnrichment(props.kbId, props.chunk.id, {
      keywords: draftKeywords.value,
      questions: draftQuestions.value,
    })
    emit('saved', updated)
    emit('close')
  } catch (value) {
    errorText.value = getKnowledgeBaseErrorMessage(value, '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.chunk-enrich-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(4px);
}

.chunk-enrich-modal {
  width: min(640px, 100%);
  max-height: min(88vh, 900px);
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  box-shadow: var(--card-shadow-lg, 0 24px 48px rgba(15, 23, 42, 0.18));
}

.chunk-enrich-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px 12px;
}

.chunk-enrich-modal-head h3 {
  margin: 0 0 4px;
  font-size: 1.1rem;
}

.chunk-enrich-modal-head p {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.chunk-enrich-modal-body {
  display: grid;
  gap: 18px;
  padding: 8px 22px 16px;
  overflow: auto;
}

.chunk-enrich-field {
  display: grid;
  gap: 8px;
}

.chunk-enrich-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.chunk-enrich-content-readonly {
  max-height: 180px;
  overflow: auto;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--text-primary);
}

.chunk-enrich-content-readonly p {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.chunk-enrich-type-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chunk-enrich-kw-preview {
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.chunk-enrich-kw-preview pre {
  margin: 8px 0 0;
  padding: 10px;
  border-radius: 8px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.78rem;
  max-height: 120px;
  overflow: auto;
}

.chunk-enrich-error {
  margin: 0;
  color: var(--danger-color, #dc2626);
  font-size: 0.85rem;
}

.chunk-enrich-modal-foot {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  padding: 14px 22px 20px;
  border-top: 1px solid var(--border-color);
}

.chunk-enrich-kbd {
  margin-left: 6px;
  font-size: 0.72rem;
  opacity: 0.65;
}

.chunk-enrich-table-wrap :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.chunk-enrich-table-wrap :deep(th),
.chunk-enrich-table-wrap :deep(td) {
  border: 1px solid var(--border-color);
  padding: 4px 8px;
}
</style>
