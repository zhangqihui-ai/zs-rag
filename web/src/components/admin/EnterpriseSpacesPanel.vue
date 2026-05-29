<template>
  <div class="spaces-panel">
    <div class="spaces-panel-toolbar">
      <p class="spaces-panel-hint">管理企业空间（租户）及其成员与角色。</p>
      <button class="btn btn-primary" type="button" @click="openCreateModal">
        <AppIcon name="plus" :size="16" />
        创建企业空间
      </button>
    </div>

    <div v-if="loading" class="surface-card loading-skeleton panel-skeleton"></div>

    <div v-else-if="error" class="surface-card error-panel">
      <h3>加载失败</h3>
      <p>{{ error }}</p>
    </div>

    <EmptyState v-else-if="spaces.length === 0" title="暂无企业空间" description="点击上方按钮创建第一个企业空间。">
      <template #icon>
        <AppIcon name="workspace" :size="20" />
      </template>
    </EmptyState>

    <section v-else class="surface-card table-panel">
      <table class="data-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>标识 (slug)</th>
            <th>描述</th>
            <th>成员数</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="space in spaces" :key="space.id">
            <td><strong>{{ space.name }}</strong></td>
            <td><code>{{ space.slug }}</code></td>
            <td>{{ space.description || '—' }}</td>
            <td>{{ memberCounts[space.id] ?? '—' }}</td>
            <td class="table-actions">
              <button class="btn btn-secondary btn-sm" type="button" @click="openMembersDrawer(space)">成员</button>
              <button class="btn btn-secondary btn-sm" type="button" @click="openEditModal(space)">编辑</button>
              <button
                class="btn btn-secondary btn-sm"
                type="button"
                :disabled="space.slug === 'default'"
                @click="confirmDelete(space)"
              >
                删除
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- 创建/编辑 Modal -->
    <div v-if="spaceModalVisible" class="modal-overlay" @click.self="closeSpaceModal">
      <div class="modal-card">
        <h3>{{ editingSpace ? '编辑企业空间' : '创建企业空间' }}</h3>
        <form class="modal-form" @submit.prevent="submitSpaceForm">
          <label>
            名称
            <input v-model="spaceForm.name" type="text" required maxlength="100" />
          </label>
          <label v-if="!editingSpace">
            标识 (slug)
            <input v-model="spaceForm.slug" type="text" required maxlength="100" pattern="[a-z0-9-]+" />
          </label>
          <label>
            描述
            <textarea v-model="spaceForm.description" rows="3" maxlength="500"></textarea>
          </label>
          <p v-if="formError" class="form-error">{{ formError }}</p>
          <div class="modal-actions">
            <button class="btn btn-secondary" type="button" @click="closeSpaceModal">取消</button>
            <button class="btn btn-primary" type="submit" :disabled="submitting">
              {{ submitting ? '保存中...' : '保存' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- 成员 Drawer -->
    <div v-if="membersDrawerVisible" class="modal-overlay" @click.self="closeMembersDrawer">
      <div class="modal-card modal-card-wide">
        <div class="drawer-header">
          <div>
            <h3>{{ selectedSpace?.name }} · 成员管理</h3>
            <p>管理该空间下的用户成员与角色。</p>
          </div>
          <button class="btn btn-secondary btn-sm" type="button" @click="closeMembersDrawer">关闭</button>
        </div>

        <div class="member-add-row">
          <select v-model="addMemberUserId" class="member-select">
            <option :value="null">选择用户添加...</option>
            <option v-for="user in availableUsersForAdd" :key="user.id" :value="user.id">
              {{ user.username }}{{ user.email ? ` (${user.email})` : '' }}
            </option>
          </select>
          <select v-model="addMemberRole" class="member-select">
            <option value="member">普通成员</option>
            <option value="space_admin">空间管理员</option>
          </select>
          <button class="btn btn-primary btn-sm" type="button" :disabled="!addMemberUserId" @click="handleAddMember">
            添加成员
          </button>
        </div>

        <div v-if="membersLoading" class="loading-skeleton panel-skeleton"></div>
        <table v-else class="data-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>邮箱</th>
              <th>角色</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="member in members" :key="member.id">
              <td>{{ member.user.username }}</td>
              <td>{{ member.user.email || '—' }}</td>
              <td>
                <select
                  :value="member.role"
                  class="role-select"
                  @change="handleRoleChange(member, ($event.target as HTMLSelectElement).value as MembershipRole)"
                >
                  <option value="member">普通成员</option>
                  <option value="space_admin">空间管理员</option>
                </select>
              </td>
              <td>
                <button class="btn btn-secondary btn-sm" type="button" @click="handleRemoveMember(member)">移除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import {
  addSpaceMember,
  createEnterpriseSpace,
  deleteEnterpriseSpace,
  getSpaceMemberCount,
  listAllEnterpriseSpaces,
  listSpaceMembers,
  removeSpaceMember,
  updateEnterpriseSpace,
  updateSpaceMember,
  type MembershipWithUser,
} from '../../api/enterprise-space'
import { listUsers, type UserDetail } from '../../api/users'
import type { EnterpriseSpace, MembershipRole } from '../../stores/auth'
import AppIcon from '../AppIcon.vue'
import EmptyState from '../EmptyState.vue'

const spaces = ref<EnterpriseSpace[]>([])
const memberCounts = ref<Record<number, number>>({})
const loading = ref(true)
const error = ref('')

const spaceModalVisible = ref(false)
const editingSpace = ref<EnterpriseSpace | null>(null)
const spaceForm = reactive({ name: '', slug: '', description: '' })
const formError = ref('')
const submitting = ref(false)

const membersDrawerVisible = ref(false)
const selectedSpace = ref<EnterpriseSpace | null>(null)
const members = ref<MembershipWithUser[]>([])
const membersLoading = ref(false)
const allUsers = ref<UserDetail[]>([])
const addMemberUserId = ref<number | null>(null)
const addMemberRole = ref<MembershipRole>('member')

const availableUsersForAdd = ref<UserDetail[]>([])

const loadSpaces = async () => {
  loading.value = true
  error.value = ''
  try {
    const { data } = await listAllEnterpriseSpaces()
    spaces.value = data
    const counts: Record<number, number> = {}
    await Promise.all(
      data.map(async (space) => {
        const resp = await getSpaceMemberCount(space.id)
        counts[space.id] = resp.data.count
      }),
    )
    memberCounts.value = counts
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载企业空间失败'
  } finally {
    loading.value = false
  }
}

const openCreateModal = () => {
  editingSpace.value = null
  spaceForm.name = ''
  spaceForm.slug = ''
  spaceForm.description = ''
  formError.value = ''
  spaceModalVisible.value = true
}

const openEditModal = (space: EnterpriseSpace) => {
  editingSpace.value = space
  spaceForm.name = space.name
  spaceForm.slug = space.slug
  spaceForm.description = space.description || ''
  formError.value = ''
  spaceModalVisible.value = true
}

const closeSpaceModal = () => {
  spaceModalVisible.value = false
}

const submitSpaceForm = async () => {
  submitting.value = true
  formError.value = ''
  try {
    if (editingSpace.value) {
      await updateEnterpriseSpace(editingSpace.value.id, {
        name: spaceForm.name,
        description: spaceForm.description || undefined,
      })
    } else {
      await createEnterpriseSpace({
        name: spaceForm.name,
        slug: spaceForm.slug,
        description: spaceForm.description || undefined,
      })
    }
    closeSpaceModal()
    await loadSpaces()
  } catch (err) {
    formError.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    submitting.value = false
  }
}

const confirmDelete = async (space: EnterpriseSpace) => {
  if (!window.confirm(`确定删除企业空间「${space.name}」？此操作不可恢复。`)) return
  try {
    await deleteEnterpriseSpace(space.id)
    await loadSpaces()
  } catch (err) {
    window.alert(err instanceof Error ? err.message : '删除失败')
  }
}

const openMembersDrawer = async (space: EnterpriseSpace) => {
  selectedSpace.value = space
  membersDrawerVisible.value = true
  membersLoading.value = true
  addMemberUserId.value = null
  addMemberRole.value = 'member'
  try {
    const [membersResp, usersResp] = await Promise.all([
      listSpaceMembers(space.id, space.slug),
      listUsers(),
    ])
    members.value = membersResp.data
    allUsers.value = usersResp.data
    const memberIds = new Set(members.value.map((m) => m.user_id))
    availableUsersForAdd.value = allUsers.value.filter((u) => !memberIds.has(u.id))
  } catch (err) {
    window.alert(err instanceof Error ? err.message : '加载成员失败')
  } finally {
    membersLoading.value = false
  }
}

const closeMembersDrawer = () => {
  membersDrawerVisible.value = false
  selectedSpace.value = null
}

const handleAddMember = async () => {
  if (!selectedSpace.value || !addMemberUserId.value) return
  try {
    await addSpaceMember(selectedSpace.value.id, addMemberUserId.value, addMemberRole.value, selectedSpace.value.slug)
    await openMembersDrawer(selectedSpace.value)
    await loadSpaces()
  } catch (err) {
    window.alert(err instanceof Error ? err.message : '添加成员失败')
  }
}

const handleRoleChange = async (member: MembershipWithUser, role: MembershipRole) => {
  if (!selectedSpace.value) return
  try {
    await updateSpaceMember(selectedSpace.value.id, member.user_id, role, selectedSpace.value.slug)
    member.role = role
  } catch (err) {
    window.alert(err instanceof Error ? err.message : '更新角色失败')
    await openMembersDrawer(selectedSpace.value)
  }
}

const handleRemoveMember = async (member: MembershipWithUser) => {
  if (!selectedSpace.value) return
  if (!window.confirm(`确定将 ${member.user.username} 移出该空间？`)) return
  try {
    await removeSpaceMember(selectedSpace.value.id, member.user_id, selectedSpace.value.slug)
    await openMembersDrawer(selectedSpace.value)
    await loadSpaces()
  } catch (err) {
    window.alert(err instanceof Error ? err.message : '移除成员失败')
  }
}

onMounted(loadSpaces)
</script>

<style scoped>
.spaces-panel {
  display: grid;
  gap: 16px;
}

.spaces-panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.spaces-panel-hint {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 0.9rem;
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
}

.data-table th {
  color: var(--text-tertiary);
  font-size: 0.82rem;
  font-weight: 600;
}

.table-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-sm {
  padding: 6px 12px;
  font-size: 0.85rem;
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
  max-width: 480px;
  padding: 28px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  box-shadow: var(--card-shadow);
}

.modal-card-wide {
  max-width: 720px;
  max-height: 85vh;
  overflow-y: auto;
}

.modal-form {
  display: grid;
  gap: 16px;
  margin-top: 20px;
}

.modal-form label {
  display: grid;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.modal-form input,
.modal-form textarea,
.member-select,
.role-select {
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

.form-error {
  color: #f87171;
  margin: 0;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.drawer-header p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.member-add-row {
  display: flex;
  gap: 10px;
  margin: 20px 0;
  flex-wrap: wrap;
}

.member-select {
  flex: 1;
  min-width: 160px;
}

.panel-skeleton {
  min-height: 120px;
}
</style>
