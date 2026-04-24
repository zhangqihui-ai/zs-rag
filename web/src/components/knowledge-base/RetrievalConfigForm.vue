<template>
  <div class="retrieval-config-form">
    <div class="retrieval-config-mode-field">
      <span class="field-label retrieval-config-mode-title">检索方法</span>
      <div class="retrieval-config-mode-list" role="radiogroup" aria-label="检索方法">
        <label
          v-for="option in modeOptions"
          :key="option.value"
          :class="[
            'retrieval-config-mode-card',
            { 'retrieval-config-mode-card--active': modeProxy === option.value },
          ]"
          role="radio"
          :aria-checked="modeProxy === option.value"
          :tabindex="modeProxy === option.value ? 0 : -1"
        >
          <input
            v-model="modeProxy"
            type="radio"
            class="retrieval-config-mode-radio"
            :value="option.value"
          />
          <span class="retrieval-config-mode-icon" aria-hidden="true">
            <AppIcon :name="option.icon" :size="18" />
          </span>
          <div class="retrieval-config-mode-text">
            <div class="retrieval-config-mode-heading">
              <span>{{ option.label }}</span>
              <span v-if="option.recommended" class="retrieval-config-mode-badge">推荐</span>
            </div>
            <p>{{ option.caption }}</p>
          </div>
        </label>
      </div>
    </div>

    <div class="retrieval-config-card">
      <template v-if="modeProxy === 'hybrid'">
        <div class="retrieval-config-strategy">
          <label
            :class="['retrieval-config-strategy-card', { active: hybridStrategyProxy === 'weight' }]"
            role="radio"
            :aria-checked="hybridStrategyProxy === 'weight'"
          >
            <input v-model="hybridStrategyProxy" type="radio" value="weight" />
            <div>
              <strong>权重设置</strong>
              <p>调整向量与关键词分支权重，优先语义或关键词匹配。</p>
            </div>
          </label>
          <label
            :class="['retrieval-config-strategy-card', { active: hybridStrategyProxy === 'rerank' }]"
            role="radio"
            :aria-checked="hybridStrategyProxy === 'rerank'"
          >
            <input v-model="hybridStrategyProxy" type="radio" value="rerank" />
            <div>
              <strong>Rerank 模型</strong>
              <p>使用重排序模型对候选结果再打分，提升召回质量。</p>
            </div>
          </label>
        </div>

        <div v-if="hybridStrategyProxy === 'weight'" class="retrieval-config-field">
          <div class="retrieval-config-slider-head">
            <span class="field-label">
              向量相似度权重
              <span class="retrieval-config-help" :title="helpVectorWeight" tabindex="0" role="note">?</span>
            </span>
            <input
              v-model.number="vectorWeightProxy"
              class="input retrieval-config-slider-input"
              type="number"
              min="0"
              max="1"
              step="0.01"
            />
          </div>
          <div class="retrieval-config-weight-slider" :style="weightSliderStyle">
            <input
              v-model.number="vectorWeightProxy"
              class="retrieval-config-weight-range"
              type="range"
              min="0"
              max="1"
              step="0.01"
              aria-label="向量相似度权重"
            />
            <div class="retrieval-config-weight-hint">
              <span class="retrieval-config-weight-hint-semantic">语义 {{ vectorWeightFormatted }}</span>
              <span class="retrieval-config-weight-hint-keyword">{{ keywordWeightFormatted }} 关键词</span>
            </div>
          </div>
        </div>

        <div v-else class="retrieval-config-field">
          <span class="field-label">Rerank 模型</span>
          <RerankModelPicker
            v-model="rerankModelIdProxy"
            :models="rerankModels"
            :loading="rerankLoading"
            :default-model="defaultRerankModel"
          />
        </div>
      </template>

      <template v-else>
        <div class="retrieval-config-field retrieval-config-field--switch">
          <label class="retrieval-config-switch-row">
            <span class="switch">
              <input v-model="rerankEnabledProxy" type="checkbox" />
            </span>
            <span class="field-label retrieval-config-switch-label">
              Rerank 模型
              <span class="retrieval-config-help" :title="helpRerank" tabindex="0" role="note">?</span>
            </span>
          </label>
          <RerankModelPicker
            v-if="rerankEnabledProxy"
            v-model="rerankModelIdProxy"
            :models="rerankModels"
            :loading="rerankLoading"
            :default-model="defaultRerankModel"
          />
        </div>
      </template>

      <div class="retrieval-config-grid">
        <div class="retrieval-config-field">
          <span class="field-label retrieval-config-field-label">
            Top K
            <span class="retrieval-config-help" :title="helpTopK" tabindex="0" role="note">?</span>
          </span>
          <div class="retrieval-config-slider-row">
            <input
              v-model.number="topKProxy"
              class="input retrieval-config-number-input"
              type="number"
              min="1"
              max="50"
              step="1"
            />
            <input
              v-model.number="topKProxy"
              class="retrieval-config-progress-range"
              type="range"
              min="1"
              max="20"
              step="1"
              :style="topKSliderStyle"
              aria-label="Top K"
            />
          </div>
        </div>

        <div class="retrieval-config-field">
          <span class="field-label retrieval-config-switch-inline">
            <span class="switch retrieval-config-switch-sm">
              <input v-model="scoreThresholdEnabledProxy" type="checkbox" />
            </span>
            <span class="retrieval-config-switch-text">Score 阈值</span>
            <span class="retrieval-config-help" :title="helpScoreThreshold" tabindex="0" role="note">?</span>
          </span>
          <div class="retrieval-config-slider-row">
            <input
              v-model.number="scoreThresholdProxy"
              class="input retrieval-config-number-input"
              type="number"
              min="0"
              max="1"
              step="0.01"
              :disabled="!scoreThresholdEnabledProxy"
            />
            <input
              v-model.number="scoreThresholdProxy"
              class="retrieval-config-progress-range"
              type="range"
              min="0"
              max="1"
              step="0.01"
              :disabled="!scoreThresholdEnabledProxy"
              :style="scoreThresholdSliderStyle"
              aria-label="Score 阈值"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import type { RetrievalMode } from '../../api/knowledge-base'
