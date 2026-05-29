<template>
  <Layout>
    <div class="page-shell admin-users-view">
      <PageHeader
        eyebrow="Identity Management"
        title="用户管理"
      >
        <template #actions>
          <button v-if="activeTab === 'users'" class="btn btn-primary" type="button" @click="openCreateModal">
            <AppIcon name="plus" :size="16" />
            创建用户
          </button>
        </template>
      </PageHeader>

      <div v-if="canManageUsers && canManageSpaces" class="admin-tabs" role="tablist" aria-label="管理模块">
        <button
          type="button"
          role="tab"
          :class="['admin-tab', { active: activeTab === 'users' }]"
          @click="activeTab = 'users'"
        >
          用户
        </button>
        <button
          type="button"
          role="tab"
          :class="['admin-tab', { active: activeTab === 'spaces' }]"
          @click="activeTab = 'spaces'"
        >
          企业空间
        </button>
      </div>

      <EnterpriseSpacesPanel v-if="activeTab === 'spaces'" />

      <template v-else>
      <section class="surface-card toolbar-panel">
        <div class="search-row">
          <input v-model="searchQuery" type="search" placeholder="搜索用户名或邮箱..." @keyup.enter="loadUsers" />
          <button class="btn btn-secondary" type="button" @click="loadUsers">
            <AppIcon name="search" :size="16" />
            搜索
          </button>
        </div>
      </section>

      <div v-if="loading" class="surface-card loading-skeleton panel-skeleton"></div>

      <div v-else-if="error" class="surface-card error-panel">
        <h3>加载失败</h3>
        <p>{{ error }}</p>
      </div>

      <EmptyState v-else-if="users.length === 0" title="暂无用户" description="点击上方按钮创建第一个用户。">
        <template #icon>
          <AppIcon name="user" :size="20" />
        </template>
      </EmptyState>

      <section v-else class="surface-card table-panel">
        <table class="data-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>邮箱</th>
              <th>状态</th>
              <th>平台角色</th>
              <th>所属空间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td><strong>{{ user.username }}</strong></td>
              <td>{{ user.email || '—' }}</td>
              <td>
                <span :class="['status-badge', user.is_active ? 'active' : 'inactive']">
                  {{ user.is_active ? '启用' : '禁用' }}
                </span>
              </td>
              <td>{{ user.is_admin ? '系统管理员' : '普通用户' }}</td>
              <td>
                <span v-if="user.memberships.length === 0" class="text-muted">未分配</span>
                <span v-else class="space-tags">
                  <span v-for="m in user.memberships" :key="m.enterprise_space_id" class="chip">
                    {{ m.space.name }} ({{ roleLabel(m.role) }})
                  </span>
                </span>
              </td>
              <td class="table-actions">
                <button class="btn btn-secondary btn-sm" type="button" @click="openEditModal(user)">编辑</button>
                <button
                  class="btn btn-secondary btn-sm"
                  type="button"
                  :disabled="user.is_bootstrap_admin"
                  @click="confirmDelete(user)"
                >
                  删除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 创建/编辑 Modal -->
      <div v-if="userModalVisible" class="modal-overlay" @click.self="closeUserModal">
        <div class="modal-card modal-card-wide">
          <h3>{{ editingUser ? '编辑用户' : '创建用户' }}</h3>
          <form class="modal-form" @submit.prevent="submitUserForm">
            <div class="form-grid">
              <label>
                用户名
                <input v-model="userForm.username" type="text" required maxlength="100" />
              </label>
              <label>
                邮箱（选填）
                <input v-model="userForm.email" type="email" placeholder="可不填写" />
              </label>
              <label>
                {{ editingUser ? '新密码（留空不修改）' : '密码' }}
                <input v-model="userForm.password" type="password" :required="!editingUser" minlength="8" />
              </label>
              <label v-if="editingUser">
                状态
                <select v-model="userForm.is_active">
                  <option :value="true">启用</option>
                  <option :value="false">禁用</option>
                </select>
              </label>
            </div>

            <label v-if="authStore.isBootstrapAdmin" class="checkbox-row">
              <input v-model="userForm.is_admin" type="checkbox" />
              系统管理员
            </label>

            <div v-if="authStore.isSystemAdmin && allSpaces.length > 0" class="assignments-section">
              <h4>企业空间分配</h4>
              <p class="hint">可为同一用户分配多个企业空间。</p>
              <div v-for="(item, index) in userForm.assignments" :key="index" class="assignment-row">
                <select v-model="item.enterprise_space_id">
                  <option v-for="space in allSpaces" :key="space.id" :value="space.id">{{ space.name }}</option>
                </select>
                <select v-model="item.role">
                  <option value="member">普通成员</option>
                  <option value="space_admin">空间管理员</option>
                </select>
                <button class="btn btn-secondary btn-sm" type="button" @click="removeAssignment(index)">移除</button>
              </div>
              <button class="btn btn-secondary btn-sm" type="button" @click="addAssignment">添加空间</button>
            </div>

            <p v-if="formError" class="form-error">{{ formError }}</p>
            <div class="modal-actions">
              <button class="btn btn-secondary" type="button" @click="closeUserModal">取消</button>
              <button class="btn btn-primary" type="submit" :disabled="submitting">
                {{ submitting ? '保存中...' : '保存' }}
              </button>
            </div>
          </form>
        </div>
      </div>
      </template>
    </div>
  </Layout>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { listAllEnterpriseSpaces } from '../api/enterprise-space'
