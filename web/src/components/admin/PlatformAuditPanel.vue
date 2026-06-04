<template>
  <div class="platform-audit-panel">
    <section class="surface-card toolbar-panel">
      <div class="audit-filters">
        <label v-if="authStore.isSystemAdmin" class="audit-filter-field">
          <span class="audit-filter-label">企业空间</span>
          <select v-model="spaceFilter" class="select audit-filter-control">
            <option value="">全部空间</option>
            <option v-for="space in allSpaces" :key="space.id" :value="String(space.id)">
              {{ space.name }}
            </option>
          </select>
        </label>
        <label class="audit-filter-field">
          <span class="audit-filter-label">操作用户</span>
          <select v-model="userFilter" class="select audit-filter-control">
            <option value="">全部用户</option>
            <option v-for="user in spaceMembers" :key="user.id" :value="String(user.id)">
              {{ user.username }}
            </option>
          </select>
        </label>
        <label class="audit-filter-field">
          <span class="audit-filter-label">操作类型</span>
          <select v-model="actionFilter" class="select audit-filter-control">
            <option value="">全部操作</option>
            <option v-for="(label, value) in PLATFORM_AUDIT_ACTION_LABELS" :key="value" :value="value">
              {{ label }}
            </option>
          </select>
        </label>
        <label class="audit-filter-field">
          <span class="audit-filter-label">资源类型</span>
          <select v-model="resourceTypeFilter" class="select audit-filter-control">
            <option value="">全部资源</option>
            <option v-for="(label, value) in PLATFORM_AUDIT_RESOURCE_TYPE_LABELS" :key="value" :value="value">
              {{ label }}
            </option>
          </select>
        </label>
        <label class="audit-date-field">
          <span class="audit-date-label">开始日期</span>
          <input v-model="dateFrom" type="date" class="input" />
        </label>
        <label class="audit-date-field">
          <span class="audit-date-label">结束日期</span>
          <input v-model="dateTo" type="date" class="input" />
        </label>
        <div class="audit-filter-actions">
          <button class="btn btn-secondary" type="button" :disabled="loading" @click="resetFilters">
            重置
          </button>
          <button class="btn btn-primary" type="button" :disabled="loading" @click="search">
            <AppIcon name="search" :size="16" />
            查询
          </button>
        </div>
      </div>
    </section>

    <div v-if="loading" class="surface-card loading-skeleton panel-skeleton"></div>

    <div v-else-if="error" class="surface-card error-panel">
      <h3>加载失败</h3>
      <p>{{ error }}</p>
    </div>

    <EmptyState v-else-if="events.length === 0" title="暂无操作记录" description="调整筛选条件或稍后再试。">
      <template #icon>
        <AppIcon name="shield" :size="20" />
      </template>
    </EmptyState>

    <section v-else class="surface-card table-panel">
      <table class="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th v-if="authStore.isSystemAdmin && !selectedSpaceId">企业空间</th>
            <th>操作用户</th>
            <th>操作</th>
            <th>资源</th>
            <th>说明</th>
            <th>IP</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="event in events" :key="event.id">
            <tr>
              <td class="audit-time">{{ formatTime(event.created_at) }}</td>
              <td v-if="authStore.isSystemAdmin && !selectedSpaceId">{{ event.space_name || '—' }}</td>
              <td>{{ event.username || '—' }}</td>
              <td>
                <span class="chip">{{ formatAuditAction(event.action) }}</span>
              </td>
              <td>
                <span class="audit-resource">
                  {{ formatAuditResourceType(event.resource_type) }}
                  <span v-if="event.resource_id" class="text-muted">#{{ event.resource_id }}</span>
                </span>
              </td>
              <td class="audit-message">{{ event.message || '—' }}</td>
              <td class="text-muted">{{ event.ip_address || '—' }}</td>
              <td class="table-actions">
                <button
                  v-if="event.detail && Object.keys(event.detail).length > 0"
                  class="btn btn-secondary btn-sm"
                  type="button"
                  @click="toggleDetail(event.id)"
                >
                  {{ expandedId === event.id ? '收起' : '详情' }}
                </button>
              </td>
            </tr>
            <tr v-if="expandedId === event.id && event.detail" class="audit-detail-row">
              <td :colspan="detailColspan">
                <pre class="audit-detail-json">{{ formatDetail(event.detail) }}</pre>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <div v-if="total > 0" class="audit-pagination">
        <span class="audit-pagination-meta">共 {{ total }} 条</span>
        <label class="audit-pagination-size">
          <span>每页</span>
          <select v-model.number="pageSize" class="select" @change="goPage(1)">
            <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}</option>
          </select>
        </label>
        <div class="audit-pagination-nav">
          <button class="btn btn-secondary btn-sm" type="button" :disabled="page <= 1" @click="goPage(page - 1)">
            上一页
          </button>
          <span class="audit-pagination-page">{{ page }} / {{ totalPages }}</span>
          <button
            class="btn btn-secondary btn-sm"
            type="button"
            :disabled="page >= totalPages"
            @click="goPage(page + 1)"
          >
            下一页
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { listAllEnterpriseSpaces } from '../../api/enterprise-space'
import {
  formatAuditAction,
  formatAuditResourceType,
  listPlatformAuditEvents,
  PLATFORM_AUDIT_ACTION_LABELS,
  PLATFORM_AUDIT_RESOURCE_TYPE_LABELS,
  type PlatformAuditEvent,
} from '../../api/platform-audit'
import { listUsers, type UserDetail } from '../../api/users'
import { getApiErrorMessage } from '../../lib/apiError'
import { formatApiDateTime } from '../../lib/formatDateTime'
import AppIcon from '../AppIcon.vue'
import EmptyState from '../EmptyState.vue'
import type { EnterpriseSpace } from '../../stores/auth'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{
  initialUserId?: number | null
}>()

