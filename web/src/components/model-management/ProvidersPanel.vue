<template>
  <section class="panel providers-panel">
    <div class="panel-header">
      <div>
        <h2>已接入厂商与模型</h2>
      </div>
    </div>

    <div v-if="loading" class="panel-placeholder">正在加载厂商与模型...</div>
    <div v-else-if="providers.length === 0" class="panel-placeholder">暂无已接入厂商，请从右侧模板开始接入</div>
    <div v-else class="provider-list">
      <article v-for="provider in providers" :key="provider.id" class="provider-card">
        <div class="provider-top">
          <div class="provider-info" :tabindex="provider.remark || provider.last_sync_at ? 0 : -1">
            <span class="provider-mark">{{ getProviderMark(provider.provider_name) }}</span>
            <div class="provider-body">
              <div class="provider-title-row">
                <h3>{{ provider.provider_name }}</h3>
                <span class="provider-url">{{ provider.base_url }}</span>
              </div>
              <div class="tag-group">
                <span v-for="type in provider.supported_types" :key="type" class="tag subtle-tag">
                  {{ MODEL_TYPE_LABEL_MAP[type] }}
                </span>
                <span class="tag" :class="syncStatusClassMap[provider.sync_status]">
                  {{ syncStatusLabelMap[provider.sync_status] }}
                </span>
                <span class="tag subtle-tag">已启用 {{ provider.enabled_model_total }}/{{ provider.model_total }}</span>
              </div>
            </div>
            <div v-if="provider.remark || provider.last_sync_at" class="provider-hover-detail">
              <p v-if="provider.remark" class="provider-remark">{{ provider.remark }}</p>
              <p v-if="provider.last_sync_at" class="provider-meta">最近同步：{{ formatDateTime(provider.last_sync_at) }}</p>
            </div>
          </div>

          <div class="provider-actions">
            <button class="action-btn" @click="emit('test', provider.id)" :disabled="testingIds.includes(provider.id)">
              {{ testingIds.includes(provider.id) ? '测试中...' : '连通性' }}
            </button>
            <button class="action-btn" @click="emit('edit', provider.id)">配置</button>
            <button class="action-btn" @click="emit('sync', provider.id)" :disabled="syncingIds.includes(provider.id)">
              {{ syncingIds.includes(provider.id) ? '同步中...' : '同步模型' }}
            </button>
            <button class="icon-btn danger-btn" @click="emit('remove', provider.id)">删除</button>
          </div>
        </div>

        <p v-if="provider.last_sync_error" class="provider-error">{{ provider.last_sync_error }}</p>
        <p v-if="providerTestResults[provider.id]" :class="['provider-test-result', providerTestResults[provider.id].success ? 'success' : 'error']">
          {{ providerTestResults[provider.id].message }}
        </p>

        <div v-if="provider.models.length === 0" class="model-empty">暂无同步模型，请先执行同步</div>

        <template v-else>
          <div class="model-toolbar">
            <div class="type-summary">
              <button
                class="tag summary-tag summary-filter-btn"
                :class="{ active: getSelectedModelType(provider.id) === 'all' }"
                type="button"
                @click="setSelectedModelType(provider.id, 'all')"
              >
                全部 {{ provider.models.length }}
              </button>
              <button
                v-for="group in getModelGroups(provider.models)"
                :key="group.type"
                class="tag summary-tag summary-filter-btn"
                :class="{ active: getSelectedModelType(provider.id) === group.type }"
                type="button"
                @click="setSelectedModelType(provider.id, group.type)"
              >
                {{ group.label }} {{ group.models.length }}
              </button>
            </div>
            <button class="collapse-btn" type="button" @click="toggleProviderExpanded(provider.id)">
              {{ getExpandButtonLabel(provider) }}
            </button>
          </div>

          <div v-if="isProviderExpanded(provider.id)" class="model-groups">
            <section v-for="group in getVisibleModelGroups(provider)" :key="group.type" class="model-group">
              <div class="model-group-header">
                <div class="model-group-title-wrap">
                  <span class="mini-tag type-tag">{{ group.label }}</span>
                  <strong>{{ group.label }} 模型</strong>
                </div>
                <span class="model-group-count">已启用 {{ group.enabledCount }}/{{ group.models.length }}</span>
              </div>

              <div class="model-list">
                <div v-for="model in group.models" :key="model.id" class="model-row">
                  <div class="model-main">
                    <div class="model-name-line">
                      <strong>{{ model.model_name }}</strong>
                      <span v-if="model.is_default" class="mini-tag default-tag">默认</span>
                    </div>
                    <div class="model-tags">
                      <span class="mini-tag type-tag">{{ MODEL_TYPE_LABEL_MAP[model.model_type] }}</span>
                      <span v-for="capability in model.capabilities" :key="capability" class="mini-tag capability-tag">
                        {{ capability }}
                      </span>
                      <span v-if="!model.capabilities.length" class="mini-tag capability-tag muted">{{ model.model_code }}</span>
                    </div>
                  </div>
                  <label class="switch-row">
                    <input
                      :checked="model.is_enabled"
                      type="checkbox"
                      :disabled="togglingModelIds.includes(model.id)"
                      @change="emit('toggle-model', { modelId: model.id, enabled: ($event.target as HTMLInputElement).checked })"
                    />
                  </label>
                </div>
              </div>
            </section>
          </div>
        </template>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

