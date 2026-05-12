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
import { retrievalFormFromKnowledgeBase, type StoredRetrievalConfig } from './retrieval-form'

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

function validate(): string | null {
  const f = form.value
  if (f.top_k < 1 || f.top_k > 50 || !Number.isFinite(f.top_k)) {
    return 'Top K 取值范围为 1~50。'
  }
  if (f.score_threshold_enabled) {
    if (f.score_threshold < 0 || f.score_threshold > 1 || !Number.isFinite(f.score_threshold)) {
      return 'Score 阈值取值范围为 0~1。'
    }
  }
  if (f.mode === 'hybrid') {
    if (f.hybrid_strategy === 'weight') {
      if (f.vector_weight < 0 || f.vector_weight > 1 || !Number.isFinite(f.vector_weight)) {
        return '向量相似度权重取值范围为 0~1。'
      }
    } else if (!f.rerank_model_id) {
      return '请选择一个 Rerank 模型或切换到权重设置。'
    }
  } else if (f.rerank_enabled && !f.rerank_model_id) {
    return '已启用 Rerank，请选择一个 Rerank 模型。'
  }
  return null
}

async function save() {
  const err = validate()
  if (err) {
    message.value = err
    messageType.value = 'err'
    return
  }
  saving.value = true
  message.value = ''
  try {
    const f = form.value
    const prev = (props.knowledgeBase.config || {}) as Record<string, unknown>
    const retrievalStored: StoredRetrievalConfig = {
      vector_weight: f.vector_weight,
      hybrid_strategy: f.hybrid_strategy,
      rerank_enabled: f.rerank_enabled,
      rerank_model_id:
        f.mode === 'hybrid'
          ? f.hybrid_strategy === 'rerank'
            ? f.rerank_model_id
            : null
          : f.rerank_enabled
            ? f.rerank_model_id
            : null,
      score_threshold_enabled: f.score_threshold_enabled,
    }
    const nextConfig = { ...prev, retrieval: retrievalStored } as Record<string, unknown>
    const payload = {
      default_retrieval_mode: f.mode,
      default_top_k: Math.round(f.top_k),
      default_score_threshold: f.score_threshold_enabled ? f.score_threshold : null,
      config: nextConfig,
    }
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
