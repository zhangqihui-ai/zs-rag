<template>
  <div class="layout">
    <!-- 左侧导航栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="logo">ZS-RAG</span>
      </div>

      <nav class="sidebar-nav">
        <router-link to="/" class="nav-link">
          <span class="nav-icon">📊</span>
          <span class="nav-text">首页</span>
        </router-link>
        <router-link to="/providers" class="nav-link">
          <span class="nav-icon">🤖</span>
          <span class="nav-text">模型管理</span>
        </router-link>
        <router-link to="/knowledge-bases" class="nav-link">
          <span class="nav-icon">📚</span>
          <span class="nav-text">知识库管理</span>
        </router-link>
      </nav>
    </aside>

    <!-- 右侧内容区 -->
    <div class="content-wrapper">
      <!-- 顶部导航栏 -->
      <header class="top-navbar">
        <div class="top-navbar-left">
          <!-- 可以放面包屑或其他内容 -->
        </div>

        <div class="top-navbar-right">
          <SpaceSelector
            v-model="currentSpaceSlug"
            :spaces="authStore.enterpriseSpaces"
          />

          <div class="user-menu">
            <span class="username">{{ authStore.currentUser?.username || '用户' }}</span>
            <button @click="handleLogout" class="logout-button" title="退出登录">
              <span class="logout-text">退出</span>
            </button>
          </div>
        </div>
      </header>

      <!-- 主内容区 -->
      <main class="main-content">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import SpaceSelector from './SpaceSelector.vue'

const router = useRouter()
const authStore = useAuthStore()

const currentSpaceSlug = computed({
  get: () => authStore.currentSpaceSlug,
  set: (slug) => authStore.switchSpace(slug),
})

// 监听企业空间切换，刷新数据
watch(currentSpaceSlug, () => {
  router.go(0)
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  background: #0f172a;
}

/* ========== 左侧导航栏 ========== */
.sidebar {
  width: 260px;
  min-height: 100vh;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%);
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 100;
}

.sidebar-header {
  padding: 24px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo {
  font-size: 1.5rem;
  font-weight: 700;
  color: #7dd3fc;
  letter-spacing: 1px;
}

.sidebar-nav {
  flex: 1;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  color: #94a3b8;
  text-decoration: none;
  border-radius: 8px;
  transition: all 0.2s;
  font-size: 0.95rem;
}

.nav-link:hover {
  color: #e2e8f0;
  background: rgba(255, 255, 255, 0.05);
}

.nav-link.router-link-active {
  color: #7dd3fc;
  background: rgba(124, 211, 252, 0.15);
  font-weight: 500;
}

.nav-icon {
  font-size: 1.2rem;
  width: 24px;
  text-align: center;
}

.nav-text {
  flex: 1;
}

/* ========== 右侧内容区 ========== */
.content-wrapper {
  flex: 1;
  margin-left: 260px;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* ========== 顶部导航栏 ========== */
.top-navbar {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: rgba(15, 23, 42, 0.85);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  height: 64px;
}

.top-navbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.top-navbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: auto;
}

/* 用户菜单 */
.user-menu {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-left: 16px;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
}

.username {
  color: #e2e8f0;
  font-size: 0.9rem;
  font-weight: 500;
}

.logout-button {
  padding: 8px 16px;
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 6px;
  color: #f87171;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.logout-button:hover {
  background: rgba(248, 113, 113, 0.2);
  border-color: #f87171;
}

.logout-text {
  display: flex;
  align-items: center;
}

/* ========== 主内容区 ========== */
.main-content {
  flex: 1;
  padding: 24px;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  overflow-y: auto;
  min-height: calc(100vh - 64px);
}

/* ========== 响应式 ========== */
@media (max-width: 768px) {
  .sidebar {
    width: 200px;
  }

  .content-wrapper {
    margin-left: 200px;
  }

  .nav-text {
    font-size: 0.85rem;
  }

  .top-navbar {
    padding: 12px 16px;
  }

  .username {
    display: none;
  }

  .logout-button {
    padding: 8px 12px;
  }

  .logout-text::before {
    content: '🚪';
    font-size: 1.2rem;
  }
}

@media (max-width: 640px) {
  .sidebar {
    width: 60px;
  }

  .content-wrapper {
    margin-left: 60px;
  }

  .sidebar-header {
    padding: 16px 12px;
  }

  .logo {
    font-size: 1rem;
  }

  .nav-text {
    display: none;
  }

  .nav-link {
    justify-content: center;
    padding: 12px 8px;
  }

  .nav-icon {
    font-size: 1.3rem;
  }

  .main-content {
    padding: 16px;
  }

  .top-navbar-right {
    gap: 12px;
  }

  .user-menu {
    padding-left: 12px;
  }

  .username {
    display: none;
  }
}
</style>
