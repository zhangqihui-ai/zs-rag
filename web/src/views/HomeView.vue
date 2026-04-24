<template>
  <Layout>
    <div class="page-shell home-view">
      <section class="hero-card">
        <div class="hero-main">
          <span class="hero-eyebrow">Enterprise RAG Workspace</span>
          <h2>统一管理知识资产、检索链路与模型供给</h2>
          <p>
            面向企业知识平台场景，聚焦知识库治理、检索验证、模型编排与系统运营，帮助团队在同一工作台内高效完成配置与协同。
          </p>
          <div class="hero-meta">
            <span class="chip chip-brand">
              <AppIcon name="workspace" :size="14" />
              {{ authStore.currentSpace?.name || '未选择企业空间' }}
            </span>
            <span class="chip">
              <AppIcon name="shield" :size="14" />
              {{ authStore.currentUser?.is_admin ? '管理员视角' : '成员视角' }}
            </span>
            <span class="chip">
              <AppIcon :name="appStore.isDark ? 'moon' : 'sun'" :size="14" />
              {{ appStore.isDark ? '深色主题' : '浅色主题' }}
            </span>
          </div>
        </div>

        <div class="hero-actions">
          <router-link to="/knowledge-bases" class="btn btn-primary">
            <AppIcon name="knowledge" :size="16" />
            进入知识库管理
          </router-link>
          <router-link to="/providers" class="btn btn-secondary">
            <AppIcon name="models" :size="16" />
            查看模型管理
          </router-link>
        </div>
      </section>

      <section class="metrics-grid">
        <article v-for="metric in metrics" :key="metric.label" class="metric-card">
          <div class="metric-card-header">
            <span class="metric-icon">
              <AppIcon :name="metric.icon" :size="18" />
            </span>
            <span :class="['status-pill', metric.tone]">{{ metric.badge }}</span>
          </div>
          <p class="metric-label">{{ metric.label }}</p>
          <p class="metric-value">{{ metric.value }}</p>
          <p class="metric-meta">{{ metric.meta }}</p>
        </article>
      </section>

      <div class="page-grid dashboard-grid">
        <section class="surface-card">
          <div class="section-heading">
            <div>
              <h3>系统状态总览</h3>
              <p>实时关注后端服务、数据库连接与工作空间上下文。</p>
            </div>
            <button class="btn btn-ghost" type="button" @click="fetchDashboard">
              <AppIcon name="refresh" :size="16" />
              刷新
            </button>
          </div>

          <div v-if="loading" class="status-list loading-skeleton skeleton-panel"></div>
          <div v-else class="status-list">
            <div v-for="item in statusItems" :key="item.label" class="status-row">
              <div class="status-row-main">
                <span class="status-row-icon" :class="item.tone">
                  <AppIcon :name="item.icon" :size="16" />
                </span>
                <div>
                  <strong>{{ item.label }}</strong>
                  <p>{{ item.description }}</p>
                </div>
              </div>
              <span :class="['status-pill', item.tone]">{{ item.value }}</span>
            </div>
          </div>
        </section>

        <section class="surface-card">
          <div class="section-heading">
            <div>
              <h3>快捷入口</h3>
              <p>围绕企业级 RAG 平台日常运营的高频操作。</p>
            </div>
          </div>

          <div class="quick-link-list">
            <router-link v-for="link in quickLinks" :key="link.to" :to="link.to" class="quick-link-card">
              <span class="quick-link-icon">
                <AppIcon :name="link.icon" :size="18" />
              </span>
              <div>
                <strong>{{ link.title }}</strong>
                <p>{{ link.description }}</p>
              </div>
              <AppIcon name="arrow-up-right" :size="16" />
            </router-link>
          </div>
        </section>

        <section class="surface-card">
          <div class="section-heading">
            <div>
              <h3>今日重点</h3>
              <p>建议优先检查的工作项，帮助平台快速进入稳定运营状态。</p>
            </div>
          </div>

          <div class="focus-list">
            <article v-for="item in focusItems" :key="item.title" class="focus-item">
              <span class="focus-icon">
                <AppIcon :name="item.icon" :size="16" />
              </span>
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.description }}</p>
              </div>
            </article>
          </div>
        </section>

        <section class="surface-card">
          <div class="section-heading">
            <div>
              <h3>平台治理建议</h3>
              <p>基于当前页面能力整理的运营建议，用于指导后续配置与验收。</p>
            </div>
          </div>

          <div class="governance-list">
            <div class="governance-item">
              <strong>1. 先配置默认模型</strong>
              <p>完成 LLM、Embedding 等默认模型编排，确保检索和对话链路具备可执行基础。</p>
            </div>
            <div class="governance-item">
              <strong>2. 再治理知识资产</strong>
              <p>建立统一知识库结构，明确向量库与图谱库的职责边界，避免检索质量不稳定。</p>
            </div>
            <div class="governance-item">
              <strong>3. 最后验证检索与对话</strong>
              <p>通过检索测试页与对话工作台，持续观察召回相关性、引用来源与回答可信度。</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  </Layout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { knowledgeBaseApi } from '../api/knowledge-base'
