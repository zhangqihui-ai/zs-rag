<template>
  <Layout>
    <div class="page-shell knowledge-view">
      <div v-if="notice" :class="['notice-bar', noticeType]">
        <AppIcon :name="noticeType === 'success' ? 'check' : 'status'" :size="16" />
        <p>{{ notice }}</p>
      </div>

      <Transition name="toast-fade">
        <div v-if="toastVisible" :class="['center-toast', toastType === 'warning' ? 'error' : toastType]">
          <AppIcon :name="toastType === 'success' ? 'check' : 'status'" :size="16" />
          <span>{{ toastMessage }}</span>
        </div>
      </Transition>

      <section class="surface-card toolbar-panel">
        <div>
          <h3>知识库管理</h3>
        </div>
        <div class="toolbar-row">
          <div class="kb-search">
            <AppIcon name="search" :size="15" />
            <input
              v-model.trim="searchTerm"
              class="kb-search-input"
              type="text"
              placeholder="搜索知识库名称 / 描述"
            />
            <button v-if="searchTerm" class="kb-search-clear" type="button" aria-label="清除" @click="searchTerm = ''">
              <AppIcon name="close" :size="14" />
            </button>
          </div>
          <button class="btn btn-secondary" type="button" :disabled="loading" @click="refreshKnowledgeBases">
            <AppIcon name="refresh" :size="16" />
            刷新
          </button>
          <button class="btn btn-primary" type="button" @click="openCreateModal">
            <AppIcon name="plus" :size="16" />
            创建知识库
          </button>
        </div>
      </section>

      <div v-if="loading" class="surface-card loading-skeleton panel-skeleton"></div>

      <div v-else-if="error" class="surface-card error-panel">
        <div>
          <h3>知识库数据加载失败</h3>
          <p>{{ error }}</p>
        </div>
      </div>

      <EmptyState
        v-else-if="knowledgeBases.length === 0"
        title="当前没有可展示的知识库"
        description="请先创建知识库。"
      >
        <template #icon>
          <AppIcon name="folder" :size="20" />
        </template>
        <button class="btn btn-primary" type="button" @click="openCreateModal">
          <AppIcon name="plus" :size="16" />
          创建知识库
        </button>
      </EmptyState>

      <section v-else class="kb-grid-panel">
        <div v-if="filteredKnowledgeBases.length === 0" class="surface-card kb-no-result">
          <AppIcon name="search" :size="18" />
          <p>未找到匹配“{{ searchTerm }}”的知识库</p>
        </div>
        <div v-else class="kb-grid">
          <article
            v-for="kb in pagedKnowledgeBases"
            :key="kb.id"
            class="kb-tile"
            role="button"
            tabindex="0"
            @click="goDetail(kb.id)"
            @keydown.enter.prevent="goDetail(kb.id)"
            @keydown.space.prevent="goDetail(kb.id)"
          >
            <div class="kb-tile-top">
              <div
                :class="[
                  'kb-tile-avatar',
                  kbStorageKind(kb) === 'graph' ? 'kb-tile-avatar--graph' : 'kb-tile-avatar--vector',
                ]"
                :title="kbStorageLabel(kb)"
                :aria-label="kbStorageLabel(kb)"
              >
                <AppIcon
                  :name="kbStorageKind(kb) === 'graph' ? 'graph' : 'vector-db'"
                  :size="kbStorageKind(kb) === 'graph' ? 22 : 20"
                />
              </div>
              <button class="tile-menu-trigger" type="button" @click.stop="toggleMenu(kb.id)">⋯</button>
              <div v-if="openMenuId === kb.id" class="tile-menu" @click.stop>
                <button class="tile-menu-item" type="button" @click="handleEditFromMenu(kb)">修改</button>
                <button class="tile-menu-item danger" type="button" :disabled="purgingId === kb.id" @click="openPurgeModal(kb)">
                  {{ purgingId === kb.id ? '删除中...' : '删除…' }}
                </button>
              </div>
            </div>

            <h4 class="kb-tile-title" :title="displayKbName(kb)">{{ displayKbName(kb) }}</h4>
            <p class="kb-tile-desc">{{ kb.description?.trim() || '该知识库暂无描述。' }}</p>
            <div class="kb-tile-tags">
              <span class="kb-tag kb-tag--embed" :title="embeddingLabelTitleForKb(kb)">
                <AppIcon name="vector-db" :size="12" />
                {{ embeddingShortLabelForKb(kb) }}
              </span>
              <span :class="['kb-tag', kbStorageKind(kb) === 'graph' ? 'kb-tag--graph' : 'kb-tag--vector']">
                <AppIcon :name="kbStorageKind(kb) === 'graph' ? 'graph' : 'database'" :size="12" />
                {{ kbEngineLabel(kb) }}
              </span>
            </div>
            <div class="kb-tile-meta-row">
              <span :class="['status-pill', kbStatusTone(kb.status)]">{{ statusLabelMap[kb.status] || kb.status }}</span>
              <span class="kb-tile-date">{{ formatDate(kb.created_at) }}</span>
            </div>
          </article>
        </div>

        <div v-if="filteredKnowledgeBases.length > 0" class="kb-pagination">
          <span class="kb-pagination-info">共 {{ filteredKnowledgeBases.length }} 个知识库</span>
          <div class="kb-pagination-controls">
            <label class="kb-page-size">
              每页
              <select v-model.number="pageSize" class="select">
                <option :value="12">12</option>
                <option :value="24">24</option>
                <option :value="48">48</option>
              </select>
            </label>
            <button class="btn btn-ghost btn-sm" type="button" :disabled="currentPage <= 1" @click="currentPage -= 1">
              上一页
            </button>
            <span class="kb-pagination-page">{{ currentPage }} / {{ totalPages }}</span>
            <button class="btn btn-ghost btn-sm" type="button" :disabled="currentPage >= totalPages" @click="currentPage += 1">
              下一页
            </button>
          </div>
        </div>
      </section>

      <div v-if="modalOpen" class="modal-overlay" @click.self="closeModal">
        <section class="modal-card kb-modal">
          <header class="kb-modal-header">
            <div>
              <h3>{{ modalMode === 'create' ? '创建知识库' : '修改知识库' }}</h3>
              <p>{{ modalMode === 'create' ? '新建知识库基础信息。' : '更新知识库基础信息。' }}</p>
            </div>
            <button class="icon-button" type="button" @click="closeModal">
              <AppIcon name="close" :size="16" />
            </button>
          </header>

          <form class="form-grid" @submit.prevent="submitModal">
            <label class="field">
              <span class="field-label">知识库名称</span>
              <input v-model.trim="form.name" class="input" type="text" maxlength="200" placeholder="请输入知识库名称" required />
            </label>

            <label class="field">
              <span class="field-label">知识库描述</span>
              <textarea v-model.trim="form.description" class="textarea" maxlength="2000" placeholder="可选，描述用途与范围"></textarea>
            </label>

            <div class="field">
              <span class="field-label">知识库类型</span>
              <div class="kb-type-picker" role="radiogroup" aria-label="知识库类型">
                <button
                  v-for="option in kbTypeOptions"
                  :key="option.value"
                  type="button"
                  class="kb-type-option"
                  :class="[option.tone, { 'is-active': form.kb_type === option.value }]"
                  :disabled="modalMode === 'edit'"
                  :aria-pressed="form.kb_type === option.value"
                  @click="selectKbType(option.value)"
                >
                  <span class="kb-type-option-icon">
                    <AppIcon :name="option.icon" :size="22" />
                  </span>
                  <span class="kb-type-option-body">
                    <strong>{{ option.title }}</strong>
                    <span>{{ option.subtitle }}</span>
                  </span>
                  <span v-if="form.kb_type === option.value" class="kb-type-option-check" aria-hidden="true">
                    <AppIcon name="check" :size="16" />
                  </span>
                </button>
              </div>
              <p v-if="modalMode === 'edit'" class="field-hint">创建后不可更改知识库类型。</p>
            </div>

            <label v-if="modalMode === 'edit'" class="field">
              <span class="field-label">状态</span>
              <select v-model="form.status" class="select">
                <option value="active">运行中</option>
                <option value="inactive">未激活</option>
                <option value="embedding_unavailable">Embedding 不可用</option>
              </select>
              <p v-if="form.status === 'embedding_unavailable'" class="field-hint">
                修复 Embedding 模型或 GPU 资源后，可改回「运行中」以恢复解析与索引。
              </p>
            </label>

            <p v-if="submitting && submitPhase === 'probing'" class="field-hint modal-probing-hint">
              正在检测 Embedding 模型，可能需要 1–2 分钟，请勿重复点击…
            </p>

            <p v-if="modalError" class="modal-error">{{ modalError }}</p>

            <footer class="kb-modal-actions">
              <button class="btn btn-ghost" type="button" @click="closeModal">
                {{ submitting ? '取消请求' : '取消' }}
              </button>
              <button class="btn btn-primary" type="submit" :disabled="submitting || !form.name.trim()">
                {{ submitButtonLabel }}
              </button>
            </footer>
          </form>
        </section>
      </div>

      <div v-if="purgeOpen && purgeTarget" class="modal-overlay" @click.self="closePurgeModal">
        <section class="modal-card kb-modal kb-purge-modal">
          <header class="kb-modal-header">
            <div>
              <h3>删除知识库</h3>
              <p>该操作不可恢复，将清空该知识库下的所有文档和向量化数据。</p>
            </div>
            <button class="icon-button" type="button" @click="closePurgeModal">
              <AppIcon name="close" :size="16" />
            </button>
          </header>

          <div class="kb-purge-body">
            <p class="kb-purge-warn">
              请输入知识库名称 <strong>「{{ purgeTarget.name }}」</strong> 以确认。
            </p>
            <input
              v-model.trim="purgeConfirmName"
              class="input"
              type="text"
              :placeholder="purgeTarget.name"
              autocomplete="off"
            />
            <p v-if="purgeConfirmName && !canSubmitPurge" class="kb-purge-tip">名称不匹配，无法提交。</p>
            <div v-if="purgeError" class="status-box error">{{ purgeError }}</div>
          </div>

          <footer class="kb-modal-actions">
            <button class="btn btn-ghost" type="button" :disabled="purgeSubmitting" @click="closePurgeModal">取消</button>
            <button
              class="btn btn-danger"
              type="button"
              :disabled="purgeSubmitting || !canSubmitPurge"
              @click="submitPurge"
            >
              {{ purgeSubmitting ? '删除中...' : '确认删除' }}
            </button>
          </footer>
        </section>
      </div>
    </div>
  </Layout>
