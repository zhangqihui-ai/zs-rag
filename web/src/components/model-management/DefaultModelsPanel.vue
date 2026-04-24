<template>
  <section class="panel defaults-panel">
    <div class="panel-header">
      <div>
        <h2>默认模型设置</h2>
      </div>
      <button class="primary-btn" :disabled="saving || loading" @click="handleSave">
        {{ saving ? '保存中...' : '保存设置' }}
      </button>
    </div>

    <div v-if="loading" class="panel-placeholder">正在加载默认模型...</div>
    <div v-else class="default-card">
      <label v-for="modelType in DEFAULT_MODEL_TYPES" :key="modelType" class="default-item">
        <span class="default-label-block">
          <span class="default-label">
            <span v-if="modelType === 'llm'" class="required-mark">*</span>
            {{ MODEL_TYPE_LABEL_MAP[modelType] }}
            <span class="hint-wrap" tabindex="0" role="note" :aria-label="`${MODEL_TYPE_LABEL_MAP[modelType]} 类型说明`">
              <span class="hint-icon">i</span>
              <span class="hint-tooltip">{{ MODEL_TYPE_DESC_MAP[modelType] }}</span>
            </span>
          </span>
        </span>

        <div class="select-shell">
          <select v-model="draftSelections[modelType]" class="default-select">
            <option :value="null">请选择模型</option>
            <optgroup
              v-for="group in groupedEnabledOptionsMap[modelType] || []"
              :key="`${modelType}-${group.providerName}`"
              :label="group.providerName"
            >
              <option v-for="option in group.options" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </optgroup>
          </select>
          <AppIcon name="chevron-down" class="select-arrow" :size="16" />
        </div>
      </label>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { MODEL_TYPE_LABEL_MAP, type DefaultsData, type ModelType } from '../../api/model-management'
import AppIcon from '../AppIcon.vue'

interface ModelOption {
  label: string
  value: number
  providerName: string
}

interface ModelOptionGroup {
  providerName: string
  options: ModelOption[]
}

const DEFAULT_MODEL_TYPES: ModelType[] = ['llm', 'embedding', 'vlm', 'asr', 'rerank', 'tts']

const MODEL_TYPE_DESC_MAP: Record<ModelType, string> = {
  llm: '通用大语言模型，适合对话、问答、内容生成与推理。',
  embedding: '向量模型，用于把文本转成向量，常用于检索、召回和相似度匹配。',
  rerank: '重排序模型，用于对召回结果二次排序，提升检索结果相关性。',
  tts: '语音合成模型，用于把文本转换成语音。',
  asr: '语音识别模型，用于把音频内容转换成文本。',
  vlm: '视觉语言模型，既能理解图片，也能结合文本进行分析与回答。',
  moderation: '内容审核模型，用于识别违规、敏感或不安全内容。',
  ocr: '文字识别模型，用于从图片或扫描件中提取文本。',
}

const props = defineProps<{
  defaults: DefaultsData
  enabledOptionsMap: Record<ModelType, ModelOption[]>
  loading: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  save: [payload: Record<ModelType, number | null>]
}>()

const createSelections = (defaults: DefaultsData): Record<ModelType, number | null> => ({
  llm: defaults.llm?.model_id ?? null,
  embedding: defaults.embedding?.model_id ?? null,
  vlm: defaults.vlm?.model_id ?? null,
  asr: defaults.asr?.model_id ?? null,
  rerank: defaults.rerank?.model_id ?? null,
  tts: defaults.tts?.model_id ?? null,
  moderation: null,
  ocr: null,
})

const draftSelections = ref<Record<ModelType, number | null>>(createSelections(props.defaults))

const groupedEnabledOptionsMap = computed(() => {
  const result = {
    llm: [],
    embedding: [],
    rerank: [],
    tts: [],
    asr: [],
    vlm: [],
    moderation: [],
    ocr: [],
  } as Record<ModelType, ModelOptionGroup[]>

  ;(Object.keys(props.enabledOptionsMap) as ModelType[]).forEach((modelType) => {
    const providerMap = new Map<string, ModelOption[]>()

    ;(props.enabledOptionsMap[modelType] || []).forEach((option) => {
      const options = providerMap.get(option.providerName) || []
      options.push(option)
      providerMap.set(option.providerName, options)
    })

    result[modelType] = Array.from(providerMap.entries()).map(([providerName, options]) => ({
      providerName,
      options,
    }))
  })

  return result
})

