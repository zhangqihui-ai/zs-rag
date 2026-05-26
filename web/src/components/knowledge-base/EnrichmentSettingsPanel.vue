<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { getKnowledgeBaseErrorMessage, knowledgeBaseApi, type KnowledgeBase } from '../../api/knowledge-base'
import {
  defaultModelApi,
  getErrorMessage as getModelErrorMessage,
  modelApi,
  type DefaultModelOption,
  type ModelItem,
} from '../../api/model-management'
import AppIcon from '../AppIcon.vue'

const DEFAULT_ENRICHMENT = {
  enabled: false,
  llm_id: null,
  generate_keywords: true,
  generate_questions: true,
  max_questions: 3,
}

const props = defineProps<{
  knowledgeBase: KnowledgeBase
}>()

const emit = defineEmits<{
  saved: [kb: KnowledgeBase]
}>()

const expanded = ref(false)
const saving = ref(false)
const llmModels = ref<ModelItem[]>([])
const llmModelsLoading = ref(false)
const defaultLlmModel = ref<DefaultModelOption | null>(null)

function enrichmentConfig(): Record<string, unknown> {
  const cfg = (props.knowledgeBase.config || {}) as Record<string, unknown>
  const raw = cfg.enrichment
  const base = { ...DEFAULT_ENRICHMENT }
  if (raw && typeof raw === 'object') {
    return { ...base, ...(raw as Record<string, unknown>) }
  }
  return base
}

const enabled = computed(() => enrichmentConfig().enabled === true)

const llmId = computed(() => {
  const raw = enrichmentConfig().llm_id
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : null
})

async function loadLlmModels() {
  if (!props.knowledgeBase?.id) {
    return
  }
  llmModelsLoading.value = true
  try {
    const [modelsData, defaultsData] = await Promise.all([
      modelApi.getModels({ model_type: 'llm', is_enabled: true, view: 'flat' }),
      defaultModelApi.getDefaults(),
    ])
    llmModels.value = modelsData as ModelItem[]
    defaultLlmModel.value = defaultsData.llm
  } catch (e) {
    console.error(getModelErrorMessage(e, '加载 LLM 列表失败'))
  } finally {
    llmModelsLoading.value = false
  }
}

async function saveEnrichment(patch: Record<string, unknown>) {
  if (!props.knowledgeBase.id) {
    return
  }
  saving.value = true
  try {
    const prev = (props.knowledgeBase.config || {}) as Record<string, unknown>
    const prevEnrichment = (prev.enrichment && typeof prev.enrichment === 'object'
      ? prev.enrichment
      : {}) as Record<string, unknown>
    const nextConfig = {
      ...prev,
      enrichment: { ...DEFAULT_ENRICHMENT, ...prevEnrichment, ...patch },
    }
    const updated = await knowledgeBaseApi.update(props.knowledgeBase.id, { config: nextConfig })
    emit('saved', updated)
  } catch (e) {
    alert(getKnowledgeBaseErrorMessage(e, '保存入库增强配置失败'))
  } finally {
    saving.value = false
  }
}

async function onEnabledChange(evt: Event) {
  await saveEnrichment({ enabled: (evt.target as HTMLInputElement).checked })
}

async function onLlmChange(evt: Event) {
  const val = (evt.target as HTMLSelectElement).value
  await saveEnrichment({ llm_id: val ? Number(val) : null })
}

onMounted(() => {
  void loadLlmModels()
})

watch(
  () => props.knowledgeBase?.id,
  () => {
    void loadLlmModels()
  },
)
</script>

<template>
  <div class="enrichment-settings">
    <div class="enrichment-header">
      <div class="enrichment-title-row">
        <h4 class="enrichment-title">入库增强</h4>
        <p class="enrichment-sub">
          索引前用 LLM 为每个切片生成关键词与假设问题，提升检索匹配；会增加索引耗时与 LLM 费用。
        </p>
      </div>
      <button class="btn btn-ghost enrichment-toggle-btn" type="button" @click="expanded = !expanded">
        <AppIcon :name="expanded ? 'chevron-up' : 'chevron-down'" :size="16" />
        {{ expanded ? '收起' : '展开' }}
      </button>
    </div>

    <template v-if="expanded">
      <div class="enrichment-rows">
        <div class="enrichment-row">
          <label class="enrichment-label">启用</label>
          <div class="enrichment-field">
            <label class="enrichment-check">
              <input type="checkbox" :checked="enabled" :disabled="saving" @change="onEnabledChange" />
              启用入库 LLM 增强
            </label>
          </div>
        </div>

        <div v-if="enabled" class="enrichment-row">
          <label class="enrichment-label">LLM 模型</label>
          <div class="enrichment-field">
            <div class="custom-select-wrap">
              <select
                v-if="!llmModelsLoading"
                class="custom-select"
                :value="llmId ?? ''"
                :disabled="saving"
                @change="onLlmChange"
              >
                <option value="">
                  默认{{ defaultLlmModel ? `（${defaultLlmModel.model_name}）` : '' }}
                </option>
                <option v-for="model in llmModels" :key="model.id" :value="model.id">
                  {{ model.model_name }}（{{ model.provider_name }}）
                </option>
              </select>
              <span v-else class="enrichment-loading">加载中…</span>
              <span class="custom-select-arrow"><AppIcon name="chevron-down" :size="14" /></span>
            </div>
            <p class="enrichment-hint">未指定时使用企业空间默认 LLM。重新索引文档后生效。</p>
          </div>
        </div>
      </div>
      <span v-if="saving" class="enrichment-saving">保存中…</span>
    </template>
  </div>
</template>

<style scoped>
.enrichment-settings {
  display: grid;
  gap: 12px;
  margin-top: 8px;
}

.enrichment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.enrichment-title-row {
  display: grid;
  gap: 4px;
}

.enrichment-title {
  margin: 0;
  font-size: 1.05rem;
  color: var(--text-primary);
}

.enrichment-sub {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.enrichment-toggle-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 32px;
  padding: 4px 12px;
  font-size: 0.85rem;
  border-radius: 10px;
}

.enrichment-rows {
  display: grid;
  gap: 14px;
}

.enrichment-row {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 12px;
  align-items: start;
}

.enrichment-label {
  font-weight: 600;
  font-size: 0.92rem;
  color: var(--text-primary);
  padding-top: 8px;
}

.enrichment-field {
  display: grid;
  gap: 6px;
}

.enrichment-check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.enrichment-hint {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.enrichment-saving,
.enrichment-loading {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.custom-select-wrap {
  position: relative;
  max-width: 420px;
}

.custom-select {
  width: 100%;
  appearance: none;
  padding: 8px 36px 8px 12px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-size: 0.9rem;
}

.custom-select-arrow {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--text-secondary);
}
</style>