</template>

<script setup lang="ts">
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  getKnowledgeBaseErrorMessage,
  knowledgeBaseApi,
  normalizeKnowledgeBaseList,
  type KnowledgeBase,
  type KnowledgeBasePayload,
} from '../api/knowledge-base'
import { defaultModelApi, modelApi, type DefaultModelOption, type ModelItem } from '../api/model-management'
import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import Layout from '../components/Layout.vue'

const statusLabelMap: Record<string, string> = {
  active: '运行中',
  inactive: '未激活',
  embedding_unavailable: 'Embedding 不可用',
  deleted: '已删除',
}

function kbStatusTone(status: string): string {
  if (status === 'active') {
    return 'success'
  }
  if (status === 'embedding_unavailable') {
    return 'error'
  }
  return 'warning'
}

const router = useRouter()

const knowledgeBases = ref<KnowledgeBase[]>([])
const searchTerm = ref('')
const currentPage = ref(1)
const pageSize = ref(12)

const filteredKnowledgeBases = computed(() => {
  const term = searchTerm.value.trim().toLowerCase()
  if (!term) {
    return knowledgeBases.value
  }
  return knowledgeBases.value.filter((kb) => {
    const name = displayKbName(kb).toLowerCase()
    const desc = (kb.description || '').toLowerCase()
    return name.includes(term) || desc.includes(term)
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredKnowledgeBases.value.length / pageSize.value)))

const pagedKnowledgeBases = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredKnowledgeBases.value.slice(start, start + pageSize.value)
})

