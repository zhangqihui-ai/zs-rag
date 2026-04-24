<template>
  <Layout>
    <div class="page-shell knowledge-view">
      <div v-if="notice" :class="['notice-bar', noticeType]">
        <AppIcon :name="noticeType === 'success' ? 'check' : 'status'" :size="16" />
        <p>{{ notice }}</p>
      </div>

      <Transition name="toast-fade">
        <div v-if="toastVisible" :class="['center-toast', toastType]">
          <AppIcon :name="toastType === 'success' ? 'check' : 'status'" :size="16" />
          <span>{{ toastMessage }}</span>
        </div>
      </Transition>

      <section class="surface-card toolbar-panel">
        <div>
          <h3>知识库管理</h3>
        </div>
        <div class="toolbar-row">
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
        <div class="kb-grid">
          <article
            v-for="kb in knowledgeBases"
            :key="kb.id"
            class="kb-tile"
            role="button"
            tabindex="0"
            @click="goDetail(kb.id)"
            @keydown.enter.prevent="goDetail(kb.id)"
            @keydown.space.prevent="goDetail(kb.id)"
          >
            <div class="kb-tile-top">
              <div class="kb-tile-avatar">{{ kb.name.slice(0, 1).toUpperCase() }}</div>
              <button class="tile-menu-trigger" type="button" @click.stop="toggleMenu(kb.id)">⋯</button>
              <div v-if="openMenuId === kb.id" class="tile-menu" @click.stop>
                <button class="tile-menu-item" type="button" @click="handleEditFromMenu(kb)">修改</button>
                <button class="tile-menu-item danger" type="button" :disabled="purgingId === kb.id" @click="openPurgeModal(kb)">
                  {{ purgingId === kb.id ? '删除中...' : '删除…' }}
                </button>
              </div>
            </div>

            <h4>{{ kb.name }}</h4>
            <p class="kb-tile-desc">{{ kb.description || '该知识库暂无描述。' }}</p>
            <div class="kb-tile-meta-row">
              <span :class="['status-pill', kb.status === 'active' ? 'success' : 'warning']">{{ statusLabelMap[kb.status] || kb.status }}</span>
              <span class="kb-tile-date">{{ formatDate(kb.created_at) }}</span>
            </div>
          </article>
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

            <div class="form-grid two">
              <label class="field inline-field">
                <span class="field-label">启用向量数据库</span>
                <label class="switch">
                  <input v-model="form.vector_db_enabled" type="checkbox" />
                </label>
              </label>

              <label class="field inline-field">
                <span class="field-label">启用图数据库</span>
                <label class="switch">
                  <input v-model="form.graph_db_enabled" type="checkbox" />
                </label>
              </label>
            </div>

            <label v-if="modalMode === 'edit'" class="field">
              <span class="field-label">状态</span>
              <select v-model="form.status" class="select">
                <option value="active">运行中</option>
                <option value="inactive">未激活</option>
              </select>
            </label>

            <p v-if="modalError" class="modal-error">{{ modalError }}</p>

            <footer class="kb-modal-actions">
              <button class="btn btn-ghost" type="button" :disabled="submitting" @click="closeModal">取消</button>
              <button class="btn btn-primary" type="submit" :disabled="submitting || !form.name">
                {{ submitting ? '提交中...' : modalMode === 'create' ? '创建' : '保存' }}
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
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getKnowledgeBaseErrorMessage, knowledgeBaseApi, type KnowledgeBase, type KnowledgeBasePayload } from '../api/knowledge-base'
import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import Layout from '../components/Layout.vue'

const statusLabelMap: Record<string, string> = {
  active: '运行中',
  inactive: '未激活',
  deleted: '已删除',
}

const router = useRouter()

const knowledgeBases = ref<KnowledgeBase[]>([])
const loading = ref(true)
const error = ref('')

const notice = ref('')
const noticeType = ref<'success' | 'error'>('success')
let noticeTimer: number | undefined

const toastVisible = ref(false)
const toastMessage = ref('')
const toastType = ref<'success' | 'error'>('success')
let toastTimer: number | undefined

const showToast = (text: string, type: 'success' | 'error' = 'success') => {
  toastMessage.value = text
  toastType.value = type
  toastVisible.value = true
  if (toastTimer) {
    window.clearTimeout(toastTimer)
  }
  toastTimer = window.setTimeout(() => {
    toastVisible.value = false
  }, 2000)
}

const modalOpen = ref(false)
const modalMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const submitting = ref(false)
const modalError = ref('')
const openMenuId = ref<number | null>(null)

const form = reactive({
  name: '',
  description: '',
  vector_db_enabled: true,
  graph_db_enabled: false,
  status: 'active' as 'active' | 'inactive',
})

const createDefaults: Omit<KnowledgeBasePayload, 'name' | 'description' | 'vector_db_enabled' | 'graph_db_enabled'> = {
  embedding_model_id: null,
  default_chunk_size: 1024,
  default_chunk_overlap: 50,
  default_retrieval_mode: 'hybrid',
  default_top_k: 5,
  default_score_threshold: null,
  config: null,
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
  form.vector_db_enabled = true
  form.graph_db_enabled = false
  form.status = 'active'
  modalError.value = ''
}

const refreshKnowledgeBases = async () => {
  loading.value = true
  error.value = ''
  try {
    knowledgeBases.value = await knowledgeBaseApi.list()
  } catch (value) {
    error.value = getKnowledgeBaseErrorMessage(value, '加载知识库失败')
  } finally {
    loading.value = false
  }
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
  form.vector_db_enabled = kb.vector_db_enabled
  form.graph_db_enabled = kb.graph_db_enabled
  form.status = kb.status === 'inactive' ? 'inactive' : 'active'
  modalError.value = ''
  modalOpen.value = true
}

const closeModal = () => {
  if (submitting.value) {
    return
  }
  modalOpen.value = false
  editingId.value = null
  modalError.value = ''
}

const submitModal = async () => {
  submitting.value = true
  modalError.value = ''

  const description = form.description.trim() ? form.description.trim() : null
  try {
    if (modalMode.value === 'create') {
      await knowledgeBaseApi.create({
        ...createDefaults,
        name: form.name.trim(),
        description,
        vector_db_enabled: form.vector_db_enabled,
        graph_db_enabled: form.graph_db_enabled,
      })
      modalOpen.value = false
      editingId.value = null
      modalError.value = ''
      await refreshKnowledgeBases()
      showToast('知识库创建成功', 'success')
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
    modalError.value = getKnowledgeBaseErrorMessage(value, modalMode.value === 'create' ? '创建知识库失败' : '修改知识库失败')
  } finally {
    submitting.value = false
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

.kb-grid-panel {
  display: grid;
}

.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.kb-tile {
  position: relative;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: var(--bg-tertiary);
  padding: 16px;
  box-shadow: var(--card-shadow-xs);
  display: grid;
  align-content: start;
  gap: 12px;
  min-height: 176px;
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
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #ea580c 0%, #f97316 100%);
  color: #fff;
  font-weight: 700;
  font-size: 1rem;
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

.kb-tile h4 {
  margin: 0;
}

.kb-tile-desc {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
  font-size: 0.92rem;
}

.kb-tile-meta-row {
  margin-top: auto;
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

.inline-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
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
