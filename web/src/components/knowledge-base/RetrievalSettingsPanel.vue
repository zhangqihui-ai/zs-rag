<template>
  <div class="retrieval-settings">
    <div class="retrieval-settings-header">
      <div class="retrieval-settings-title-row">
        <h4 class="retrieval-settings-title">检索设置</h4>
        <p class="retrieval-settings-sub">
          选择知识库默认的检索方式，并配置 Top K、Rerank 模型等参数。保存后对问答与检索测试生效。
        </p>
      </div>
      <button class="btn btn-ghost retrieval-settings-toggle-btn" type="button" @click="expanded = !expanded">
        <AppIcon :name="expanded ? 'chevron-up' : 'chevron-down'" :size="16" />
        {{ expanded ? '收起' : '展开' }}
      </button>
    </div>

    <template v-if="expanded">
      <RetrievalConfigForm v-model="form" />

      <div class="retrieval-settings-footer">
        <button class="btn btn-primary" type="button" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存' }}
        </button>
        <button class="btn btn-ghost" type="button" :disabled="saving" @click="resetFromKnowledgeBase">重置</button>
        <p v-if="message" :class="['retrieval-settings-message', messageType === 'ok' ? 'ok' : 'err']">{{ message }}</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import {
  getKnowledgeBaseErrorMessage,
  knowledgeBaseApi,
  type KnowledgeBase,
} from '../../api/knowledge-base'
import AppIcon from '../AppIcon.vue'
import RetrievalConfigForm, { type RetrievalFormState } from './RetrievalConfigForm.vue'
import {
  buildRetrievalUpdatePayload,
  retrievalFormFromKnowledgeBase,
  validateRetrievalForm,
} from './retrieval-form'

const props = defineProps<{ knowledgeBase: KnowledgeBase }>()
const emit = defineEmits<{ (e: 'saved', value: KnowledgeBase): void }>()

const expanded = ref(false)
const saving = ref(false)
const message = ref('')
const messageType = ref<'ok' | 'err'>('ok')

const form = ref<RetrievalFormState>(retrievalFormFromKnowledgeBase(props.knowledgeBase))

function resetFromKnowledgeBase() {
  form.value = retrievalFormFromKnowledgeBase(props.knowledgeBase)
  message.value = ''
}

async function save() {
  const err = validateRetrievalForm(form.value)
  if (err) {
    message.value = err
    messageType.value = 'err'
    return
  }
  saving.value = true
  message.value = ''
  try {
    const payload = buildRetrievalUpdatePayload(form.value, props.knowledgeBase.config)
    const updated = await knowledgeBaseApi.update(props.knowledgeBase.id, payload)
    message.value = '检索设置已保存。'
    messageType.value = 'ok'
    emit('saved', updated)
  } catch (error) {
    message.value = getKnowledgeBaseErrorMessage(error, '保存检索设置失败')
    messageType.value = 'err'
  } finally {
    saving.value = false
  }
}

watch(
  () => props.knowledgeBase.id,
  () => {
    resetFromKnowledgeBase()
  },
)

watch(
  form,
  () => {
    if (message.value) {
      message.value = ''
    }
  },
  { deep: true },
)

onMounted(() => {
  resetFromKnowledgeBase()
})
</script>

<style scoped>
.retrieval-settings {
  display: grid;
  gap: 16px;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid var(--border-color);
}

.retrieval-settings-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.retrieval-settings-title-row {
  display: grid;
  gap: 4px;
}

.retrieval-settings-title {
  margin: 0;
  font-size: 1.05rem;
  color: var(--text-primary);
}

.retrieval-settings-sub {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.retrieval-settings-toggle-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 32px;
  padding: 4px 12px;
  font-size: 0.85rem;
  border-radius: 10px;
}

.retrieval-settings-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.retrieval-settings-message {
  margin: 0;
  font-size: 0.9rem;
}

.retrieval-settings-message.ok {
  color: var(--success-color);
}

.retrieval-settings-message.err {
  color: var(--danger-color);
}
</style>