watch([searchTerm, pageSize], () => {
  currentPage.value = 1
})

watch([totalPages, currentPage], () => {
  if (currentPage.value > totalPages.value) {
    currentPage.value = totalPages.value
  }
})

const embeddingModels = ref<ModelItem[]>([])
const embeddingDefault = ref<DefaultModelOption | null>(null)
const loading = ref(true)
const error = ref('')

const notice = ref('')
const noticeType = ref<'success' | 'error'>('success')
let noticeTimer: number | undefined

const toastVisible = ref(false)
const toastMessage = ref('')
const toastType = ref<'success' | 'error' | 'warning'>('success')
let toastTimer: number | undefined

const showToast = (text: string, type: 'success' | 'error' | 'warning' = 'success') => {
  toastMessage.value = text
  toastType.value = type
  toastVisible.value = true
  if (toastTimer) {
    window.clearTimeout(toastTimer)
  }
  toastTimer = window.setTimeout(
    () => {
      toastVisible.value = false
    },
    type === 'warning' ? 6000 : 2000,
  )
}

const modalOpen = ref(false)
const modalMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const submitting = ref(false)
const submitPhase = ref<'idle' | 'probing'>('idle')
const createAbortController = ref<AbortController | null>(null)
const modalError = ref('')
const openMenuId = ref<number | null>(null)

