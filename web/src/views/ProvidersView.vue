<template>
  <Layout>
    <div class="page-shell model-page">
      <div v-if="notice.text" :class="['notice-bar', notice.type]">
        <AppIcon :name="notice.type === 'success' ? 'check' : 'status'" :size="16" />
        <p>{{ notice.text }}</p>
      </div>

      <div v-if="pageError" class="surface-card page-error">
        <div>
          <h3>模型管理页加载失败</h3>
          <p>{{ pageError }}</p>
        </div>
        <button class="btn btn-secondary" type="button" @click="loadPageData">
          <AppIcon name="refresh" :size="16" />
          重试
        </button>
      </div>

      <div v-else class="workspace-shell">
        <div class="main-column">
          <DefaultModelsPanel
            :defaults="defaults"
            :enabled-options-map="enabledOptionsMap"
            :loading="loading"
            :saving="defaultsSaving"
            @save="handleSaveDefaults"
          />

          <ProvidersPanel
            :providers="providerCards"
            :loading="loading"
            :syncing-ids="syncingIds"
            :testing-ids="testingIds"
            :toggling-model-ids="togglingModelIds"
            :provider-test-results="providerTestResults"
            @edit="openEditModal"
            @sync="handleSyncProvider"
            @remove="handleDeleteProvider"
            @test="handleTestProvider"
            @toggle-model="handleToggleModel"
          />
        </div>

        <aside class="sidebar-column">
          <ProviderTemplatesPanel
            :templates="filteredTemplates"
            :keyword="templateKeyword"
            :active-type="activeTemplateType"
            @create="openCreateModal"
            @update:keyword="templateKeyword = $event"
            @update:active-type="activeTemplateType = $event"
          />
        </aside>
      </div>

      <ProviderConfigModal
        :open="modalOpen"
        :mode="modalMode"
        :template="activeTemplate"
        :initial-value="editingProviderDetail"
        :submitting="modalSubmitting"
        :error="modalError"
        @close="closeModal"
        @submit="handleSubmitProvider"
      />
    </div>
  </Layout>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'

import {
  defaultModelApi,
  getErrorMessage,
  modelApi,
  providerApi,
  type DefaultsData,
  type ModelItem,
  type ModelType,
  type ProviderCreatePayload,
  type ProviderDetail,
  type ProviderModelsGroup,
  type ProviderSummary,
  type ProviderTemplate,
  type ProviderTestResult,
} from '../api/model-management'
import AppIcon from '../components/AppIcon.vue'
import Layout from '../components/Layout.vue'
import { useSpaceReadyLoader } from '../composables/useSpaceReady'
import DefaultModelsPanel from '../components/model-management/DefaultModelsPanel.vue'
import ProviderConfigModal from '../components/model-management/ProviderConfigModal.vue'
import ProvidersPanel from '../components/model-management/ProvidersPanel.vue'
import ProviderTemplatesPanel from '../components/model-management/ProviderTemplatesPanel.vue'

const createEmptyDefaults = (): DefaultsData => ({
  llm: null,
  embedding: null,
  rerank: null,
  tts: null,
  asr: null,
  vlm: null,
  moderation: null,
  ocr: null,
})

const loading = ref(true)
const pageError = ref('')
const defaultsSaving = ref(false)
const templates = ref<ProviderTemplate[]>([])
const providers = ref<ProviderSummary[]>([])
const groupedModels = ref<ProviderModelsGroup[]>([])
const enabledModels = ref<ModelItem[]>([])
const defaults = ref<DefaultsData>(createEmptyDefaults())
const templateKeyword = ref('')
const activeTemplateType = ref<ModelType | 'all'>('all')
const syncingIds = ref<number[]>([])
const testingIds = ref<number[]>([])
const togglingModelIds = ref<number[]>([])
const providerTestResults = ref<Record<number, ProviderTestResult>>({})

const notice = reactive<{ type: 'success' | 'error'; text: string }>({
  type: 'success',
  text: '',
})

const modalOpen = ref(false)
const modalMode = ref<'create' | 'edit'>('create')
const activeTemplate = ref<ProviderTemplate | null>(null)
const editingProviderId = ref<number | null>(null)
const editingProviderDetail = ref<ProviderDetail | null>(null)
const modalSubmitting = ref(false)
const modalError = ref('')

let noticeTimer: number | undefined