const authStore = useAuthStore()

function todayDateString() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const events = ref<PlatformAuditEvent[]>([])
const total = ref(0)
const loading = ref(true)
const error = ref('')
const page = ref(1)
const pageSize = ref(20)
const pageSizeOptions = [20, 50, 100]

const allSpaces = ref<EnterpriseSpace[]>([])
const spaceMembers = ref<UserDetail[]>([])

const spaceFilter = ref('')
const userFilter = ref('')
const actionFilter = ref('')
const resourceTypeFilter = ref('')
const dateFrom = ref(todayDateString())
const dateTo = ref(todayDateString())
const expandedId = ref<number | null>(null)

const selectedSpaceId = computed(() => {
  if (!authStore.isSystemAdmin) return authStore.currentSpace?.id ?? null
  if (!spaceFilter.value) return null
  const parsed = Number(spaceFilter.value)
  return Number.isFinite(parsed) ? parsed : null
})

const detailColspan = computed(() => {
  let cols = 7
  if (authStore.isSystemAdmin && !selectedSpaceId.value) cols += 1
  return cols
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

function formatTime(value: string) {
  return formatApiDateTime(value, value)
}

function formatDetail(detail: Record<string, unknown>) {
  return JSON.stringify(detail, null, 2)
}

function toggleDetail(id: number) {
  expandedId.value = expandedId.value === id ? null : id
}

function toIsoStart(date: string) {
  if (!date) return undefined
  return new Date(`${date}T00:00:00`).toISOString()
}

function toIsoEnd(date: string) {
  if (!date) return undefined
  return new Date(`${date}T23:59:59.999`).toISOString()
}

async function loadMembers() {
  try {
    const { data } = await listUsers()
    spaceMembers.value = data
  } catch {
    spaceMembers.value = []
  }
}

async function loadSpaces() {
  if (!authStore.isSystemAdmin) return
  try {
    const { data } = await listAllEnterpriseSpaces()
    allSpaces.value = data
  } catch {
    allSpaces.value = []
  }
}

async function fetchEvents() {
  loading.value = true
  error.value = ''
  expandedId.value = null
  try {
    const params: Record<string, string | number> = {
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    }
    if (selectedSpaceId.value != null) params.enterprise_space_id = selectedSpaceId.value
    if (userFilter.value) params.user_id = Number(userFilter.value)
    if (actionFilter.value) params.action = actionFilter.value
    if (resourceTypeFilter.value) params.resource_type = resourceTypeFilter.value
    const from = toIsoStart(dateFrom.value)
    const to = toIsoEnd(dateTo.value)
    if (from) params.created_from = from
    if (to) params.created_to = to

    const { data } = await listPlatformAuditEvents(params)
    events.value = data.items ?? []
    total.value = data.total ?? 0
  } catch (err) {
    error.value = getApiErrorMessage(err, '加载操作记录失败')
    events.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void fetchEvents()
}

function goPage(nextPage: number) {
  page.value = Math.min(Math.max(1, nextPage), totalPages.value)
  void fetchEvents()
}

function resetFilters() {
  spaceFilter.value = ''
  userFilter.value = ''
  actionFilter.value = ''
  resourceTypeFilter.value = ''
  dateFrom.value = todayDateString()
  dateTo.value = todayDateString()
  page.value = 1
  void fetchEvents()
}

watch(
  () => props.initialUserId,
  (userId, prev) => {
    if (userId == null || userId === prev) return
    userFilter.value = String(userId)
    page.value = 1
    void fetchEvents()
  },
)

watch(spaceFilter, async () => {
  if (props.initialUserId != null) return
  userFilter.value = ''
  await loadMembers()
})

onMounted(async () => {
  await Promise.all([loadSpaces(), loadMembers()])
  if (props.initialUserId != null) {
    userFilter.value = String(props.initialUserId)
  }
  await fetchEvents()
})

defineExpose({ search })
</script>

<style scoped>
.platform-audit-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar-panel {
  padding: 16px;
}

.audit-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: flex-end;
}

.audit-filter-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 160px;
}

.audit-filter-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
}

.audit-filter-control {
  min-width: 160px;
  min-height: 40px;
  padding-right: 32px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
}

.audit-date-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 150px;
}

.audit-date-label {
  font-size: 0.82rem;
  color: var(--text-tertiary);
}

.audit-filter-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
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
  white-space: nowrap;
}

.audit-time {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.audit-message {
  max-width: 280px;
  word-break: break-word;
}

.audit-resource {
  white-space: nowrap;
}

.text-muted {
  color: var(--text-tertiary);
}

.chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-tertiary);
  font-size: 0.82rem;
}

.table-actions {
  white-space: nowrap;
}

.audit-detail-row td {
  background: var(--bg-tertiary);
}

.audit-detail-json {
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: var(--bg-secondary);
  font-size: 0.82rem;
  overflow-x: auto;
}

.audit-pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
  padding: 16px;
  border-top: 1px solid var(--border-color);
}

.audit-pagination-meta {
  color: var(--text-secondary);
  font-size: 0.88rem;
}

.audit-pagination-size {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 0.88rem;
}

.audit-pagination-nav {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

.audit-pagination-page {
  min-width: 72px;
  text-align: center;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.error-panel {
  padding: 24px;
}

.error-panel h3 {
  margin: 0 0 8px;
}

.error-panel p {
  margin: 0;
  color: var(--text-secondary);
}

.panel-skeleton {
  min-height: 240px;
}
</style>