const form = reactive({
  name: '',
  description: '',
  kb_type: 'classic' as 'classic' | 'lightrag',
  vector_db_enabled: true,
  graph_db_enabled: false,
  status: 'active' as KnowledgeBase['status'],
})

const needsEmbeddingProbeOnCreate = computed(() => {
  if (modalMode.value !== 'create') {
    return false
  }
  return form.kb_type === 'lightrag' || form.vector_db_enabled
})

const submitButtonLabel = computed(() => {
  if (!submitting.value) {
    return modalMode.value === 'create' ? '创建' : '保存'
  }
  if (modalMode.value === 'create' && submitPhase.value === 'probing') {
    return '正在检测 Embedding 模型…'
  }
  return '提交中…'
})

function embeddingProbeWarningMessage(kb: KnowledgeBase): string {
  const probe = kb.config?.embedding_probe
  if (probe && typeof probe === 'object' && typeof (probe as { message?: unknown }).message === 'string') {
    const message = ((probe as { message: string }).message || '').trim()
    if (message) {
      return `知识库已创建，但 Embedding 模型暂不可用：${message}`
    }
  }
  return '知识库已创建，但 Embedding 模型暂不可用，请在修复模型后将状态改回「运行中」。'
}

const kbTypeOptions = [
  {
    value: 'classic' as const,
    title: '向量知识库',
    subtitle: 'Milvus 向量存储 + 混合检索',
    icon: 'vector-db',
    tone: 'kb-type-option--vector',
  },
  {
    value: 'lightrag' as const,
    title: '图知识库',
    subtitle: 'LightRAG 图谱 + 五模式检索',
    icon: 'graph',
    tone: 'kb-type-option--graph',
  },
]

function selectKbType(value: 'classic' | 'lightrag') {
  if (modalMode.value === 'edit') {
    return
  }
  form.kb_type = value
  if (value === 'classic') {
    form.vector_db_enabled = true
    form.graph_db_enabled = false
  } else {
    form.vector_db_enabled = true
    form.graph_db_enabled = true
  }
}

const createDefaults: Omit<KnowledgeBasePayload, 'name' | 'description' | 'vector_db_enabled' | 'graph_db_enabled'> = {
  embedding_model_id: null,
  default_chunk_size: 1024,
  default_chunk_overlap: 50,
  default_retrieval_mode: 'hybrid',
  default_top_k: 5,
  default_score_threshold: 0.5,
  config: {
    retrieval: {
      vector_weight: 0.3,
      hybrid_strategy: 'weight',
      fusion_method: 'weighted',
      score_threshold_enabled: true,
    },
  },
}

const showNotice = (text: string, type: 'success' | 'error' = 'success') => {
  notice.value = text
  noticeType.value = type
  if (noticeTimer) {
    window.clearTimeout(noticeTimer)
  }
  noticeTimer = window.setTimeout(() => {
    notice.value = ''
  }, 3200)
}

const resetForm = () => {
  form.name = ''
  form.description = ''
  form.kb_type = 'classic'
  form.vector_db_enabled = true
  form.graph_db_enabled = false
  form.status = 'active'
  modalError.value = ''
}

function displayKbName(kb: KnowledgeBase) {
  const name = (kb.name || '').trim()
  return name || '未命名知识库'
}