const showNotice = (text: string, type: 'success' | 'error' = 'success') => {
  notice.type = type
  notice.text = text
  if (noticeTimer) {
    window.clearTimeout(noticeTimer)
  }
  noticeTimer = window.setTimeout(() => {
    notice.text = ''
  }, 3200)
}

const enabledOptionsMap = computed(() => {
  const result = {
    llm: [],
    embedding: [],
    rerank: [],
    tts: [],
    asr: [],
    vlm: [],
    moderation: [],
    ocr: [],
  } as Record<ModelType, Array<{ label: string; value: number; providerName: string }>>

  enabledModels.value
    .slice()
    .sort((a, b) => {
      const providerDiff = a.provider_name.localeCompare(b.provider_name, 'zh-CN')
      if (providerDiff !== 0) {
        return providerDiff
      }
      return a.model_name.localeCompare(b.model_name, 'zh-CN')
    })
    .forEach((model) => {
      result[model.model_type].push({
        label: model.model_name,
        value: model.id,
        providerName: model.provider_name,
      })
    })

  return result
})

const providerCards = computed(() => {
  const groupedMap = new Map(groupedModels.value.map((item) => [item.provider_id, item]))
  return providers.value.map((provider) => ({
    ...provider,
    models: groupedMap.get(provider.id)?.models || [],
  }))
})

const filteredTemplates = computed(() => {
  const keyword = templateKeyword.value.trim().toLowerCase()
  return templates.value.filter((template) => {
    const matchesType = activeTemplateType.value === 'all' || template.supported_types.includes(activeTemplateType.value)
    const matchesKeyword = !keyword || template.provider_name.toLowerCase().includes(keyword) || template.provider_code.toLowerCase().includes(keyword)
    return matchesType && matchesKeyword
  })
})

const buildFallbackTemplate = (detail: ProviderDetail): ProviderTemplate => ({
  provider_code: detail.provider_code,
  provider_name: detail.provider_name,
  deployment_type: detail.deployment_type,
  default_base_url: detail.base_url,
  supported_types: detail.supported_types,
  auth_type: detail.auth_type,
  auth_fields: detail.auth_fields,
})

const loadPageData = async () => {
  loading.value = true
  pageError.value = ''
  try {
    const [templateList, providerList, groupedList, enabledList, defaultsData] = await Promise.all([
      providerApi.getProviderTemplates(),
      providerApi.getProviders(),
      modelApi.getModels({ view: 'grouped' }) as Promise<ProviderModelsGroup[]>,
      modelApi.getModels({ view: 'flat', is_enabled: true }) as Promise<ModelItem[]>,
      defaultModelApi.getDefaults(),
    ])

    templates.value = templateList
    providers.value = providerList
    groupedModels.value = groupedList
    enabledModels.value = enabledList
    defaults.value = { ...createEmptyDefaults(), ...defaultsData }
  } catch (error) {
    pageError.value = getErrorMessage(error, '加载模型管理页面失败')
  } finally {
    loading.value = false
  }
}

const refreshModelData = async () => {
  const [providerList, groupedList, enabledList, defaultsData] = await Promise.all([
    providerApi.getProviders(),
    modelApi.getModels({ view: 'grouped' }) as Promise<ProviderModelsGroup[]>,
    modelApi.getModels({ view: 'flat', is_enabled: true }) as Promise<ModelItem[]>,
    defaultModelApi.getDefaults(),
  ])

  providers.value = providerList
  groupedModels.value = groupedList
  enabledModels.value = enabledList
  defaults.value = { ...createEmptyDefaults(), ...defaultsData }
}

const closeModal = () => {
  modalOpen.value = false
  modalError.value = ''
  editingProviderId.value = null
  editingProviderDetail.value = null
  activeTemplate.value = null
}

const openCreateModal = (template: ProviderTemplate) => {
  modalMode.value = 'create'
  activeTemplate.value = template
  editingProviderDetail.value = null
  editingProviderId.value = null
  modalError.value = ''
  modalOpen.value = true
}

const openEditModal = async (providerId: number) => {
  modalMode.value = 'edit'
  modalError.value = ''
  modalSubmitting.value = false
  try {
    const detail = await providerApi.getProviderDetail(providerId)
    editingProviderId.value = providerId
    editingProviderDetail.value = detail
    activeTemplate.value = templates.value.find((item) => item.provider_code === detail.provider_code) || buildFallbackTemplate(detail)
    modalOpen.value = true
  } catch (error) {
    showNotice(getErrorMessage(error, '加载厂商详情失败'), 'error')
  }
}