import { providerApi } from '../api/model-management'
import AppIcon from '../components/AppIcon.vue'
import Layout from '../components/Layout.vue'
import { http } from '../lib/http'
import { useAppStore } from '../stores/app'
import { useAuthStore } from '../stores/auth'

type HealthPayload = {
  status: string
  database: string
}

const authStore = useAuthStore()
const appStore = useAppStore()

const loading = ref(true)
const health = ref<HealthPayload | null>(null)
const providersCount = ref(0)
const knowledgeBasesCount = ref(0)

const quickLinks = [
  {
    title: '知识库管理',
    description: '查看知识库、向量库与图谱连接的配置状态。',
    to: '/knowledge-bases',
    icon: 'knowledge',
  },
  {
    title: '知识检索',
    description: '验证查询输入、召回结果与排序策略。',
    to: '/retrieval',
    icon: 'retrieval',
  },
  {
    title: '对话工作台',
    description: '模拟企业知识助手对话流程与引用链路。',
    to: '/chat',
    icon: 'chat',
  },
  {
    title: '模型管理',
    description: '维护厂商接入、模型同步与默认模型设置。',
    to: '/providers',
    icon: 'models',
  },
] as const

const focusItems = [
  {
    title: '检查默认模型是否完整',
    description: '确保问答链路最少具备 LLM 与 Embedding 两类模型，以便后续功能可直接联调。',
    icon: 'spark',
  },
  {
    title: '确认知识库连接策略',
    description: '为不同业务场景分别建立向量数据库与图数据库配置，避免混用带来的维护成本。',
    icon: 'database',
  },
  {
    title: '建立检索验收基线',
    description: '针对关键问题预设查询样例，持续观察召回数量、匹配类型与答案引用质量。',
    icon: 'status',
  },
] as const

const metrics = computed(() => [
  {
    label: '企业空间',
    value: String(authStore.enterpriseSpaces.length).padStart(2, '0'),
    meta: authStore.currentSpace ? `当前：${authStore.currentSpace.name}` : '尚未选择工作空间',
    badge: '组织视图',
    tone: 'info',
    icon: 'workspace',
  },
  {
    label: '知识库总数',
    value: String(knowledgeBasesCount.value).padStart(2, '0'),
    meta: '包括已启用向量库与图谱配置的知识资产集合',
    badge: '知识资产',
    tone: knowledgeBasesCount.value > 0 ? 'success' : 'warning',
    icon: 'knowledge',
  },
  {
    label: '模型 Provider',
    value: String(providersCount.value).padStart(2, '0'),
    meta: '已接入并可同步模型的厂商配置数量',
    badge: providersCount.value > 0 ? '已接入' : '待配置',
    tone: providersCount.value > 0 ? 'success' : 'warning',
    icon: 'models',
  },
  {
    label: '系统健康',
    value: health.value?.status === 'ok' ? 'OK' : 'N/A',
    meta: health.value?.database === 'ok' ? '数据库连接正常' : '等待健康检查',
    badge: health.value?.status === 'ok' ? '稳定运行' : '待检测',
    tone: health.value?.status === 'ok' ? 'success' : 'warning',
    icon: 'server',
  },
])