const refreshKnowledgeBases = async () => {
  loading.value = true
  error.value = ''
  try {
    const [raw] = await Promise.all([knowledgeBaseApi.list(), loadEmbeddingContext()])
    const list = normalizeKnowledgeBaseList(raw)
    if (
      list.length === 0 &&
      raw != null &&
      typeof raw === 'object' &&
      !Array.isArray(raw) &&
      ('data' in (raw as Record<string, unknown>) || 'items' in (raw as Record<string, unknown>))
    ) {
      error.value = '知识库列表数据格式异常，请硬刷新后重试；若仍为空请检查 Network 中 /knowledge-bases 响应。'
      knowledgeBases.value = []
      return
    }
    knowledgeBases.value = list
  } catch (value) {
    error.value = getKnowledgeBaseErrorMessage(value, '加载知识库失败')
  } finally {
    loading.value = false
  }
}

const embeddingModelById = computed(() => {
  const map = new Map<number, ModelItem>()
  for (const item of embeddingModels.value) {
    map.set(item.id, item)
  }
  return map
})

async function loadEmbeddingContext() {
  const [modelsResult, defaultsResult] = await Promise.allSettled([
    modelApi.getModels({ model_type: 'embedding', is_enabled: true, view: 'flat' }),
    defaultModelApi.getDefaults(),
  ])
  if (modelsResult.status === 'fulfilled' && Array.isArray(modelsResult.value)) {
    embeddingModels.value = modelsResult.value as ModelItem[]
  }
  if (defaultsResult.status === 'fulfilled') {
    embeddingDefault.value = defaultsResult.value.embedding ?? null
  }
}

function resolveEmbeddingModel(kb: KnowledgeBase): ModelItem | null {
  if (kb.embedding_model_id != null) {
    return embeddingModelById.value.get(kb.embedding_model_id) ?? null
  }
  const defaultId = embeddingDefault.value?.model_id
  if (defaultId != null) {
    return embeddingModelById.value.get(defaultId) ?? null
  }
  return embeddingModels.value[0] ?? null
}

function embeddingShortLabelForKb(kb: KnowledgeBase): string {
  const model = resolveEmbeddingModel(kb)
  if (model?.model_name) {
    return truncateLabel(model.model_name, 22)
  }
  if (kb.embedding_model_id != null) {
    return `模型 #${kb.embedding_model_id}`
  }
  return '默认 Embedding'
}

function embeddingLabelTitleForKb(kb: KnowledgeBase): string | undefined {
  const model = resolveEmbeddingModel(kb)
  if (model) {
    const suffix = kb.embedding_model_id != null ? '' : '（工作区默认）'
    return `${model.model_name} @ ${model.provider_name}${suffix}`
  }
  if (kb.embedding_model_id != null) {
    return `模型 ID ${kb.embedding_model_id}`
  }
  return '知识库未单独指定向量模型，使用工作区默认 Embedding'
}

function kbEngineLabel(kb: KnowledgeBase): string {
  return kbStorageKind(kb) === 'graph' ? 'LightRAG' : 'Milvus'
}

function truncateLabel(text: string, maxLen: number): string {
  const trimmed = text.trim()
  if (trimmed.length <= maxLen) {
    return trimmed
  }
  return `${trimmed.slice(0, maxLen - 1)}…`
}

const formatDate = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '--'
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}

const goDetail = (kbId: number) => {
  router.push(`/knowledge-bases/${kbId}`)
}

function kbStorageKind(kb: KnowledgeBase): 'vector' | 'graph' {
  if (kb.kb_type === 'lightrag') {
    return 'graph'
  }
  if (kb.kb_type === 'classic') {
    return 'vector'
  }
  return kb.graph_db_enabled && !kb.vector_db_enabled ? 'graph' : 'vector'
}

function kbStorageLabel(kb: KnowledgeBase): string {
  return kbStorageKind(kb) === 'graph' ? '图知识库（LightRAG）' : '向量知识库（Milvus）'
}

const toggleMenu = (kbId: number) => {
  openMenuId.value = openMenuId.value === kbId ? null : kbId
}

const handleEditFromMenu = (kb: KnowledgeBase) => {
  openMenuId.value = null
  openEditModal(kb)
}

const closeMenu = () => {
  openMenuId.value = null
}

const openCreateModal = () => {
  closeMenu()
  modalMode.value = 'create'
  editingId.value = null
  resetForm()
  modalOpen.value = true
}