const handleSubmitProvider = async (payload: ProviderCreatePayload) => {
  modalSubmitting.value = true
  modalError.value = ''
  try {
    if (modalMode.value === 'create') {
      const result = await providerApi.createProvider(payload)
      showNotice(`接入成功，已同步 ${result.model_count} 个模型`, 'success')
    } else if (editingProviderId.value !== null) {
      await providerApi.updateProvider(editingProviderId.value, payload)
      showNotice('厂商配置已更新', 'success')
    }
    closeModal()
    await refreshModelData()
  } catch (error) {
    modalError.value = getErrorMessage(error, modalMode.value === 'create' ? '接入厂商失败' : '更新厂商失败')
  } finally {
    modalSubmitting.value = false
  }
}

const handleSaveDefaults = async (payload: Record<ModelType, number | null>) => {
  defaultsSaving.value = true
  try {
    await defaultModelApi.saveDefaults(payload)
    await refreshModelData()
    showNotice('默认模型已保存', 'success')
  } catch (error) {
    showNotice(getErrorMessage(error, '保存默认模型失败'), 'error')
  } finally {
    defaultsSaving.value = false
  }
}

const handleSyncProvider = async (providerId: number) => {
  syncingIds.value = [...syncingIds.value, providerId]
  try {
    const result = await providerApi.syncProviderModels(providerId)
    await refreshModelData()
    showNotice(`同步完成：新增 ${result.added}，更新 ${result.updated}，禁用 ${result.disabled}`, 'success')
  } catch (error) {
    showNotice(getErrorMessage(error, '同步模型失败'), 'error')
  } finally {
    syncingIds.value = syncingIds.value.filter((item) => item !== providerId)
  }
}

const handleTestProvider = async (providerId: number) => {
  testingIds.value = [...testingIds.value, providerId]
  try {
    const result = await providerApi.testProvider(providerId)
    providerTestResults.value = {
      ...providerTestResults.value,
      [providerId]: result,
    }
    showNotice(result.message, result.success ? 'success' : 'error')
  } catch (error) {
    const message = getErrorMessage(error, '连通性测试失败')
    providerTestResults.value = {
      ...providerTestResults.value,
      [providerId]: { success: false, message },
    }
    showNotice(message, 'error')
  } finally {
    testingIds.value = testingIds.value.filter((item) => item !== providerId)
  }
}

const handleDeleteProvider = async (providerId: number) => {
  if (!window.confirm('确认删除该厂商配置及其模型吗？')) {
    return
  }

  try {
    await providerApi.deleteProvider(providerId)
    await refreshModelData()
    showNotice('厂商已删除', 'success')
  } catch (error) {
    showNotice(getErrorMessage(error, '删除厂商失败'), 'error')
  }
}

const handleToggleModel = async ({ modelId, enabled }: { modelId: number; enabled: boolean }) => {
  togglingModelIds.value = [...togglingModelIds.value, modelId]
  try {
    await modelApi.toggleModelEnabled(modelId, { is_enabled: enabled })
    await refreshModelData()
    showNotice(enabled ? '模型已启用' : '模型已禁用', 'success')
  } catch (error) {
    showNotice(getErrorMessage(error, enabled ? '启用模型失败' : '禁用模型失败'), 'error')
  } finally {
    togglingModelIds.value = togglingModelIds.value.filter((item) => item !== modelId)
  }
}

useSpaceReadyLoader(loadPageData)
onBeforeUnmount(() => {
  if (noticeTimer) {
    window.clearTimeout(noticeTimer)
  }
})
</script>

<style scoped>
.model-page {
  --model-font-title: 15px;
  --model-font-subtitle: 14px;
  --model-font-body: 13px;
  --model-font-meta: 12px;
  --model-font-chip: 11px;

  gap: 24px;
  font-size: var(--model-font-body);
}

.page-error {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
}

.page-error h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--model-font-title);
  line-height: 1.5;
}

.page-error p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: var(--model-font-body);
  line-height: 1.6;
}

.workspace-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.78fr);
  align-items: start;
  gap: 24px;
}

.main-column,
.sidebar-column {
  display: grid;
  gap: 20px;
}

.sidebar-column {
  position: sticky;
  top: calc(var(--header-height) + 32px);
}

@media (max-width: 1280px) {
  .workspace-shell {
    grid-template-columns: 1fr;
  }

  .sidebar-column {
    position: static;
  }
}

@media (max-width: 960px) {
  .page-error {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
