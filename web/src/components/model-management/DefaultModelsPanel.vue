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
      <label
        v-for="modelType in DEFAULT_MODEL_TYPES"
        :key="modelType"
        class="default-item"
        :class="{ 'default-item--picker-open': openPickerType === modelType }"
      >
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
          <div
            class="defaults-model-picker"
            :class="{ 'defaults-model-picker--open': openPickerType === modelType }"
          >
            <button
              type="button"
              class="defaults-model-trigger"
              :disabled="loading"
              :aria-expanded="openPickerType === modelType"
              aria-haspopup="listbox"
              :aria-label="`${MODEL_TYPE_LABEL_MAP[modelType]} 默认模型`"
              @click.stop="togglePicker(modelType)"
            >
              <span class="defaults-model-trigger-label" :title="triggerTitle(modelType)">{{
                triggerLabel(modelType)
              }}</span>
              <AppIcon
                name="chevron-down"
                :size="14"
                class="defaults-model-chevron"
                :class="{ 'is-open': openPickerType === modelType }"
              />
            </button>
            <div
              v-if="openPickerType === modelType"
              class="defaults-model-dropdown"
              role="presentation"
              @click.stop
            >
              <div class="defaults-model-list scrollbar-pill" role="listbox" :aria-label="`${MODEL_TYPE_LABEL_MAP[modelType]} 列表`">
                <button
                  type="button"
                  role="option"
                  class="defaults-model-option"
                  :class="{ 'is-current': draftSelections[modelType] === null }"
                  @click="selectOption(modelType, null)"
                >
                  <span class="defaults-model-option-name defaults-model-option-name--muted">请选择模型</span>
                </button>
                <template v-if="sortedGroupedEnabledOptionsMap[modelType]?.length">
                  <div
                    v-for="group in sortedGroupedEnabledOptionsMap[modelType]"
                    :key="`${modelType}-${group.providerName}`"
                    class="defaults-model-group"
                  >
                    <div class="defaults-model-group-title">{{ group.providerName }}</div>
                    <button
                      v-for="option in group.options"
                      :key="option.value"
                      type="button"
                      role="option"
                      class="defaults-model-option"
                      :class="{ 'is-current': draftSelections[modelType] === option.value }"
                      @click="selectOption(modelType, option.value)"
                    >
                      <span class="defaults-model-option-name">{{ option.label }}</span>
                    </button>
                  </div>
                </template>
                <div v-else class="defaults-model-empty">暂无已启用的该类型模型</div>
              </div>
            </div>
          </div>
        </div>
      </label>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

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

const openPickerType = ref<ModelType | null>(null)

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

const sortedGroupedEnabledOptionsMap = computed(() => {
  const raw = groupedEnabledOptionsMap.value
  const out = {} as Record<ModelType, ModelOptionGroup[]>
  DEFAULT_MODEL_TYPES.forEach((modelType) => {
    const groups = [...(raw[modelType] || [])].sort((a, b) =>
      a.providerName.localeCompare(b.providerName, 'zh-CN'),
    )
    out[modelType] = groups.map((g) => ({
      ...g,
      options: [...g.options].sort((a, b) => a.label.localeCompare(b.label, 'zh-CN')),
    }))
  })
  return out
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
    result[modelType] =
      (props.enabledOptionsMap[modelType] || []).find((option) => option.value === selectedValue) || null
  })

  return result
})

function triggerLabel(modelType: ModelType): string {
  const opt = selectedOptionMap.value[modelType]
  return opt?.label ?? '请选择模型'
}

function triggerTitle(modelType: ModelType): string {
  const opt = selectedOptionMap.value[modelType]
  return opt ? `${opt.label} · ${opt.providerName}` : ''
}

function togglePicker(modelType: ModelType) {
  if (props.loading) {
    return
  }
  openPickerType.value = openPickerType.value === modelType ? null : modelType
}

function selectOption(modelType: ModelType, value: number | null) {
  draftSelections.value[modelType] = value
  openPickerType.value = null
}

function onDocumentClick() {
  openPickerType.value = null
}

watch(
  () => props.defaults,
  (value) => {
    draftSelections.value = createSelections(value)
    openPickerType.value = null
  },
  { deep: true },
)

onMounted(() => {
  window.addEventListener('click', onDocumentClick)
})

onBeforeUnmount(() => {
  window.removeEventListener('click', onDocumentClick)
})

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
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
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

.select-shell {
  position: relative;
  z-index: 1;
}

.default-item--picker-open {
  z-index: 4;
}

.defaults-model-picker {
  position: relative;
  width: 100%;
}

.defaults-model-picker--open {
  z-index: 30;
}

.defaults-model-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  max-width: 100%;
  padding: 8px 12px;
  margin: 0;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  color: var(--text-primary);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
  box-sizing: border-box;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.defaults-model-trigger:hover:not(:disabled) {
  border-color: rgba(100, 116, 139, 0.45);
  background: var(--bg-secondary);
}

.defaults-model-trigger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.defaults-model-trigger-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.defaults-model-chevron {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform 0.15s ease;
}

.defaults-model-chevron.is-open {
  transform: rotate(180deg);
}

.defaults-model-dropdown {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 6px);
  z-index: 50;
}

.defaults-model-list {
  width: 100%;
  max-height: 280px;
  overflow-y: auto;
  padding: 8px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.6),
    0 10px 28px rgba(15, 23, 42, 0.14);
}

.defaults-model-group + .defaults-model-group {
  margin-top: 8px;
  padding-top: 10px;
  border-top: 1px solid rgba(148, 163, 184, 0.35);
}

.defaults-model-group-title {
  padding: 4px 10px 8px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.defaults-model-option {
  display: flex;
  width: 100%;
  padding: 10px 12px;
  margin-bottom: 2px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  font: inherit;
  transition: background 0.12s ease;
}

.defaults-model-option-name {
  font-size: 0.9rem;
  font-weight: 700;
  line-height: 1.3;
}

.defaults-model-option-name--muted {
  font-weight: 600;
  color: var(--text-tertiary);
}

.defaults-model-option:hover:not(.is-current) {
  background: var(--bg-tertiary);
}

.defaults-model-option.is-current {
  background: var(--brand-primary-light);
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.2);
}

.defaults-model-empty {
  padding: 12px;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  line-height: 1.5;
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