const openEditModal = (kb: KnowledgeBase) => {
  modalMode.value = 'edit'
  editingId.value = kb.id
  form.name = kb.name
  form.description = kb.description || ''
  form.kb_type = (kb.kb_type === 'lightrag' ? 'lightrag' : 'classic') as 'classic' | 'lightrag'
  form.vector_db_enabled = kb.vector_db_enabled
  form.graph_db_enabled = kb.graph_db_enabled
  form.status =
    kb.status === 'inactive' || kb.status === 'embedding_unavailable' ? kb.status : 'active'
  modalError.value = ''
  modalOpen.value = true
}

const closeModal = () => {
  if (submitting.value) {
    createAbortController.value?.abort()
    createAbortController.value = null
    submitting.value = false
    submitPhase.value = 'idle'
  }
  modalOpen.value = false
  editingId.value = null
  modalError.value = ''
}

const submitModal = async () => {
  if (submitting.value) {
    return
  }
  submitting.value = true
  submitPhase.value = modalMode.value === 'create' && needsEmbeddingProbeOnCreate.value ? 'probing' : 'idle'
  modalError.value = ''
  createAbortController.value = modalMode.value === 'create' ? new AbortController() : null

  const description = form.description.trim() ? form.description.trim() : null
  try {
    if (modalMode.value === 'create') {
      const created = await knowledgeBaseApi.create(
        {
          ...createDefaults,
          name: form.name.trim(),
          description,
          kb_type: form.kb_type,
          vector_db_enabled: form.kb_type === 'classic' ? form.vector_db_enabled : true,
          graph_db_enabled: form.kb_type === 'lightrag' ? true : form.graph_db_enabled,
        },
        { signal: createAbortController.value?.signal },
      )
      modalOpen.value = false
      editingId.value = null
      modalError.value = ''
      await refreshKnowledgeBases()
      if (created.status === 'embedding_unavailable') {
        showToast(embeddingProbeWarningMessage(created), 'warning')
      } else {
        showToast('知识库创建成功', 'success')
      }
    } else if (editingId.value !== null) {
      await knowledgeBaseApi.update(editingId.value, {
        name: form.name.trim(),
        description,
        vector_db_enabled: form.vector_db_enabled,
        graph_db_enabled: form.graph_db_enabled,
        status: form.status,
      })
      modalOpen.value = false
      editingId.value = null
      modalError.value = ''
      await refreshKnowledgeBases()
      showToast('知识库修改成功', 'success')
    }
  } catch (value) {
    if (axios.isCancel(value) || (value instanceof DOMException && value.name === 'AbortError')) {
      modalError.value = '已取消创建请求'
      return
    }
    modalError.value = getKnowledgeBaseErrorMessage(value, modalMode.value === 'create' ? '创建知识库失败' : '修改知识库失败')
  } finally {
    createAbortController.value = null
    submitting.value = false
    submitPhase.value = 'idle'
  }
}

const purgeOpen = ref(false)
const purgeTarget = ref<KnowledgeBase | null>(null)
const purgeConfirmName = ref('')
const purgeError = ref('')
const purgeSubmitting = ref(false)
const purgingId = ref<number | null>(null)

const canSubmitPurge = computed(() => {
  if (!purgeTarget.value) {
    return false
  }
  return purgeConfirmName.value.trim() === purgeTarget.value.name.trim()
})

const openPurgeModal = (kb: KnowledgeBase) => {
  closeMenu()
  purgeTarget.value = kb
  purgeConfirmName.value = ''
  purgeError.value = ''
  purgeSubmitting.value = false
  purgeOpen.value = true
}

const closePurgeModal = () => {
  if (purgeSubmitting.value) {
    return
  }
  purgeOpen.value = false
  purgeTarget.value = null
  purgeConfirmName.value = ''
  purgeError.value = ''
}

const submitPurge = async () => {
  if (!purgeTarget.value) {
    return
  }
  purgeSubmitting.value = true
  purgeError.value = ''
  purgingId.value = purgeTarget.value.id
  try {
    await knowledgeBaseApi.purge(purgeTarget.value.id, { confirm_name: purgeConfirmName.value.trim(), confirm: true })
    purgeOpen.value = false
    purgeTarget.value = null
    purgeConfirmName.value = ''
    purgeError.value = ''
    await refreshKnowledgeBases()
    showToast('知识库已删除', 'success')
  } catch (value) {
    purgeError.value = getKnowledgeBaseErrorMessage(value, '彻底删除失败')
  } finally {
    purgeSubmitting.value = false
    purgingId.value = null
  }
}

