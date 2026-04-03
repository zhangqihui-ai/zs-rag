<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import Layout from '../components/Layout.vue'

const appStore = useAppStore()

const statusText = computed(() => {
  if (appStore.loading) {
    return '检查中...'
  }
  if (appStore.error) {
    return appStore.error
  }
  if (appStore.health) {
    return `服务 ${appStore.health.status} / 数据库 ${appStore.health.database}`
  }
  return '等待检查'
})

onMounted(() => {
  void appStore.fetchHealth()
})
</script>

<template>
  <Layout>
    <section class="panel">
      <div>
        <p class="label">后端健康状态</p>
        <h2>{{ statusText }}</h2>
        <p class="description">
          默认请求 <code>/health</code>，用于验收前后端基础连通性。
        </p>
      </div>
      <button type="button" class="action" @click="appStore.fetchHealth">
        重新检测
      </button>
    </section>
  </Layout>
</template>

<style scoped>
.panel {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: center;
  padding: 28px;
  border-radius: 24px;
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(125, 211, 252, 0.18);
  box-shadow: 0 20px 45px rgba(8, 17, 32, 0.35);
}

.label {
  margin: 0 0 8px;
  color: #7dd3fc;
  font-size: 0.95rem;
}

h2 {
  margin: 0;
  font-size: 1.6rem;
}

.description {
  margin: 12px 0 0;
  color: #cbd5e1;
}

code {
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.14);
}

.action {
  border: 0;
  border-radius: 999px;
  padding: 12px 20px;
  background: linear-gradient(135deg, #38bdf8, #2563eb);
  color: white;
  cursor: pointer;
  white-space: nowrap;
}

.action:hover {
  opacity: 0.92;
}

@media (max-width: 720px) {
  .panel {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