import {
  defaultModelApi,
  modelApi,
  type DefaultModelOption,
  type ModelItem,
} from '../../api/model-management'
import AppIcon from '../AppIcon.vue'
import RerankModelPicker from './RerankModelPicker.vue'

export type HybridStrategy = 'weight' | 'rerank'

export interface RetrievalFormState {
  mode: RetrievalMode
  top_k: number
  score_threshold_enabled: boolean
  score_threshold: number
  vector_weight: number
  hybrid_strategy: HybridStrategy
  rerank_enabled: boolean
  rerank_model_id: number | null
}

const props = defineProps<{ modelValue: RetrievalFormState }>()
const emit = defineEmits<{ (e: 'update:modelValue', value: RetrievalFormState): void }>()

interface ModeOption {
  value: RetrievalMode
  label: string
  caption: string
  icon: string
  recommended?: boolean
}

const modeOptions: ModeOption[] = [
  {
    value: 'vector',
    label: '向量检索',
    caption: '通过生成查询嵌入并查询与其向量表示最相似的文本分段。',
    icon: 'grip',
  },
  {
    value: 'keyword',
    label: '全文检索',
    caption: '索引文档中的所有词汇，从而允许用户查询任意词汇，并返回包含这些词的文本片段。',
    icon: 'knowledge',
  },
  {
    value: 'hybrid',
    label: '混合检索',
    caption:
      '同时执行全文检索和向量检索，并应用重排序步骤，从两类查询结果中选择匹配用户问题的最佳结果，用户可以选择设置权重或配置重新排序模型。',
    icon: 'dashboard',
    recommended: true,
  },
]

