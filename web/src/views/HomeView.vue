<template>
  <Layout>
    <div class="page-shell home-view">
      <section v-if="loading" class="home-kpi-grid">
        <article v-for="n in 5" :key="n" class="home-kpi-card home-kpi-card--skeleton"></article>
      </section>

      <section v-else-if="error" class="surface-card error-panel">
        <div>
          <h3>仪表盘加载失败</h3>
          <p>{{ error }}</p>
        </div>
        <button class="btn btn-secondary" type="button" @click="fetchDashboard">重试</button>
      </section>

      <template v-else-if="overview">
        <section class="home-kpi-grid">
          <article v-for="metric in topMetrics" :key="metric.label" class="home-kpi-card">
            <span :class="['home-kpi-icon', metric.tone]">
              <AppIcon :name="metric.icon" :size="22" />
            </span>
            <div class="home-kpi-body">
              <p class="home-kpi-value">{{ metric.value }}</p>
              <p class="home-kpi-label">{{ metric.label }}</p>
              <p class="home-kpi-sub">较昨日 —</p>
            </div>
          </article>
        </section>

        <UsageStatsSection />

        <KnowledgeUsagePanel :knowledge="overview.knowledge" :usage="overview.knowledge_usage" />

        <div class="home-extras-grid">
          <section class="surface-card home-extra-card">
            <header class="home-extra-head">
              <span class="home-extra-icon tone-green">
                <AppIcon name="shield" :size="18" />
              </span>
              <div>
                <h3>系统健康</h3>
                <p>后端与数据库连接状态</p>
              </div>
            </header>
            <div :class="['home-health-badge', healthOk ? 'is-ok' : 'is-warn']">
              <strong>{{ healthOk ? '运行正常' : '待检测' }}</strong>
              <span>{{ healthOk ? '后端服务与数据库连接正常' : '健康检查暂未通过' }}</span>
            </div>
          </section>

          <section class="surface-card home-extra-card">
            <header class="home-extra-head">
              <span class="home-extra-icon tone-teal">
                <AppIcon name="folder" :size="18" />
              </span>
              <div>
                <h3>文档处理管道</h3>
                <p>解析、索引与失败文档</p>
              </div>
            </header>
            <ul class="home-pipeline-list">
              <li v-for="row in pipelineRows" :key="row.label">
                <span>{{ row.label }}</span>
                <strong>{{ row.value }}</strong>
              </li>
            </ul>
            <div class="home-index-row">
              <span>索引覆盖率</span>
              <strong>{{ indexPercent }}%</strong>
            </div>
            <div class="home-progress-track">
              <span class="home-progress-fill" :style="{ width: `${indexPercent}%` }"></span>
            </div>
          </section>

          <section class="surface-card home-extra-card">
            <header class="home-extra-head">
              <span class="home-extra-icon tone-indigo">
                <AppIcon name="chat" :size="18" />
              </span>
              <div>
                <h3>Agentic 对话占比</h3>
                <p>智能体模式 vs 经典 RAG</p>
              </div>
            </header>
            <div class="home-agentic-stats">
              <div>
                <strong>{{ formatNumber(overview.chat.agentic_conversation_total) }}</strong>
                <span>Agentic</span>
              </div>
              <div>
                <strong>{{ formatNumber(overview.chat.classic_conversation_total) }}</strong>
                <span>经典 RAG</span>
              </div>
            </div>
            <div class="home-agentic-bar" aria-hidden="true">
              <span class="home-agentic-seg home-agentic-seg--agentic" :style="{ width: `${agenticPercent}%` }"></span>
              <span class="home-agentic-seg home-agentic-seg--classic" :style="{ width: `${classicPercent}%` }"></span>
            </div>
          </section>

          <section class="surface-card home-extra-card">
            <header class="home-extra-head">
              <span class="home-extra-icon tone-amber">
                <AppIcon name="status" :size="18" />
              </span>
              <div>
                <h3>最近活动</h3>
                <p>当前空间最近 8 条审计</p>
              </div>
            </header>
            <ul v-if="overview.recent_audit.length" class="home-audit-list">
              <li v-for="item in overview.recent_audit" :key="item.id" class="home-audit-row">
                <div class="home-audit-main">
                  <strong>{{ item.action }}</strong>
                  <span>{{ item.message || `${item.resource_type}${item.resource_id ? ` #${item.resource_id}` : ''}` }}</span>
                </div>
                <div class="home-audit-meta">
                  <span>{{ item.username || '系统' }}</span>
                  <time>{{ formatAuditTime(item.created_at) }}</time>
                </div>
              </li>
            </ul>
            <p v-else class="home-audit-empty">暂无审计记录</p>
          </section>
        </div>

        <section class="surface-card home-shortcuts">
          <header class="home-section-head home-section-head--compact">
            <span class="home-section-icon tone-indigo">
              <AppIcon name="dashboard" :size="20" />
            </span>
            <div class="home-section-title">
              <h3>快捷入口</h3>
              <p>常用功能一键直达</p>
            </div>
          </header>
          <div class="home-shortcut-grid">
            <router-link v-for="link in quickLinks" :key="link.to" :to="link.to" class="home-shortcut-tile">
              <span :class="['home-shortcut-icon', link.tone]">
                <AppIcon :name="link.icon" :size="22" />
              </span>
              <strong>{{ link.title }}</strong>
              <span>{{ link.caption }}</span>
            </router-link>
          </div>
        </section>
      </template>
    </div>
  </Layout>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import { getDashboardOverview, type DashboardOverview } from '../api/dashboard'
import AppIcon from '../components/AppIcon.vue'
import KnowledgeUsagePanel from '../components/dashboard/KnowledgeUsagePanel.vue'
import UsageStatsSection from '../components/dashboard/UsageStatsSection.vue'
import Layout from '../components/Layout.vue'
import { useSpaceReadyLoader } from '../composables/useSpaceReady'
import { http } from '../lib/http'
import { useAuthStore } from '../stores/auth'

type HealthPayload = {
  status: string
  database: string
}

const authStore = useAuthStore()

const loading = ref(true)
const error = ref('')
const overview = ref<DashboardOverview | null>(null)
const health = ref<HealthPayload | null>(null)

const healthOk = computed(() => health.value?.status === 'ok' && health.value?.database === 'ok')

const quickLinks = [
  { title: '知识库', caption: '资产管理', to: '/knowledge-bases', icon: 'knowledge', tone: 'tone-blue' },
  { title: '检索', caption: '召回验证', to: '/retrieval', icon: 'retrieval', tone: 'tone-indigo' },
  { title: '聊天助手', caption: '智能问答', to: '/chat', icon: 'chat', tone: 'tone-green' },
  { title: '模型', caption: 'Provider', to: '/providers', icon: 'models', tone: 'tone-amber' },
] as const

const topMetrics = computed(() => {
  if (!overview.value) return []
  const data = overview.value
  return [
    { label: '知识库个数', value: formatNumber(data.knowledge.total), icon: 'knowledge', tone: 'tone-blue' },
    { label: '文档总数', value: formatNumber(data.knowledge.document_total), icon: 'folder', tone: 'tone-teal' },
    { label: '对话数', value: formatNumber(data.chat.conversation_total), icon: 'chat', tone: 'tone-green' },
    { label: '总消息数', value: formatNumber(data.chat.message_total), icon: 'send', tone: 'tone-purple' },
    { label: '用户数', value: formatNumber(data.users.member_total), icon: 'user', tone: 'tone-amber' },
  ]
})

const indexPercent = computed(() => {
  if (!overview.value) return 0
  const total = overview.value.knowledge.document_total
  if (!total) return 0
  return Math.min(100, Math.round((overview.value.knowledge.indexed_document_total / total) * 100))
})

const agenticPercent = computed(() => {
  if (!overview.value) return 0
  const total = overview.value.chat.conversation_total
  if (!total) return 0
  return Math.round((overview.value.chat.agentic_conversation_total / total) * 100)
})

const classicPercent = computed(() => Math.max(0, 100 - agenticPercent.value))

const pipelineRows = computed(() => {
  if (!overview.value) return []
  const p = overview.value.document_pipeline
  return [
    { label: '解析/处理中', value: formatNumber(p.parsing) },
    { label: '已索引', value: formatNumber(p.indexed) },
    { label: '失败', value: formatNumber(p.failed) },
  ]
})

function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function formatAuditTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const fetchDashboard = async () => {
  if (!authStore.currentSpaceSlug) {
    overview.value = null
    error.value = '请先选择企业空间'
    loading.value = false
    return
  }

  loading.value = true
  error.value = ''
  const [dashboardResult, healthResult] = await Promise.allSettled([
    getDashboardOverview(),
    http.get<HealthPayload>('/health'),
  ])

  if (dashboardResult.status === 'fulfilled') {
    overview.value = dashboardResult.value.data
  } else {
    overview.value = null
    error.value = '无法加载企业空间仪表盘数据'
  }

  health.value = healthResult.status === 'fulfilled' ? healthResult.value.data : null
  loading.value = false
}

useSpaceReadyLoader(fetchDashboard)
</script>

<style scoped>
.home-view {
  gap: 20px;
}

.error-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.error-panel h3 {
  margin: 0;
}

.error-panel p {
  margin: 8px 0 0;
  color: var(--text-secondary);
}

.home-kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
}

.home-kpi-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 16px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-secondary);
  box-shadow: var(--card-shadow-xs);
}

