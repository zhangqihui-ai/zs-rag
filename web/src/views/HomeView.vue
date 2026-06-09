<template>
  <Layout>
    <div class="page-shell home-view">
      <header class="dashboard-header surface-card">
        <div>
          <span class="dashboard-eyebrow">企业空间仪表盘</span>
          <h2>{{ overview?.space_name || authStore.currentSpace?.name || '未选择企业空间' }}</h2>
          <p>以下指标均来自当前企业空间。</p>
        </div>
        <div class="dashboard-header-actions">
          <span class="chip chip-brand">
            <AppIcon name="workspace" :size="14" />
            {{ authStore.roleLabel }}
          </span>
          <button class="btn btn-ghost" type="button" :disabled="loading" @click="fetchDashboard">
            <AppIcon name="refresh" :size="16" />
            刷新
          </button>
        </div>
      </header>

      <section v-if="loading" class="home-kpi-grid">
        <article v-for="n in 6" :key="n" class="home-kpi-card home-kpi-card--skeleton"></article>
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
            </div>
          </article>
        </section>

        <div class="home-panels">
          <section class="surface-card home-section">
            <header class="home-section-head">
              <span class="home-section-icon tone-blue">
                <AppIcon name="knowledge" :size="20" />
              </span>
              <div class="home-section-title">
                <h3>知识库使用情况</h3>
                <p>资产规模与类型分布</p>
              </div>
              <router-link to="/knowledge-bases" class="btn btn-ghost home-section-link">管理</router-link>
            </header>

            <div class="home-stat-strip">
              <div v-for="item in knowledgeStrip" :key="item.label" class="home-stat-item">
                <span :class="['home-stat-icon', item.tone]">
                  <AppIcon :name="item.icon" :size="16" />
                </span>
                <strong :class="item.color">{{ item.value }}</strong>
                <span>{{ item.label }}</span>
              </div>
            </div>

            <div class="home-visual-block">
              <div class="home-visual-head">
                <span>类型分布</span>
                <span class="home-visual-meta">向量 {{ overview.knowledge.vector }} · 图 {{ overview.knowledge.graph }}</span>
              </div>
              <div class="home-stack-bar" aria-hidden="true">
                <span
                  class="home-stack-seg home-stack-seg--vector"
                  :style="{ width: `${kbVectorPercent}%` }"
                ></span>
                <span
                  class="home-stack-seg home-stack-seg--graph"
                  :style="{ width: `${kbGraphPercent}%` }"
                ></span>
              </div>
              <div class="home-legend">
                <span><i class="dot dot-blue"></i>向量库 Milvus</span>
                <span><i class="dot dot-red"></i>图库 LightRAG</span>
              </div>
            </div>

            <div class="home-visual-block">
              <div class="home-visual-head">
                <span>索引覆盖率</span>
                <span class="home-visual-meta">{{ indexPercent }}%</span>
              </div>
              <div class="home-progress-track">
                <span class="home-progress-fill" :style="{ width: `${indexPercent}%` }"></span>
              </div>
            </div>
          </section>

          <section class="surface-card home-section">
            <header class="home-section-head">
              <span class="home-section-icon tone-green">
                <AppIcon name="chat" :size="20" />
              </span>
              <div class="home-section-title">
                <h3>对话与检索</h3>
                <p>空间内问答与召回语料</p>
              </div>
              <div class="home-section-links">
                <router-link to="/chat" class="btn btn-ghost home-section-link">对话</router-link>
                <router-link to="/retrieval" class="btn btn-ghost home-section-link">检索</router-link>
              </div>
            </header>

            <div class="home-stat-strip">
              <div v-for="item in chatStrip" :key="item.label" class="home-stat-item">
                <span :class="['home-stat-icon', item.tone]">
                  <AppIcon :name="item.icon" :size="16" />
                </span>
                <strong :class="item.color">{{ item.value }}</strong>
                <span>{{ item.label }}</span>
              </div>
            </div>

            <ul class="home-insight-list">
              <li v-for="row in retrievalInsights" :key="row.label" class="home-insight-row">
                <span :class="['home-insight-icon', row.tone]">
                  <AppIcon :name="row.icon" :size="16" />
                </span>
                <span class="home-insight-label">{{ row.label }}</span>
                <span class="home-insight-value">{{ row.value }}</span>
              </li>
            </ul>

            <div class="home-mini-bars" aria-hidden="true">
              <div v-for="bar in chatBars" :key="bar.label" class="home-mini-bar-row">
                <span class="home-mini-bar-label">{{ bar.label }}</span>
                <div class="home-mini-bar-track">
                  <span class="home-mini-bar-fill" :style="{ width: `${bar.percent}%`, background: bar.color }"></span>
                </div>
              </div>
            </div>
          </section>

          <section class="surface-card home-section">
            <header class="home-section-head">
              <span class="home-section-icon tone-amber">
                <AppIcon name="models" :size="20" />
              </span>
              <div class="home-section-title">
                <h3>模型与用户</h3>
                <p>模型供给与成员规模</p>
              </div>
              <router-link to="/providers" class="btn btn-ghost home-section-link">模型</router-link>
            </header>

            <div class="home-stat-strip">
              <div v-for="item in modelStrip" :key="item.label" class="home-stat-item">
                <span :class="['home-stat-icon', item.tone]">
                  <AppIcon :name="item.icon" :size="16" />
                </span>
                <strong :class="item.color">{{ item.value }}</strong>
                <span>{{ item.label }}</span>
              </div>
            </div>

            <ul class="home-insight-list">
              <li v-for="row in modelInsights" :key="row.label" class="home-insight-row">
                <span :class="['home-insight-icon', row.tone]">
                  <AppIcon :name="row.icon" :size="16" />
                </span>
                <span class="home-insight-label">{{ row.label }}</span>
                <span class="home-insight-value">{{ row.value }}</span>
              </li>
            </ul>

            <div class="home-health-row">
              <span :class="['home-health-icon', healthOk ? 'is-ok' : 'is-warn']">
                <AppIcon :name="healthOk ? 'shield' : 'status'" :size="18" />
              </span>
              <div>
                <strong>{{ healthOk ? '系统运行正常' : '系统待检测' }}</strong>
                <p>{{ healthOk ? '后端服务与数据库连接正常' : '健康检查暂未通过' }}</p>
              </div>
            </div>
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
import { computed, onMounted, ref } from 'vue'