const helpVectorWeight =
  '向量相似度权重：向量分支与全文（关键词）分支的权重之和为 1.0。调大向量权重偏向语义匹配，调大全文权重偏向关键词命中。'
const helpRerank =
  'Rerank 模型将根据候选文档列表与用户问题的语义匹配度进行重新排序，从而改进语义排序的结果。'
const helpTopK = 'Top K：召回返回的候选结果数量。数值越大召回越多，但噪声也可能增加。'
const helpScoreThreshold =
  '相似度阈值：用于过滤低相关度结果。开启后，低于该阈值的候选片段会被过滤；关闭则不过滤。开启 Rerank 后，阈值作用于 Rerank 模型输出分数，请重新标定。'

function emitPatch(patch: Partial<RetrievalFormState>) {
  emit('update:modelValue', { ...props.modelValue, ...patch })
}

function makeProxy<K extends keyof RetrievalFormState>(key: K) {
  return computed<RetrievalFormState[K]>({
    get: () => props.modelValue[key],
    set: (value) => emitPatch({ [key]: value } as Partial<RetrievalFormState>),
  })
}

const modeProxy = makeProxy('mode')
const topKProxy = makeProxy('top_k')
const scoreThresholdEnabledProxy = makeProxy('score_threshold_enabled')
const scoreThresholdProxy = makeProxy('score_threshold')
const vectorWeightProxy = makeProxy('vector_weight')
const hybridStrategyProxy = makeProxy('hybrid_strategy')
const rerankEnabledProxy = makeProxy('rerank_enabled')
const rerankModelIdProxy = makeProxy('rerank_model_id')

const rerankModels = ref<ModelItem[]>([])
const rerankLoading = ref(false)
const defaultRerankModel = ref<DefaultModelOption | null>(null)

const vectorWeightFormatted = computed(() => {
  const clamped = Math.min(Math.max(vectorWeightProxy.value, 0), 1)
  return clamped.toFixed(2)
})

const keywordWeightFormatted = computed(() => {
  const clamped = Math.min(Math.max(vectorWeightProxy.value, 0), 1)
  return (1 - clamped).toFixed(2)
})

const weightSliderStyle = computed(() => {
  const clamped = Math.min(Math.max(vectorWeightProxy.value, 0), 1)
  return { '--weight-split': `${(clamped * 100).toFixed(2)}%` } as Record<string, string>
})

const topKSliderStyle = computed(() => {
  const min = 1
  const max = 20
  const raw = Number.isFinite(topKProxy.value) ? topKProxy.value : min
  const clamped = Math.min(Math.max(raw, min), max)
  const pct = ((clamped - min) / (max - min)) * 100
  return { '--progress': `${pct.toFixed(2)}%` } as Record<string, string>
})

const scoreThresholdSliderStyle = computed(() => {
  const raw = Number.isFinite(scoreThresholdProxy.value) ? scoreThresholdProxy.value : 0
  const clamped = Math.min(Math.max(raw, 0), 1)
  return { '--progress': `${(clamped * 100).toFixed(2)}%` } as Record<string, string>
})

async function loadRerankModels() {
  rerankLoading.value = true
  try {
    const [modelsData, defaultsData] = await Promise.all([
      modelApi.getModels({ model_type: 'rerank', is_enabled: true, view: 'flat' }),
      defaultModelApi.getDefaults(),
    ])
    rerankModels.value = modelsData as ModelItem[]
    defaultRerankModel.value = defaultsData.rerank ?? null
  } catch {
    // 静默失败：父级组件仍然可以正常工作，只是下拉框为空。
  } finally {
    rerankLoading.value = false
  }
}

watch(
  [() => props.modelValue.rerank_enabled, () => props.modelValue.hybrid_strategy],
  () => {
    // 当用户打开/切换到 Rerank 策略时：若 Score 阈值是基于非 rerank 分数调好的，
    // 其数值含义会失效。此处自动关闭阈值避免误过滤，用户可重新打开。
    const rerankActive =
      (props.modelValue.mode !== 'hybrid' && props.modelValue.rerank_enabled) ||
      (props.modelValue.mode === 'hybrid' && props.modelValue.hybrid_strategy === 'rerank')
    if (rerankActive && props.modelValue.score_threshold_enabled) {
      emitPatch({ score_threshold_enabled: false })
    }
  },
)