.home-kpi-card--skeleton {
  min-height: 88px;
  background: linear-gradient(120deg, var(--bg-tertiary) 0%, rgba(148, 163, 184, 0.14) 50%, var(--bg-tertiary) 100%);
}

.home-kpi-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  flex-shrink: 0;
}

.home-kpi-body {
  min-width: 0;
}

.home-kpi-value {
  margin: 0;
  font-size: 1.65rem;
  font-weight: 700;
  line-height: 1.1;
  color: var(--text-primary);
}

.home-kpi-label {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 0.84rem;
}

.home-kpi-sub {
  margin: 2px 0 0;
  color: var(--text-tertiary);
  font-size: 0.72rem;
  opacity: 0.85;
}

.tone-blue,
.home-kpi-icon.tone-blue,
.home-section-icon.tone-blue,
.home-shortcut-icon.tone-blue,
.home-extra-icon.tone-blue {
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
}

.tone-teal,
.home-extra-icon.tone-teal {
  background: rgba(20, 184, 166, 0.12);
  color: #0d9488;
}

.tone-indigo,
.home-section-icon.tone-indigo,
.home-shortcut-icon.tone-indigo,
.home-extra-icon.tone-indigo {
  background: rgba(99, 102, 241, 0.12);
  color: #4f46e5;
}