const statusItems = computed(() => [
  {
    label: '后端服务',
    description: '用于支撑知识库、模型配置与系统接口调用。',
    value: health.value?.status === 'ok' ? '运行正常' : '待检测',
    tone: health.value?.status === 'ok' ? 'success' : 'warning',
    icon: 'server',
  },
  {
    label: '数据库连接',
    description: '用于保存业务配置、知识资产和平台元数据。',
    value: health.value?.database === 'ok' ? '连接正常' : '待检测',
    tone: health.value?.database === 'ok' ? 'success' : 'warning',
    icon: 'database',
  },
  {
    label: '企业空间上下文',
    description: '所有请求均带有当前企业空间上下文头信息。',
    value: authStore.currentSpace?.name || '未配置',
    tone: authStore.currentSpace ? 'info' : 'warning',
    icon: 'workspace',
  },
  {
    label: '主题模式',
    description: '支持浅色/深色主题切换，适用于企业后台日常使用。',
    value: appStore.isDark ? '深色主题' : '浅色主题',
    tone: 'info',
    icon: appStore.isDark ? 'moon' : 'sun',
  },
])

const fetchDashboard = async () => {
  loading.value = true
  const [healthResult, providersResult, knowledgeResult] = await Promise.allSettled([
    http.get<HealthPayload>('/health'),
    providerApi.getProviders(),
    knowledgeBaseApi.list(),
  ])

  health.value = healthResult.status === 'fulfilled' ? healthResult.value.data : null
  providersCount.value = providersResult.status === 'fulfilled' ? providersResult.value.length : 0
  knowledgeBasesCount.value = knowledgeResult.status === 'fulfilled' ? knowledgeResult.value.length : 0
  loading.value = false
}

onMounted(() => {
  fetchDashboard()
})
</script>

<style scoped>
.home-view {
  gap: 28px;
}

.hero-card {
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  gap: 24px;
  padding: 30px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--surface-overlay) 100%);
  box-shadow: var(--card-shadow);
}

.hero-main {
  display: grid;
  gap: 16px;
  max-width: 820px;
}

.hero-eyebrow {
  display: inline-flex;
  width: fit-content;
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-main h2 {
  margin: 0;
  font-size: clamp(2rem, 3vw, 2.8rem);
  line-height: 1.1;
  color: var(--text-primary);
}

.hero-main p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 1rem;
  line-height: 1.75;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-actions {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: stretch;
  gap: 12px;
  min-width: 220px;
}

.dashboard-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.status-list,
.focus-list,
.governance-list,
.quick-link-list {
  display: grid;
  gap: 14px;
}

.skeleton-panel {
  min-height: 240px;
  border-radius: 18px;
  background: linear-gradient(120deg, var(--bg-tertiary) 0%, rgba(148, 163, 184, 0.16) 50%, var(--bg-tertiary) 100%);
}

.status-row,
.focus-item,
.governance-item,
.quick-link-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: var(--bg-tertiary);
}

.status-row {
  justify-content: space-between;
}

.status-row-main {
  display: flex;
  gap: 14px;
}

.status-row-main strong,
.focus-item strong,
.governance-item strong,
.quick-link-card strong {
  color: var(--text-primary);
}

.status-row-main p,
.focus-item p,
.governance-item p,
.quick-link-card p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  line-height: 1.65;
}

.status-row-icon,
.focus-icon,
.quick-link-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 14px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  flex-shrink: 0;
}

.status-row-icon.success,
.focus-icon {
  color: var(--success-color);
}

.status-row-icon.warning {
  color: var(--warning-color);
}

.status-row-icon.info,
.quick-link-icon {
  color: var(--brand-primary);
}

.quick-link-card {
  justify-content: space-between;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.quick-link-card:hover {
  transform: translateY(-2px);
  border-color: var(--brand-primary);
  background: var(--bg-secondary);
}

@media (max-width: 1200px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .hero-card {
    flex-direction: column;
  }

  .hero-actions {
    min-width: 0;
  }

  .status-row {
    flex-direction: column;
  }
}
</style>