onMounted(() => {
  loadRerankModels()
})
</script>

<style scoped>
.retrieval-config-form {
  display: grid;
  gap: 16px;
}

.retrieval-config-mode-field {
  display: grid;
  gap: 10px;
}

.retrieval-config-mode-title {
  color: var(--text-primary);
  font-weight: 600;
  font-size: 0.92rem;
}

.retrieval-config-mode-list {
  display: grid;
  gap: 10px;
}

.retrieval-config-mode-card {
  display: grid;
  grid-template-columns: 32px 1fr;
  gap: 12px;
  align-items: start;
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--bg-tertiary);
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
  position: relative;
}

.retrieval-config-mode-card:hover {
  border-color: var(--brand-primary-light, rgba(59, 130, 246, 0.5));
}

.retrieval-config-mode-card--active {
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 1px var(--brand-primary-light);
  background: var(--bg-elevated);
}

.retrieval-config-mode-radio {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.retrieval-config-mode-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--bg-elevated);
  color: var(--brand-primary);
  border: 1px solid var(--border-color);
}

.retrieval-config-mode-card--active .retrieval-config-mode-icon {
  background: var(--brand-primary-light, rgba(59, 130, 246, 0.12));
  border-color: transparent;
}

.retrieval-config-mode-text {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.retrieval-config-mode-heading {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

.retrieval-config-mode-badge {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--brand-primary);
  background: var(--brand-primary-light, rgba(59, 130, 246, 0.12));
  border: 1px solid var(--brand-primary-light, rgba(59, 130, 246, 0.32));
}

.retrieval-config-mode-text p {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.retrieval-config-card {
  display: grid;
  gap: 16px;
  padding: 18px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-elevated);
}

.retrieval-config-strategy {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.retrieval-config-strategy-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--bg-tertiary);
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.retrieval-config-strategy-card.active {
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 1px var(--brand-primary-light);
}

.retrieval-config-strategy-card input {
  margin-top: 4px;
  accent-color: var(--brand-primary);
}

.retrieval-config-strategy-card strong {
  display: block;
  font-size: 0.92rem;
  color: var(--text-primary);
}

.retrieval-config-strategy-card p {
  margin: 4px 0 0;
  font-size: 0.84rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.retrieval-config-field {
  display: grid;
  gap: 8px;
}

.retrieval-config-field--switch {
  gap: 12px;
}

.retrieval-config-switch-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.retrieval-config-switch-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--text-primary);
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
}

.retrieval-config-switch-inline {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.retrieval-config-switch-text {
  color: var(--text-primary);
  font-weight: 600;
  font-size: 0.9rem;
}

.retrieval-config-switch-sm {
  width: 34px;
  height: 20px;
}

.retrieval-config-switch-sm input {
  width: 34px;
  height: 20px;
}

.retrieval-config-switch-sm input::after {
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
}

.retrieval-config-switch-sm input:checked::after {
  transform: translateX(14px);
}

.retrieval-config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.retrieval-config-slider-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.retrieval-config-slider-input {
  width: 92px;
  text-align: center;
}

.retrieval-config-field-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--text-primary);
  font-weight: 600;
  font-size: 0.9rem;
}

