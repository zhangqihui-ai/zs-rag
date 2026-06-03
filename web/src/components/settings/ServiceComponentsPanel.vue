<template>
  <section class="surface-card service-components-panel">
    <div class="section-heading panel-header">
      <div>
        <h3>服务组件状态</h3>
        <p>查看平台依赖的中间件运行状态；快速访问需使用当前浏览器所在主机 IP，内网部署时请确认端口已在 compose 中映射。</p>
      </div>
      <button class="btn btn-secondary" type="button" :disabled="loading" @click="loadStatus">
        <AppIcon name="status" :size="16" />
        {{ loading ? '检测中...' : '刷新' }}
      </button>
    </div>

    <div v-if="error" class="error-panel">
      <p>{{ error }}</p>
    </div>

    <div v-else-if="loading && items.length === 0" class="loading-skeleton panel-skeleton"></div>

    <div v-else class="table-panel">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>名称</th>
            <th>服务类型</th>
            <th>Host</th>
            <th>宿主机端口</th>
            <th>容器端口</th>
            <th>状态</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in items" :key="item.id">
            <td>{{ index }}</td>
            <td class="name-cell">
              <strong>{{ item.name }}</strong>
              <div
                v-for="line in accessLines(item)"
                :key="`${item.id}-${line.label}`"
                class="name-access"
              >
                <span class="access-label">{{ line.label }}</span>
                <a
                  v-if="line.href"
                  class="access-link"
                  :href="line.href"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {{ line.text }}
                </a>
                <button
                  v-else
                  class="access-link access-copy"
                  type="button"
                  @click="copyText(line.text)"
                >
                  {{ line.text }}
                </button>
              </div>
            </td>
            <td>
              <span class="chip">{{ serviceTypeLabel(item.service_type) }}</span>
            </td>
            <td>
              <span class="endpoint-badge">{{ item.host }}</span>
            </td>
            <td>
              <span v-if="hostPort(item) !== null" class="endpoint-badge">{{ hostPort(item) }}</span>
              <span v-else class="host-port-unexposed">未暴露</span>
            </td>
            <td>
              <span class="endpoint-badge">{{ item.port }}</span>
            </td>
            <td>
              <span :class="['status-pill', statusClass(item.status)]">
                <span class="status-dot"></span>
                {{ statusLabel(item.status) }}
              </span>
            </td>
            <td class="table-actions">
              <div class="action-group">
                <a
                  v-if="visitUrl(item)"
                  class="btn btn-secondary btn-sm visit-link"
                  :href="visitUrl(item)!"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <AppIcon name="arrow-up-right" :size="14" />
                  {{ item.visit_label || '访问' }}
                </a>
                <button
                  v-else-if="externalEndpoint(item)"
                  class="btn btn-secondary btn-sm endpoint-copy"
                  type="button"
                  :title="`复制连接地址：${externalEndpoint(item)}`"
                  @click="copyEndpoint(item)"
                >
                  <AppIcon name="copy" :size="14" />
                  {{ externalEndpoint(item) }}
                </button>
                <button
                  v-if="hasCredentials(item)"
                  class="btn btn-secondary btn-sm icon-only-btn"
                  type="button"
                  title="查看账号密码"
                  @click="openCredentials(item)"
                >
                  <AppIcon name="key" :size="14" />
                </button>
                <span v-if="!visitUrl(item) && !externalEndpoint(item) && !hasCredentials(item)" class="action-placeholder">—</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="checkedAt && !loading" class="checked-at">最近检测：{{ formatCheckedAt(checkedAt) }}</p>

    <div v-if="credentialModalItem" class="modal-overlay" @click.self="closeCredentials">
      <div class="modal-card credentials-modal">
        <div class="modal-header">
          <h3>{{ credentialModalItem.name }} 访问凭据</h3>
          <button class="icon-only-btn modal-close" type="button" aria-label="关闭" @click="closeCredentials">
            <AppIcon name="close" :size="16" />
          </button>
        </div>
        <p class="modal-hint">以下信息来自当前部署配置，仅供运维人员使用。</p>
        <div class="credential-list">
          <div
            v-for="credential in credentialModalItem.credentials"
            :key="`${credentialModalItem.id}-${credential.label}`"
            class="credential-row"
          >
            <span class="credential-label">{{ credential.label }}</span>
            <code class="credential-value">{{ credential.value }}</code>
            <button
              class="btn btn-secondary btn-sm"
              type="button"
              @click.stop="copyText(credential.value)"
            >
              <AppIcon name="copy" :size="14" />
              复制
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import AppIcon from '../AppIcon.vue'
import { copyToClipboard } from '../../lib/copy-to-clipboard'
import {
  buildComponentAccessLines,
  buildComponentExternalEndpoint,
  buildComponentHostPort,
  buildComponentVisitUrl,
  fetchServiceComponentsStatus,
  type ComponentAccessLine,
  type ComponentStatus,
  type ServiceComponentItem,
} from '../../api/system'