import {
  createUser,
  deleteUser,
  listUsers,
  setUserMemberships,
  updateUser,
  type UserDetail,
} from '../api/users'
import EnterpriseSpacesPanel from '../components/admin/EnterpriseSpacesPanel.vue'
import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import Layout from '../components/Layout.vue'
import PageHeader from '../components/PageHeader.vue'
import type { EnterpriseSpace, MembershipRole } from '../stores/auth'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()

const canManageUsers = computed(() => authStore.canManageUsers)
const canManageSpaces = computed(() => authStore.canManageSpaces)
const activeTab = ref<'users' | 'spaces'>(authStore.canManageUsers ? 'users' : 'spaces')

const users = ref<UserDetail[]>([])
const allSpaces = ref<EnterpriseSpace[]>([])
const loading = ref(true)
const error = ref('')
const searchQuery = ref('')

const userModalVisible = ref(false)
const editingUser = ref<UserDetail | null>(null)
const userForm = reactive({
  username: '',
  email: '',
  password: '',
  is_active: true,
  is_admin: false,
  assignments: [] as Array<{ enterprise_space_id: number; role: MembershipRole }>,
})
const formError = ref('')
const submitting = ref(false)

const roleLabel = (role: MembershipRole) => (role === 'space_admin' ? '空间管理员' : '成员')

const loadUsers = async () => {
  loading.value = true
  error.value = ''
  try {
    const { data } = await listUsers(searchQuery.value.trim() || undefined)
    users.value = data
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载用户失败'
  } finally {
    loading.value = false
  }
}

const loadSpaces = async () => {
  if (!authStore.isSystemAdmin) return
  try {
    const { data } = await listAllEnterpriseSpaces()
    allSpaces.value = data
  } catch {
    allSpaces.value = []
  }
}

const resetForm = () => {
  userForm.username = ''
  userForm.email = ''
  userForm.password = ''
  userForm.is_active = true
  userForm.is_admin = false
  userForm.assignments = []
  formError.value = ''
}

const openCreateModal = () => {
  editingUser.value = null
  resetForm()
  if (authStore.isSystemAdmin && allSpaces.value.length > 0) {
    userForm.assignments = [{ enterprise_space_id: allSpaces.value[0].id, role: 'member' }]
  }
  userModalVisible.value = true
}