.tone-green,
.home-section-icon.tone-green,
.home-shortcut-icon.tone-green,
.home-extra-icon.tone-green {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}

.tone-purple,
.home-kpi-icon.tone-purple {
  background: rgba(139, 92, 246, 0.12);
  color: #7c3aed;
}

.tone-amber,
.home-section-icon.tone-amber,
.home-shortcut-icon.tone-amber,
.home-extra-icon.tone-amber {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}

.home-extras-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.home-extra-card {
  display: grid;
  gap: 14px;
  align-content: start;
}

.home-extra-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.home-extra-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  flex-shrink: 0;
}

.home-extra-head h3 {
  margin: 0;
  font-size: 0.95rem;
}

.home-extra-head p {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 0.78rem;
}

.home-health-badge {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.home-health-badge.is-ok {
  background: rgba(34, 197, 94, 0.08);
}

.home-health-badge.is-warn {
  background: rgba(245, 158, 11, 0.08);
}

.home-health-badge strong {
  color: var(--text-primary);
}

.home-health-badge span {
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.home-pipeline-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.home-pipeline-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 10px;
  background: var(--bg-tertiary);
  font-size: 0.86rem;
}

.home-index-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.84rem;
  color: var(--text-secondary);
}

.home-progress-track {
  height: 8px;
  border-radius: 999px;
  background: var(--bg-tertiary);
  overflow: hidden;
}

.home-progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #14b8a6, #22c55e);
}

.home-agentic-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.home-agentic-stats div {
  display: grid;
  gap: 4px;
  padding: 10px;
  border-radius: 12px;
  background: var(--bg-tertiary);
  text-align: center;
}

.home-agentic-stats strong {
  font-size: 1.2rem;
}

.home-agentic-stats span {
  color: var(--text-tertiary);
  font-size: 0.78rem;
}

.home-agentic-bar {
  display: flex;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--bg-tertiary);
}

.home-agentic-seg--agentic {
  background: #8b5cf6;
}

.home-agentic-seg--classic {
  background: #3b82f6;
}

.home-audit-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
  max-height: 280px;
  overflow: auto;
}

.home-audit-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--bg-tertiary);
}

.home-audit-main {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.home-audit-main strong {
  font-size: 0.84rem;
}

.home-audit-main span {
  color: var(--text-tertiary);
  font-size: 0.78rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home-audit-meta {
  display: grid;
  justify-items: end;
  gap: 2px;
  flex-shrink: 0;
  font-size: 0.74rem;
  color: var(--text-tertiary);
}

.home-audit-empty {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 0.84rem;
}

.home-section-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.home-section-head--compact {
  margin-bottom: 4px;
}

.home-section-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  flex-shrink: 0;
}

.home-section-title h3 {
  margin: 0;
  font-size: 1rem;
}

.home-section-title p {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.home-shortcuts {
  display: grid;
  gap: 16px;
}

.home-shortcut-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.home-shortcut-tile {
  display: grid;
  justify-items: center;
  gap: 8px;
  padding: 20px 12px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-tertiary);
  text-align: center;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.home-shortcut-tile:hover {
  transform: translateY(-2px);
  border-color: var(--brand-primary);
  background: var(--bg-secondary);
}

.home-shortcut-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 16px;
}

.home-shortcut-tile strong {
  color: var(--text-primary);
  font-size: 0.92rem;
}

.home-shortcut-tile > span:last-child {
  color: var(--text-tertiary);
  font-size: 0.78rem;
}

@media (max-width: 1280px) {
  .home-kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .home-extras-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 820px) {
  .home-kpi-grid,
  .home-shortcut-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