const selectedOptionMap = computed(() => {
  const result = {
    llm: null,
    embedding: null,
    rerank: null,
    tts: null,
    asr: null,
    vlm: null,
    moderation: null,
    ocr: null,
  } as Record<ModelType, ModelOption | null>

  ;(Object.keys(props.enabledOptionsMap) as ModelType[]).forEach((modelType) => {
    const selectedValue = draftSelections.value[modelType]
    result[modelType] = (props.enabledOptionsMap[modelType] || []).find((option) => option.value === selectedValue) || null
  })

  return result
})

watch(
  () => props.defaults,
  (value) => {
    draftSelections.value = createSelections(value)
  },
  { deep: true },
)

const handleSave = () => {
  emit('save', { ...draftSelections.value, moderation: null, ocr: null })
}
</script>

<style scoped>
.panel {
  display: grid;
  gap: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.panel-header h2 {
  position: relative;
  display: inline-flex;
  align-items: center;
  margin: 0;
  padding-bottom: 8px;
  font-size: calc(var(--model-font-title, 15px) + 1px);
  font-weight: 700;
  letter-spacing: 0.02em;
  line-height: 1.35;
  color: var(--text-primary);
}

.panel-header h2::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: 0;
  width: 30px;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--brand-primary) 0%, rgba(37, 99, 235, 0.18) 100%);
}

.panel-header p {
  margin: 8px 0 0;
  color: var(--text-tertiary);
  font-size: 0.92rem;
  line-height: 1.6;
}

.primary-btn {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--brand-primary);
  color: #ffffff;
  font-weight: 600;
  padding: 10px 16px;
  cursor: pointer;
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.default-card {
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-secondary);
  padding: 8px 20px;
  box-shadow: var(--card-shadow-xs);
  overflow: visible;
}

.default-item {
  position: relative;
  display: grid;
  grid-template-columns: minmax(180px, 220px) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
  padding: 16px 0;
  overflow: visible;
}

.default-item + .default-item {
  border-top: 1px solid var(--border-color);
}

.default-label-block {
  display: grid;
  padding-top: 12px;
}

.default-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  font-size: var(--model-font-body, 12px);
  font-weight: 600;
  line-height: 1.5;
}

.required-mark {
  color: #ef4444;
}

.hint-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  cursor: help;
  outline: none;
  isolation: isolate;
}

.hint-icon {
  font-size: var(--model-font-chip, 10px);
  font-style: normal;
  font-weight: 700;
  line-height: 1;
}

.hint-tooltip {
  position: absolute;
  top: 50%;
  left: calc(100% + 14px);
  z-index: 120;
  width: max-content;
  max-width: min(320px, calc(100vw - 180px));
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.96);
  color: #ffffff;
  font-size: var(--model-font-subtitle, 13px);
  line-height: 1.7;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.24);
  white-space: normal;
  word-break: break-word;
  opacity: 0;
  pointer-events: none;
  transform: translateX(-8px) translateY(-50%);
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.hint-tooltip::before {
  content: '';
  position: absolute;
  top: 50%;
  left: -6px;
  width: 12px;
  height: 12px;
  border-radius: 3px;
  background: inherit;
  transform: translateY(-50%) rotate(45deg);
}

.hint-wrap:hover,
.hint-wrap:focus-visible {
  z-index: 20;
}

.hint-wrap:hover .hint-tooltip,
.hint-wrap:focus-visible .hint-tooltip {
  opacity: 1;
  transform: translateX(0) translateY(-50%);
}

.select-stack {
  display: grid;
  gap: 8px;
}

.select-shell {
  position: relative;
}

.default-select {
  width: 100%;
  min-height: 48px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  color: var(--text-primary);
  padding: 0 42px 0 14px;
  font-size: var(--model-font-body, 12px);
  font-weight: 600;
  appearance: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.default-select:hover {
  border-color: var(--border-strong);
}

.default-select:focus {
  outline: none;
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 3px var(--brand-primary-light);
}

.select-arrow {
  position: absolute;
  top: 50%;
  right: 14px;
  color: var(--text-tertiary);
  pointer-events: none;
  transform: translateY(-50%);
}


.panel-placeholder {
  padding: 32px 0;
  color: var(--text-tertiary);
  text-align: center;
}

@media (max-width: 768px) {
  .panel-header {
    flex-direction: column;
    align-items: stretch;
  }

  .default-item {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .default-label-block {
    padding-top: 0;
  }

  .hint-tooltip {
    top: calc(100% + 10px);
    left: 0;
    max-width: min(280px, calc(100vw - 72px));
    transform: translateY(-4px);
  }

  .hint-tooltip::before {
    top: -6px;
    left: 16px;
    transform: rotate(45deg);
  }

  .hint-wrap:hover .hint-tooltip,
  .hint-wrap:focus-visible .hint-tooltip {
    transform: translateY(0);
  }
}
</style>