.retrieval-config-slider-row {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.retrieval-config-number-input {
  flex: 0 0 auto;
  width: 92px;
  min-width: 0;
  padding: 4px 8px;
  text-align: left;
}

.retrieval-config-progress-range {
  --progress: 0%;
  --progress-color: var(--brand-primary, #3b82f6);
  --progress-track: rgba(59, 130, 246, 0.12);
  -webkit-appearance: none;
  appearance: none;
  flex: 1 1 auto;
  min-width: 0;
  height: 6px;
  margin: 0;
  border-radius: 999px;
  outline: none;
  cursor: pointer;
  background: linear-gradient(
    to right,
    var(--progress-color) 0%,
    var(--progress-color) var(--progress),
    var(--progress-track) var(--progress),
    var(--progress-track) 100%
  );
}

.retrieval-config-progress-range::-webkit-slider-runnable-track {
  height: 6px;
  border-radius: 999px;
  background: transparent;
}

.retrieval-config-progress-range::-moz-range-track {
  height: 6px;
  border-radius: 999px;
  background: transparent;
}

.retrieval-config-progress-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  margin-top: -6px;
  border-radius: 50%;
  background: #ffffff;
  border: 1px solid var(--border-strong, #d1d5db);
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.2);
  cursor: pointer;
  transition: transform 0.15s ease;
}

.retrieval-config-progress-range::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #ffffff;
  border: 1px solid var(--border-strong, #d1d5db);
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.2);
  cursor: pointer;
  transition: transform 0.15s ease;
}

.retrieval-config-progress-range::-webkit-slider-thumb:hover,
.retrieval-config-progress-range:focus::-webkit-slider-thumb {
  transform: scale(1.08);
}

.retrieval-config-progress-range::-moz-range-thumb:hover,
.retrieval-config-progress-range:focus::-moz-range-thumb {
  transform: scale(1.08);
}

.retrieval-config-progress-range:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.retrieval-config-progress-range:disabled::-webkit-slider-thumb {
  cursor: not-allowed;
  box-shadow: none;
}

.retrieval-config-progress-range:disabled::-moz-range-thumb {
  cursor: not-allowed;
  box-shadow: none;
}

.retrieval-config-weight-slider {
  --semantic-color: #3b82f6;
  --keyword-color: #10b981;
  --weight-split: 50%;
  display: grid;
  gap: 8px;
}

.retrieval-config-weight-range {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 6px;
  margin: 0;
  border-radius: 999px;
  outline: none;
  cursor: pointer;
  background: linear-gradient(
    to right,
    var(--semantic-color) 0%,
    var(--semantic-color) var(--weight-split),
    var(--keyword-color) var(--weight-split),
    var(--keyword-color) 100%
  );
}

.retrieval-config-weight-range::-webkit-slider-runnable-track {
  height: 6px;
  border-radius: 999px;
  background: transparent;
}

.retrieval-config-weight-range::-moz-range-track {
  height: 6px;
  border-radius: 999px;
  background: transparent;
}

.retrieval-config-weight-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  margin-top: -6px;
  border-radius: 50%;
  background: #ffffff;
  border: 1px solid var(--border-strong, #d1d5db);
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.2);
  cursor: pointer;
  transition: transform 0.15s ease;
}

.retrieval-config-weight-range::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #ffffff;
  border: 1px solid var(--border-strong, #d1d5db);
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.2);
  cursor: pointer;
  transition: transform 0.15s ease;
}

.retrieval-config-weight-range::-webkit-slider-thumb:hover,
.retrieval-config-weight-range:focus::-webkit-slider-thumb {
  transform: scale(1.08);
}

.retrieval-config-weight-range::-moz-range-thumb:hover,
.retrieval-config-weight-range:focus::-moz-range-thumb {
  transform: scale(1.08);
}

.retrieval-config-weight-range:focus {
  outline: none;
}

.retrieval-config-weight-hint {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  font-weight: 600;
}

.retrieval-config-weight-hint-semantic {
  color: var(--semantic-color);
}

.retrieval-config-weight-hint-keyword {
  color: var(--keyword-color);
}

.retrieval-config-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  margin-left: 4px;
  border-radius: 50%;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-tertiary);
  border: 1px solid var(--border-color);
  cursor: help;
  vertical-align: middle;
}

@media (max-width: 900px) {
  .retrieval-config-strategy,
  .retrieval-config-grid {
    grid-template-columns: 1fr;
  }
}
</style>