import {
  MODEL_TYPE_LABEL_MAP,
  MODEL_TYPE_ORDER,
  type ModelItem,
  type ModelType,
  type ProviderSummary,
  type SyncStatus,
} from '../../api/model-management'

interface ProviderCardView extends ProviderSummary {
  models: ModelItem[]
}

interface ProviderTestResult {
  success: boolean
  message: string
}

interface ProviderModelGroup {
  type: ModelType
  label: string
  models: ModelItem[]
  enabledCount: number
}

const props = defineProps<{
  providers: ProviderCardView[]
  loading: boolean
  syncingIds: number[]
  testingIds: number[]
  togglingModelIds: number[]
  providerTestResults: Record<number, ProviderTestResult>
}>()

const emit = defineEmits<{
  edit: [providerId: number]
  sync: [providerId: number]
  remove: [providerId: number]
  test: [providerId: number]
  'toggle-model': [payload: { modelId: number; enabled: boolean }]
}>()

const expandedProviderState = ref<Record<number, boolean>>({})
const selectedModelTypeState = ref<Record<number, ModelType | 'all'>>({})

watch(
  () => props.providers,
  (providers) => {
    const nextExpandedState: Record<number, boolean> = {}
    const nextSelectedModelTypeState: Record<number, ModelType | 'all'> = {}

    providers.forEach((provider) => {
      const groups = getModelGroups(provider.models)
      const selectedType = selectedModelTypeState.value[provider.id] ?? 'all'
      const hasSelectedType = selectedType === 'all' || groups.some((group) => group.type === selectedType)

      nextExpandedState[provider.id] = expandedProviderState.value[provider.id] ?? false
      nextSelectedModelTypeState[provider.id] = hasSelectedType ? selectedType : 'all'
    })

    expandedProviderState.value = nextExpandedState
    selectedModelTypeState.value = nextSelectedModelTypeState
  },
  { immediate: true, deep: true },
)

const syncStatusLabelMap: Record<SyncStatus, string> = {
  pending: '待同步',
  success: '已同步',
  failed: '同步失败',
}

const syncStatusClassMap: Record<SyncStatus, string> = {
  pending: 'pending-tag',
  success: 'success-tag',
  failed: 'failed-tag',
}

const modelTypeOrderIndex = MODEL_TYPE_ORDER.reduce<Record<string, number>>((result, type, index) => {
  result[type] = index
  return result
}, {})

const formatDateTime = (value: string) => {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

const getProviderMark = (providerName: string) => {
  return providerName.trim().slice(0, 1).toUpperCase() || 'A'
}

function getModelGroups(models: ModelItem[]): ProviderModelGroup[] {
  const grouped = new Map<ModelType, ModelItem[]>()

  models.forEach((model) => {
    const current = grouped.get(model.model_type) ?? []
    current.push(model)
    grouped.set(model.model_type, current)
  })

  return Array.from(grouped.entries())
    .sort((left, right) => {
      return (modelTypeOrderIndex[left[0]] ?? Number.MAX_SAFE_INTEGER) - (modelTypeOrderIndex[right[0]] ?? Number.MAX_SAFE_INTEGER)
    })
    .map(([type, groupModels]) => ({
      type,
      label: MODEL_TYPE_LABEL_MAP[type] ?? type.toUpperCase(),
      models: groupModels,
      enabledCount: groupModels.filter((item) => item.is_enabled).length,
    }))
}

const getSelectedModelType = (providerId: number) => {
  return selectedModelTypeState.value[providerId] ?? 'all'
}

const setSelectedModelType = (providerId: number, modelType: ModelType | 'all') => {
  selectedModelTypeState.value = {
    ...selectedModelTypeState.value,
    [providerId]: modelType,
  }
}

const getVisibleModelGroups = (provider: ProviderCardView) => {
  const groups = getModelGroups(provider.models)
  const selectedType = getSelectedModelType(provider.id)

  return selectedType === 'all' ? groups : groups.filter((group) => group.type === selectedType)
}

const isProviderExpanded = (providerId: number) => {
  return expandedProviderState.value[providerId] ?? false
}

const toggleProviderExpanded = (providerId: number) => {
  expandedProviderState.value = {
    ...expandedProviderState.value,
    [providerId]: !isProviderExpanded(providerId),
  }
}

const getExpandButtonLabel = (provider: ProviderCardView) => {
  return isProviderExpanded(provider.id) ? '收起模型' : `展开模型（${provider.models.length}）`
}
</script>

<style scoped>
.panel {
  display: grid;
  gap: 16px;
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
  margin: 6px 0 0;
  color: var(--text-tertiary);
  font-size: 0.92rem;
}

.provider-list {
  display: grid;
  gap: 14px;
}

.provider-card {
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--bg-secondary);
  padding: 14px;
}