import { getDashboardOverview, type DashboardOverview } from '../api/dashboard'
import AppIcon from '../components/AppIcon.vue'
import Layout from '../components/Layout.vue'
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
  { title: '对话', caption: '智能问答', to: '/chat', icon: 'chat', tone: 'tone-green' },
  { title: '模型', caption: 'Provider', to: '/providers', icon: 'models', tone: 'tone-amber' },
] as const

const topMetrics = computed(() => {
  if (!overview.value) {
    return []
  }
  const data = overview.value
  return [
    { label: '知识库', value: formatNumber(data.knowledge.total), icon: 'knowledge', tone: 'tone-blue' },
    { label: '文档', value: formatNumber(data.knowledge.document_total), icon: 'folder', tone: 'tone-teal' },
    { label: '检索片段', value: formatNumber(data.retrieval.chunk_total), icon: 'retrieval', tone: 'tone-indigo' },
    { label: '对话', value: formatNumber(data.chat.conversation_total), icon: 'chat', tone: 'tone-green' },
    { label: '消息', value: formatNumber(data.chat.message_total), icon: 'send', tone: 'tone-cyan' },
    { label: '成员', value: formatNumber(data.users.member_total), icon: 'user', tone: 'tone-amber' },
  ]
})

const kbVectorPercent = computed(() => {
  if (!overview.value) {
    return 0
  }
  const total = overview.value.knowledge.total
  if (!total) {
    return 0
  }
  return Math.round((overview.value.knowledge.vector / total) * 100)
})

const kbGraphPercent = computed(() => {
  if (!overview.value) {
    return 0
  }
  const total = overview.value.knowledge.total
  if (!total) {
    return 0
  }
  return Math.round((overview.value.knowledge.graph / total) * 100)
})

const indexPercent = computed(() => {
  if (!overview.value) {
    return 0
  }
  const total = overview.value.knowledge.document_total
  if (!total) {
    return 0
  }
  return Math.min(100, Math.round((overview.value.knowledge.indexed_document_total / total) * 100))
})