onMounted(async () => {
  window.addEventListener('click', closeMenu)
  await refreshKnowledgeBases()
})

onBeforeUnmount(() => {
  window.removeEventListener('click', closeMenu)
  if (noticeTimer) {
    window.clearTimeout(noticeTimer)
  }
  if (toastTimer) {
    window.clearTimeout(toastTimer)
  }
})
</script>

<style scoped>
.knowledge-view {
  gap: 24px;
}

.toolbar-panel,
.error-panel,
.kb-card-header,
.kb-card-actions,
.kb-modal-header,
.kb-modal-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.kb-purge-body {
  display: grid;
  gap: 10px;
  padding: 0 2px;
}

.kb-purge-warn {
  margin: 0;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--warning-soft);
  color: var(--warning-color);
  font-size: 0.9rem;
  line-height: 1.55;
}

.kb-purge-tip {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-tertiary);
}

.toolbar-panel {
  align-items: center;
  padding: 10px 14px;
  min-height: 56px;
}

.toolbar-panel h3 {
  font-size: 1rem;
  line-height: 1.2;
}

.toolbar-panel .btn {
  min-height: 36px;
  padding: 0 12px;
  border-radius: 12px;
}

.toolbar-panel h3,
.error-panel h3,
.kb-card h4,
.kb-tile-title,
.kb-modal-header h3 {
  margin: 0;
  color: var(--text-primary);
}

.toolbar-panel p,
.error-panel p,
.kb-card p,
.kb-modal-header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.65;
}

.panel-skeleton {
  min-height: 360px;
}

.kb-search {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-secondary);
  color: var(--text-tertiary);
  min-width: 220px;
}

.kb-search:focus-within {
  border-color: var(--brand-primary);
}

.kb-search-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  color: var(--text-primary);
  font-size: 0.88rem;
}

.kb-search-clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 2px;
}

.kb-no-result {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  color: var(--text-secondary);
}

.kb-no-result p {
  margin: 0;
}

.kb-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 18px;
  flex-wrap: wrap;
}

.kb-pagination-info {
  color: var(--text-tertiary);
  font-size: 0.85rem;
}

.kb-pagination-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.kb-page-size {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-tertiary);
  font-size: 0.85rem;
}

.kb-page-size .select {
  height: 32px;
  padding: 0 6px;
  border-radius: 8px;
}

.kb-pagination-page {
  color: var(--text-secondary);
  font-size: 0.88rem;
  min-width: 56px;
  text-align: center;
}

.btn-sm {
  min-height: 32px;
  padding: 0 12px;
  border-radius: 10px;
  font-size: 0.85rem;
}

.kb-grid-panel {
  display: grid;
}

.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(268px, 1fr));
  gap: 16px;
}

.kb-tile {
  position: relative;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: var(--bg-tertiary);
  padding: 18px;
  box-shadow: var(--card-shadow-xs);
  display: grid;
  align-content: start;
  gap: 10px;
  min-height: 210px;
  cursor: pointer;
  transition: border-color 0.2s ease, transform 0.2s ease, background 0.2s ease;
}

.kb-tile:hover {
  border-color: var(--brand-primary);
  background: var(--bg-secondary);
  transform: translateY(-1px);
}

.kb-tile:focus-visible {
  box-shadow: 0 0 0 4px var(--brand-primary-light);
}

.kb-tile-top {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kb-tile-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.kb-tile-avatar--vector {
  background: linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%);
  color: #eff6ff;
}

.kb-tile-avatar--graph {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, #b91c1c 0%, #ef4444 100%);
  color: #fef2f2;
}

.kb-tile-tags {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  margin-top: 2px;
}

.kb-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 100%;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 0.76rem;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kb-tag--embed {
  border-color: rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.08);
  color: #2563eb;
}

.kb-tag--vector {
  border-color: rgba(59, 130, 246, 0.28);
  background: rgba(59, 130, 246, 0.06);
  color: #1d4ed8;
}