.provider-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.provider-info {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.provider-mark {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  font-size: var(--model-font-body, 12px);
  font-weight: 700;
  flex-shrink: 0;
}

.provider-body {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.provider-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
}

.provider-title-row h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--model-font-subtitle, 13px);
  line-height: 1.5;
}

.provider-url {
  color: var(--text-tertiary);
  font-size: var(--model-font-meta, 11px);
  line-height: 1.5;
  word-break: break-all;
}

.provider-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.action-btn,
.icon-btn,
.collapse-btn {
  height: 32px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0 12px;
}

.action-btn:disabled,
.collapse-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.collapse-btn {
  background: var(--bg-tertiary);
  color: var(--brand-primary);
  border-color: var(--brand-primary-light);
  white-space: nowrap;
}

.danger-btn {
  color: #ef4444;
}

.provider-hover-detail {
  position: absolute;
  top: calc(100% + 10px);
  left: 0;
  z-index: 12;
  min-width: 260px;
  max-width: min(420px, calc(100vw - 96px));
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-elevated);
  box-shadow: var(--card-shadow-sm);
  backdrop-filter: blur(14px);
  opacity: 0;
  pointer-events: none;
  transform: translateY(6px);
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.provider-name-trigger:hover .provider-hover-detail,
.provider-name-trigger:focus-visible .provider-hover-detail {
  opacity: 1;
  transform: translateY(0);
}

.provider-remark,
.provider-error,
.provider-test-result,
.provider-meta {
  margin: 10px 0 0;
  font-size: 0.88rem;
}

.provider-hover-detail .provider-remark,
.provider-hover-detail .provider-meta {
  margin: 0;
  line-height: 1.6;
}

.provider-hover-detail .provider-meta {
  margin-top: 6px;
}

.provider-remark,
.provider-meta {
  color: var(--text-secondary);
}

.provider-error,
.provider-test-result.error {
  color: #ef4444;
}

.provider-test-result.success {
  color: #16a34a;
}

.tag-group,
.model-tags,
.type-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag,
.mini-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 7px;
  border-radius: 6px;
  font-size: var(--model-font-chip, 10px);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  line-height: 1.4;
}

.summary-tag {
  background: var(--brand-primary-light);
  color: var(--brand-primary);
}

.summary-filter-btn {
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}

.summary-filter-btn.active {
  background: var(--brand-primary);
  color: #ffffff;
}

.summary-filter-btn:hover {
  border-color: var(--brand-primary-light);
}

.pending-tag {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

.success-tag {
  background: rgba(34, 197, 94, 0.1);
  color: #15803d;
}

.failed-tag {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.default-tag {
  background: rgba(139, 92, 246, 0.1);
  color: #6d28d9;
}

.type-tag {
  background: var(--brand-primary-light);
  color: var(--brand-primary);
}

.capability-tag.muted {
  color: var(--text-tertiary);
}

.model-toolbar {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.model-groups {
  margin-top: 12px;
  display: grid;
  gap: 12px;
}

.model-group {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  background: var(--bg-secondary);
}

.model-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
}

.model-group-title-wrap {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.model-group-title-wrap strong {
  color: var(--text-primary);
  font-size: var(--model-font-body, 12px);
  line-height: 1.5;
}

.model-group-count {
  color: var(--text-secondary);
  font-size: var(--model-font-meta, 11px);
  line-height: 1.5;
  flex-shrink: 0;
}

.model-list {
  overflow: hidden;
}

.model-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--bg-secondary);
}

.model-row + .model-row {
  border-top: 1px solid var(--border-color);
}

.model-main {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.model-name-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.model-name-line strong {
  color: var(--text-primary);
  font-size: var(--model-font-body, 12px);
  font-weight: 600;
  line-height: 1.5;
}

.switch-row {
  position: relative;
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}

.switch-row input {
  appearance: none;
  width: 34px;
  height: 20px;
  border-radius: 999px;
  background: var(--border-color);
  cursor: pointer;
  position: relative;
  transition: background 0.2s ease;
}

.switch-row input::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.2);
  transition: transform 0.2s ease;
}

.switch-row input:checked {
  background: var(--brand-primary);
}

.switch-row input:checked::after {
  transform: translateX(14px);
}

.switch-row input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.model-empty,
.panel-placeholder {
  padding: 28px 0;
  text-align: center;
  color: var(--text-tertiary);
}

@media (max-width: 960px) {
  .provider-top,
  .model-toolbar,
  .model-group-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .provider-actions {
    justify-content: flex-start;
  }
}
</style>