const knowledgeStrip = computed(() => {
  if (!overview.value) {
    return []
  }
  const k = overview.value.knowledge
  return [
    { label: '知识库总数', value: formatNumber(k.total), icon: 'knowledge', tone: 'tone-blue', color: 'c-blue' },
    { label: '文件总数', value: formatNumber(k.document_total), icon: 'folder', tone: 'tone-teal', color: 'c-teal' },
    { label: '存储容量', value: formatBytes(k.storage_bytes), icon: 'database', tone: 'tone-indigo', color: 'c-indigo' },
  ]
})

const chatStrip = computed(() => {
  if (!overview.value) {
    return []
  }
  const c = overview.value.chat
  return [
    { label: '对话总数', value: formatNumber(c.conversation_total), icon: 'chat', tone: 'tone-green', color: 'c-green' },
    { label: '会话总数', value: formatNumber(c.session_total), icon: 'panel', tone: 'tone-cyan', color: 'c-cyan' },
    { label: '消息总数', value: formatNumber(c.message_total), icon: 'send', tone: 'tone-blue', color: 'c-blue' },
  ]
})

const modelStrip = computed(() => {
  if (!overview.value) {
    return []
  }
  const m = overview.value.models
  const u = overview.value.users
  return [
    { label: 'Provider', value: formatNumber(m.provider_total), icon: 'server', tone: 'tone-amber', color: 'c-amber' },
    { label: '已启用模型', value: formatNumber(m.enabled_model_total), icon: 'models', tone: 'tone-indigo', color: 'c-indigo' },
    { label: '成员数', value: formatNumber(u.member_total), icon: 'user', tone: 'tone-green', color: 'c-green' },
  ]
})

const retrievalInsights = computed(() => {
  if (!overview.value) {
    return []
  }
  const r = overview.value.retrieval
  return [
    { label: '可检索知识库', value: formatNumber(r.ready_knowledge_base_total), icon: 'retrieval', tone: 'tone-indigo' },
    { label: '已索引文档', value: formatNumber(r.indexed_document_total), icon: 'folder', tone: 'tone-teal' },
    { label: '召回片段', value: formatNumber(r.chunk_total), icon: 'vector-db', tone: 'tone-blue' },
  ]
})

const modelInsights = computed(() => {
  if (!overview.value) {
    return []
  }
  const m = overview.value.models
  return [
    { label: 'LLM 模型', value: formatNumber(m.llm_total), icon: 'spark', tone: 'tone-amber' },
    { label: 'Embedding 模型', value: formatNumber(m.embedding_total), icon: 'vector-db', tone: 'tone-blue' },
    { label: '模型总数', value: formatNumber(m.model_total), icon: 'models', tone: 'tone-indigo' },
  ]
})

const chatBars = computed(() => {
  if (!overview.value) {
    return []
  }
  const c = overview.value.chat
  const max = Math.max(c.conversation_total, c.session_total, c.message_total, 1)
  return [
    { label: '对话', percent: Math.round((c.conversation_total / max) * 100), color: '#22c55e' },
    { label: '会话', percent: Math.round((c.session_total / max) * 100), color: '#06b6d4' },
    { label: '消息', percent: Math.round((c.message_total / max) * 100), color: '#3b82f6' },
  ]
})

