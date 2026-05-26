<template>
  <div class="no-space-page">
    <div class="no-space-card">
      <div class="no-space-icon">
        <AppIcon name="workspace" :size="32" />
      </div>
      <h1>尚未分配企业空间</h1>
      <p>您尚未被分配到任何企业空间，请联系管理员分配企业空间后再使用平台功能。</p>
      <button class="btn btn-primary" type="button" @click="handleLogout">
        <AppIcon name="logout" :size="16" />
        退出登录
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

import AppIcon from '../components/AppIcon.vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.no-space-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: var(--bg-primary);
}

.no-space-card {
  max-width: 480px;
  width: 100%;
  padding: 48px 40px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  box-shadow: var(--card-shadow);
  text-align: center;
}

.no-space-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  margin-bottom: 24px;
  border-radius: 20px;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
}

.no-space-card h1 {
  margin: 0 0 12px;
  color: var(--text-primary);
  font-size: 1.5rem;
}

.no-space-card p {
  margin: 0 0 28px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.no-space-card .btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
</style>