const openEditModal = (user: UserDetail) => {
  editingUser.value = user
  userForm.username = user.username
  userForm.email = user.email || ''
  userForm.password = ''
  userForm.is_active = user.is_active
  userForm.is_admin = user.is_admin
  userForm.assignments = user.memberships.map((m) => ({
    enterprise_space_id: m.enterprise_space_id,
    role: m.role,
  }))
  formError.value = ''
  userModalVisible.value = true
}

const closeUserModal = () => {
  userModalVisible.value = false
}

const addAssignment = () => {
  if (allSpaces.value.length === 0) return
  userForm.assignments.push({ enterprise_space_id: allSpaces.value[0].id, role: 'member' })
}

const removeAssignment = (index: number) => {
  userForm.assignments.splice(index, 1)
}

const submitUserForm = async () => {
  submitting.value = true
  formError.value = ''
  try {
    if (editingUser.value) {
      const payload: Record<string, unknown> = {
        username: userForm.username,
        email: userForm.email.trim() || null,
        is_active: userForm.is_active,
      }
      if (userForm.password) payload.password = userForm.password
      if (authStore.isBootstrapAdmin) payload.is_admin = userForm.is_admin
      await updateUser(editingUser.value.id, payload as Parameters<typeof updateUser>[1])
      if (authStore.isSystemAdmin) {
        await setUserMemberships(editingUser.value.id, userForm.assignments)
      }
    } else {
      await createUser({
        username: userForm.username,
        email: userForm.email.trim() || undefined,
        password: userForm.password,
        ...(authStore.isBootstrapAdmin && userForm.is_admin ? { is_admin: true } : {}),
        ...(authStore.isSystemAdmin && userForm.assignments.length > 0
          ? { space_assignments: userForm.assignments }
          : {}),
      })
    }
    closeUserModal()
    await loadUsers()
  } catch (err) {
    formError.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    submitting.value = false
  }
}

const confirmDelete = async (user: UserDetail) => {
  if (!window.confirm(`确定删除用户「${user.username}」？`)) return
  try {
    await deleteUser(user.id)
    await loadUsers()
  } catch (err) {
    window.alert(err instanceof Error ? err.message : '删除失败')
  }
}

onMounted(async () => {
  await Promise.all([loadUsers(), loadSpaces()])
})
</script>

<style scoped>
.admin-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  margin-bottom: 16px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.admin-tab {
  padding: 8px 18px;
  border: none;
  border-radius: 9px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}

.admin-tab:hover {
  color: var(--text-primary);
}

.admin-tab.active {
  background: var(--bg-secondary);
  color: var(--brand-primary);
  box-shadow: var(--card-shadow-xs);
}

.toolbar-panel {
  margin-bottom: 16px;
}

.search-row {
  display: flex;
  gap: 12px;
}

.search-row input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.table-panel {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
  vertical-align: top;
}

.data-table th {
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.table-actions {
  display: flex;
  gap: 8px;
}

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.8rem;
}

.status-badge.active {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.status-badge.inactive {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
}

.space-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--bg-tertiary);
  font-size: 0.82rem;
}

.text-muted {
  color: var(--text-tertiary);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.45);
}

.modal-card {
  width: 100%;
  max-width: 520px;
  padding: 28px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.modal-card-wide {
  max-width: 640px;
  max-height: 85vh;
  overflow-y: auto;
}

.modal-form {
  display: grid;
  gap: 16px;
  margin-top: 20px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.modal-form label {
  display: grid;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.modal-form input,
.modal-form select {
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.checkbox-row {
  display: flex !important;
  align-items: center;
  gap: 8px;
  flex-direction: row !important;
}

.assignments-section {
  padding: 16px;
  border-radius: 12px;
  background: var(--bg-tertiary);
}

.assignments-section h4 {
  margin: 0 0 4px;
}

.hint {
  margin: 0 0 12px;
  color: var(--text-tertiary);
  font-size: 0.85rem;
}

.assignment-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.assignment-row select {
  flex: 1;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.form-error {
  color: #f87171;
  margin: 0;
}

.btn-sm {
  padding: 6px 12px;
  font-size: 0.85rem;
}

.panel-skeleton {
  min-height: 120px;
}

@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