const items = ref<ServiceComponentItem[]>([])
const checkedAt = ref<string | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const credentialModalItem = ref<ServiceComponentItem | null>(null)

const serviceTypeLabels: Record<string, string> = {
  app_server: '应用服务',
  web_ui: '前端',
  meta_data: '元数据',
  file_store: '文件存储',
  retrieval: '检索',
  graph: '图数据库',
  parser: '解析器',
  coordination: '协调服务',
  queue: '消息队列',
  task_worker: '任务队列',
}

function serviceTypeLabel(type: string): string {
  return serviceTypeLabels[type] || type
}

function statusLabel(status: ComponentStatus): string {
  const labels: Record<ComponentStatus, string> = {
    alive: 'Alive',
    dead: 'Dead',
    disabled: 'Disabled',
    unknown: 'Unknown',
  }
  return labels[status]
}

function statusClass(status: ComponentStatus): string {
  return `is-${status}`
}

function accessLines(item: ServiceComponentItem): ComponentAccessLine[] {
  return buildComponentAccessLines(item)
}

function visitUrl(item: ServiceComponentItem): string | null {
  return buildComponentVisitUrl(item)
}

function externalEndpoint(item: ServiceComponentItem): string | null {
  return buildComponentExternalEndpoint(item)
}

function hostPort(item: ServiceComponentItem): number | null {
  return buildComponentHostPort(item)
}

function hasCredentials(item: ServiceComponentItem): boolean {
  return Boolean(item.credentials?.length)
}

function openCredentials(item: ServiceComponentItem) {
  credentialModalItem.value = item
}

function closeCredentials() {
  credentialModalItem.value = null
}

async function copyText(text: string) {
  if (!text) {
    return
  }
  const ok = await copyToClipboard(text)
  if (!ok) {
    window.alert('复制失败，请手动选择文本')
  }
}

async function copyEndpoint(item: ServiceComponentItem) {
  const endpoint = externalEndpoint(item)
  if (!endpoint) {
    return
  }
  await copyText(endpoint)
}

function formatCheckedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString()
}

async function loadStatus() {
  loading.value = true
  error.value = null
  try {
    const response = await fetchServiceComponentsStatus()
    items.value = response.items
    checkedAt.value = response.checked_at
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载服务组件状态失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadStatus()
})

defineExpose({ loadStatus })
</script>

<style scoped>
.service-components-panel {
  grid-column: 1 / -1;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.table-panel {
  overflow-x: auto;
  margin-top: 18px;
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
  vertical-align: middle;
}

.data-table th {
  color: var(--text-tertiary);
  font-size: 0.82rem;
  font-weight: 600;
}

.name-cell strong {
  display: block;
  color: var(--text-primary);
}

.name-access {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.access-label {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  font-size: 0.72rem;
  font-weight: 600;
}

.access-link {
  color: var(--brand-primary);
  font-size: 0.78rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  text-decoration: none;
  word-break: break-all;
}

.access-link:hover {
  text-decoration: underline;
}

.access-copy {
  border: 0;
  padding: 0;
  background: transparent;
  cursor: pointer;
}

.endpoint-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.host-port-unexposed {
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  font-weight: 600;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.status-pill.is-alive {
  color: #22c55e;
}

.status-pill.is-dead {
  color: #ef4444;
}

.status-pill.is-disabled {
  color: var(--text-tertiary);
}

.status-pill.is-unknown {
  color: #f59e0b;
}

.table-actions {
  min-width: 120px;
}

.action-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.icon-only-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  padding: 0;
}

.visit-link,
.endpoint-copy {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-decoration: none;
  max-width: 180px;
}

.endpoint-copy {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.78rem;
}

.action-placeholder {
  color: var(--text-tertiary);
}

.error-panel {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(239, 68, 68, 0.25);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.panel-skeleton {
  min-height: 280px;
  margin-top: 18px;
}

.checked-at {
  margin: 14px 0 0;
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.45);
}

.credentials-modal {
  width: min(520px, 100%);
  padding: 22px;
  border-radius: 18px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.18);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.05rem;
}

.modal-close {
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.modal-hint {
  margin: 10px 0 16px;
  color: var(--text-secondary);
  font-size: 0.86rem;
  line-height: 1.6;
}

.credential-list {
  display: grid;
  gap: 12px;
}

.credential-row {
  display: grid;
  grid-template-columns: 88px 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-tertiary);
}

.credential-label {
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: 600;
}

.credential-value {
  color: var(--text-primary);
  font-size: 0.82rem;
  word-break: break-all;
}

@media (max-width: 720px) {
  .panel-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
