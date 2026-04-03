<template>
  <Layout>
    <div class="dashboard">
      <div class="welcome-card">
        <h1>欢迎使用 ZS-RAG</h1>
        <p class="subtitle">企业级 RAG 知识库管理平台</p>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon">📊</div>
          <div class="stat-content">
            <div class="stat-value">{{ authStore.enterpriseSpaces.length }}</div>
            <div class="stat-label">企业空间</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon">🤖</div>
          <div class="stat-content">
            <div class="stat-value">{{ providersCount }}</div>
            <div class="stat-label">模型 Provider</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon">📚</div>
          <div class="stat-content">
            <div class="stat-value">{{ knowledgeBasesCount }}</div>
            <div class="stat-label">知识库</div>
          </div>
        </div>
      </div>

      <div class="quick-actions">
        <h2>快速访问</h2>
        <div class="actions-grid">
          <router-link to="/providers" class="action-card">
            <div class="action-icon">🔧</div>
            <h3>模型管理</h3>
            <p>配置和管理 AI 模型 Provider</p>
          </router-link>

          <router-link to="/knowledge-bases" class="action-card">
            <div class="action-icon">📖</div>
            <h3>知识库管理</h3>
            <p>管理向量数据库和图数据库连接</p>
          </router-link>
        </div>
      </div>

      <div class="system-status">
        <h2>系统状态</h2>
        <div v-if="loading" class="loading">检查中...</div>
        <div v-else-if="error" class="error">{{ error }}</div>
        <div v-else class="status-grid">
          <div class="status-item">
            <span class="status-dot success"></span>
            <span>后端服务</span>
            <span class="status-detail">{{ health?.status === 'ok' ? '正常' : '异常' }}</span>
          </div>
          <div class="status-item">
            <span class="status-dot success"></span>
            <span>数据库</span>
            <span class="status-detail">{{ health?.database === 'ok' ? '正常' : '异常' }}</span>
          </div>
          <div class="status-item">
            <span :class="['status-dot', currentSpace ? 'success' : 'warning']"></span>
            <span>当前企业空间</span>
            <span class="status-detail">{{ currentSpace?.name || '未选择' }}</span>
          </div>
        </div>
      </div>
    </div>
  </Layout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { http } from '../lib/http'
import Layout from '../components/Layout.vue'

const authStore = useAuthStore()

const health = ref<{ status: string; database: string } | null>(null)
const loading = ref(true)
const error = ref('')
const providersCount = ref(0)
const knowledgeBasesCount = ref(0)

const currentSpace = computed(() => authStore.currentSpace)

const fetchStats = async () => {
  loading.value = true
  error.value = ''

  try {
    // Fetch health
    const { data: healthData } = await http.get('/health')
    health.value = healthData

    // Fetch providers count
    try {
      const { data: providers } = await http.get('/providers')
      providersCount.value = providers.length
    } catch (err) {
      providersCount.value = 0
    }

    // Fetch knowledge bases count
    try {
      const { data: kbs } = await http.get('/knowledge-bases')
      knowledgeBasesCount.value = kbs.length
    } catch (err) {
      knowledgeBasesCount.value = 0
    }
  } catch (err) {
    error.value = '加载系统状态失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchStats()
})
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.welcome-card {
  background: linear-gradient(135deg, rgba(124, 211, 252, 0.1) 0%, rgba(56, 189, 248, 0.05) 100%);
  border: 1px solid rgba(124, 211, 252, 0.2);
  border-radius: 16px;
  padding: 32px;
  text-align: center;
}

.welcome-card h1 {
  margin: 0 0 8px;
  font-size: 2rem;
  color: #e2e8f0;
}

.subtitle {
  margin: 0;
  color: #94a3b8;
  font-size: 1rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.stat-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  font-size: 2.5rem;
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: #7dd3fc;
}

.stat-label {
  color: #94a3b8;
  font-size: 0.9rem;
}

.quick-actions h2,
.system-status h2 {
  margin: 0 0 16px;
  font-size: 1.25rem;
  color: #e2e8f0;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
}

.action-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 24px;
  text-decoration: none;
  transition: all 0.2s;
}

.action-card:hover {
  border-color: rgba(124, 211, 252, 0.3);
  background: rgba(255, 255, 255, 0.05);
  transform: translateY(-2px);
}

.action-icon {
  font-size: 2rem;
  margin-bottom: 12px;
}

.action-card h3 {
  margin: 0 0 8px;
  color: #e2e8f0;
  font-size: 1.1rem;
}

.action-card p {
  margin: 0;
  color: #64748b;
  font-size: 0.9rem;
}

.system-status {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 24px;
}

.status-grid {
  display: grid;
  gap: 16px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #e2e8f0;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.status-dot.success {
  background: #4ade80;
  box-shadow: 0 0 10px rgba(74, 222, 128, 0.5);
}

.status-dot.warning {
  background: #fbbf24;
  box-shadow: 0 0 10px rgba(251, 191, 36, 0.5);
}

.status-dot.error {
  background: #f87171;
  box-shadow: 0 0 10px rgba(248, 113, 113, 0.5);
}

.status-detail {
  color: #94a3b8;
  margin-left: auto;
}

.loading,
.error {
  text-align: center;
  padding: 24px;
  color: #64748b;
}

.error {
  color: #f87171;
}
</style>