function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function formatBytes(value: number): string {
  if (!value) {
    return '0 B'
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size >= 10 || unitIndex === 0 ? size.toFixed(unitIndex === 0 ? 0 : 1) : size.toFixed(2)} ${units[unitIndex]}`
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

onMounted(fetchDashboard)
</script>

<style scoped>
.home-view {
  gap: 20px;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  padding: 22px 24px;
}

.dashboard-eyebrow {
  display: inline-flex;
  margin-bottom: 6px;
  color: var(--brand-primary);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.dashboard-header h2 {
  margin: 0;
  font-size: clamp(1.5rem, 2.2vw, 1.85rem);
  color: var(--text-primary);
}

.dashboard-header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 0.92rem;
}

.dashboard-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
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

/* 顶部 KPI：左图标右数字 */
.home-kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
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

/* 色板 */
.tone-blue,
.home-kpi-icon.tone-blue,
.home-section-icon.tone-blue,
.home-stat-icon.tone-blue,
.home-insight-icon.tone-blue,
.home-shortcut-icon.tone-blue {
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
}

.tone-teal,
.home-stat-icon.tone-teal,
.home-insight-icon.tone-teal {
  background: rgba(20, 184, 166, 0.12);
  color: #0d9488;
}

.tone-indigo,
.home-section-icon.tone-indigo,
.home-stat-icon.tone-indigo,
.home-insight-icon.tone-indigo,
.home-shortcut-icon.tone-indigo {
  background: rgba(99, 102, 241, 0.12);
  color: #4f46e5;
}

.tone-green,
.home-section-icon.tone-green,
.home-stat-icon.tone-green,
.home-insight-icon.tone-green,
.home-shortcut-icon.tone-green {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}

.tone-cyan,
.home-stat-icon.tone-cyan {
  background: rgba(6, 182, 212, 0.12);
  color: #0891b2;
}

.tone-amber,
.home-section-icon.tone-amber,
.home-stat-icon.tone-amber,
.home-insight-icon.tone-amber,
.home-shortcut-icon.tone-amber {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}

.c-blue { color: #2563eb; }
.c-teal { color: #0d9488; }
.c-indigo { color: #4f46e5; }
.c-green { color: #16a34a; }
.c-cyan { color: #0891b2; }
.c-amber { color: #d97706; }

/* 下方三列模块 */
.home-panels {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.home-section {
  display: grid;
  gap: 18px;
  align-content: start;
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

.home-section-title {
  flex: 1;
  min-width: 0;
}

.home-section-title h3 {
  margin: 0;
  font-size: 1rem;
  color: var(--text-primary);
}

.home-section-title p {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.home-section-link {
  flex-shrink: 0;
  min-height: 32px;
  padding: 0 10px;
  font-size: 0.84rem;
}

.home-section-links {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.home-stat-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.home-stat-item {
  display: grid;
  justify-items: center;
  gap: 6px;
  padding: 12px 8px;
  border-radius: 14px;
  background: var(--bg-tertiary);
  text-align: center;
}

.home-stat-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
}

.home-stat-item strong {
  font-size: 1.2rem;
  line-height: 1.1;
}

.home-stat-item > span:last-child {
  color: var(--text-tertiary);
  font-size: 0.78rem;
}

.home-visual-block {
  display: grid;
  gap: 8px;
}

.home-visual-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 0.84rem;
  color: var(--text-secondary);
}

.home-visual-meta {
  color: var(--text-tertiary);
  font-size: 0.78rem;
}

.home-stack-bar {
  display: flex;
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--bg-tertiary);
}

.home-stack-seg--vector {
  background: linear-gradient(90deg, #2563eb, #60a5fa);
}

.home-stack-seg--graph {
  background: linear-gradient(90deg, #dc2626, #f87171);
}

.home-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  font-size: 0.78rem;
  color: var(--text-tertiary);
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 6px;
  border-radius: 999px;
  vertical-align: middle;
}

.dot-blue { background: #3b82f6; }
.dot-red { background: #ef4444; }

.home-progress-track,
.home-mini-bar-track {
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

.home-insight-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.home-insight-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--bg-tertiary);
}

.home-insight-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  flex-shrink: 0;
}

.home-insight-label {
  flex: 1;
  color: var(--text-secondary);
  font-size: 0.86rem;
}

.home-insight-value {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 0.92rem;
}

.home-mini-bars {
  display: grid;
  gap: 8px;
}

.home-mini-bar-row {
  display: grid;
  grid-template-columns: 36px 1fr;
  align-items: center;
  gap: 10px;
}

.home-mini-bar-label {
  font-size: 0.78rem;
  color: var(--text-tertiary);
}

.home-mini-bar-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.home-health-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.home-health-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  flex-shrink: 0;
}

.home-health-icon.is-ok {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}

.home-health-icon.is-warn {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}

.home-health-row strong {
  display: block;
  color: var(--text-primary);
  font-size: 0.92rem;
}

.home-health-row p {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 0.8rem;
}

/* 快捷入口 */
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

  .home-panels {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 820px) {
  .dashboard-header {
    flex-direction: column;
  }

  .home-kpi-grid,
  .home-shortcut-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .home-stat-strip {
    grid-template-columns: 1fr;
  }
}
</style>