.kb-tag--graph {
  border-color: rgba(168, 85, 247, 0.35);
  background: rgba(168, 85, 247, 0.1);
  color: #7c3aed;
}

.tile-menu-trigger {
  width: 30px;
  height: 30px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}

.tile-menu {
  position: absolute;
  top: 34px;
  right: 0;
  z-index: 5;
  min-width: 120px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-secondary);
  box-shadow: var(--card-shadow-sm);
  padding: 6px;
  display: grid;
  gap: 4px;
}

.tile-menu-item {
  border: none;
  background: transparent;
  text-align: left;
  padding: 8px 10px;
  border-radius: 8px;
  color: var(--text-primary);
  cursor: pointer;
}

.tile-menu-item:hover:not(:disabled) {
  background: var(--bg-tertiary);
}

.tile-menu-item.danger {
  color: var(--danger-color);
}

.kb-tile-title {
  font-size: 1.06rem;
  font-weight: 600;
  line-height: 1.4;
  word-break: break-word;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.kb-tile-desc {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
  font-size: 0.92rem;
}

.kb-tile-meta-row {
  margin-top: auto;
  padding-top: 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.kb-tile-date {
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.kb-modal {
  width: min(680px, 100%);
  padding: 22px;
  display: grid;
  gap: 18px;
}

.kb-type-picker {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.kb-type-option {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px;
  border: 1.5px solid var(--border-color);
  border-radius: 14px;
  background: var(--bg-tertiary);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}

.kb-type-option:hover:not(:disabled) {
  border-color: var(--brand-primary);
  background: var(--bg-secondary);
}

.kb-type-option.is-active {
  box-shadow: 0 0 0 3px var(--brand-primary-light);
}

.kb-type-option:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.kb-type-option--vector.is-active {
  border-color: rgba(59, 130, 246, 0.55);
  background: rgba(59, 130, 246, 0.06);
}

.kb-type-option--graph.is-active {
  border-color: rgba(239, 68, 68, 0.5);
  background: rgba(239, 68, 68, 0.06);
}

.kb-type-option-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  flex-shrink: 0;
}

.kb-type-option--vector .kb-type-option-icon {
  background: linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%);
  color: #eff6ff;
}

.kb-type-option--graph .kb-type-option-icon {
  background: linear-gradient(135deg, #b91c1c 0%, #ef4444 100%);
  color: #fef2f2;
}

.kb-type-option-body {
  display: grid;
  gap: 4px;
  min-width: 0;
  padding-right: 18px;
}

.kb-type-option-body strong {
  color: var(--text-primary);
  font-size: 0.92rem;
}

.kb-type-option-body span {
  color: var(--text-tertiary);
  font-size: 0.78rem;
  line-height: 1.45;
}

.kb-type-option-check {
  position: absolute;
  top: 12px;
  right: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: var(--brand-primary);
  color: #fff;
}

.kb-type-option--graph.is-active .kb-type-option-check {
  background: #ef4444;
}

.field-hint {
  margin: 8px 0 0;
  color: var(--text-tertiary);
  font-size: 0.82rem;
  line-height: 1.5;
}

@media (max-width: 640px) {
  .kb-type-picker {
    grid-template-columns: 1fr;
  }
}

.modal-error {
  margin: 0;
  color: var(--danger-color);
  font-size: 0.9rem;
}

.kb-modal-actions {
  justify-content: flex-end;
}

.center-toast {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border-radius: 12px;
  font-size: 0.95rem;
  font-weight: 500;
  pointer-events: none;
  white-space: nowrap;
}

.center-toast.success {
  background: rgba(16, 185, 129, 0.92);
  color: #fff;
  box-shadow: 0 4px 20px rgba(16, 185, 129, 0.35);
}

.center-toast.error {
  background: rgba(239, 68, 68, 0.92);
  color: #fff;
  box-shadow: 0 4px 20px rgba(239, 68, 68, 0.35);
}

.toast-fade-enter-active {
  transition: opacity 0.25s ease;
}

.toast-fade-leave-active {
  transition: opacity 0.4s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
}

.modal-probing-hint {
  margin: 0;
  color: var(--text-secondary, #64748b);
}

@media (max-width: 900px) {
  .toolbar-panel,
  .error-panel,
  .kb-card-header,
  .kb-card-actions,
  .kb-modal-header,
  .kb-modal-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
