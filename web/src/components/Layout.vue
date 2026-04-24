<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': appStore.sidebarCollapsed }">
    <aside class="app-sidebar">
      <div class="sidebar-brand">
        <div class="brand-content">
          <div class="brand-mark">
            <AppIcon name="brand" :size="22" />
          </div>
          <div class="brand-copy">
            <strong>ZS-RAG</strong>
            <span>Enterprise Knowledge Platform</span>
          </div>
        </div>
        <button class="sidebar-toggle" type="button" title="折叠导航" @click="appStore.toggleSidebar()">
          <AppIcon name="panel" :size="18" />
        </button>
      </div>

      <div class="sidebar-section">
        <p class="sidebar-caption">平台导航</p>
        <nav class="sidebar-nav">
          <router-link v-for="item in navItems" :key="item.to" :to="item.to" class="nav-link">
            <span class="nav-icon">
              <AppIcon :name="item.icon" :size="18" />
            </span>
            <span class="nav-copy">
              <strong>{{ item.label }}</strong>
              <small>{{ item.caption }}</small>
            </span>
          </router-link>
        </nav>
      </div>

      <div class="sidebar-footer">
        <div class="space-spotlight">
          <span class="space-spotlight-dot"></span>
          <div class="space-spotlight-copy">
            <strong>{{ authStore.currentSpace?.name || '未选择企业空间' }}</strong>
            <span>{{ authStore.enterpriseSpaces.length }} 个空间可切换</span>
          </div>
        </div>
      </div>
    </aside>

    <div class="app-main">
      <header class="app-header">
        <div class="app-header-main">
          <div class="app-breadcrumb">
            <template v-for="(item, index) in breadcrumbs" :key="`${item.label}-${index}`">
              <router-link v-if="item.to" class="app-breadcrumb-link" :to="item.to">{{ item.label }}</router-link>
              <span v-else class="app-breadcrumb-current">{{ item.label }}</span>
              <span v-if="index < breadcrumbs.length - 1" class="app-breadcrumb-separator">/</span>
            </template>
          </div>
          <div class="app-title-group">
            <h1>{{ currentPage.title }}</h1>
            <p>{{ currentPage.description }}</p>
          </div>
        </div>

        <div class="app-header-actions">
          <SpaceSelector v-model="currentSpaceSlug" :spaces="authStore.enterpriseSpaces" />

          <button
            class="icon-button theme-button"
            type="button"
            :title="appStore.isDark ? '切换到浅色模式' : '切换到深色模式'"
            @click="appStore.toggleTheme()"
          >
            <AppIcon :name="appStore.isDark ? 'sun' : 'moon'" :size="18" />
          </button>

          <div class="header-user-card">
            <div class="header-user-avatar">
              {{ userInitial }}
            </div>
            <div class="header-user-copy">
              <strong>{{ authStore.currentUser?.username || '未登录用户' }}</strong>
              <span>{{ authStore.currentUser?.is_admin ? '平台管理员' : '企业成员' }}</span>
            </div>
          </div>

          <button class="btn btn-secondary logout-button" type="button" @click="handleLogout">
            <AppIcon name="logout" :size="16" />
            <span>退出登录</span>
          </button>
        </div>
      </header>

      <main class="app-content">
        <div class="app-content-inner">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAppStore } from '../stores/app'
import { useAuthStore } from '../stores/auth'
import AppIcon from './AppIcon.vue'
import SpaceSelector from './SpaceSelector.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const navItems = [
  { to: '/', label: '首页仪表盘', caption: '平台概览', icon: 'dashboard' },
  { to: '/knowledge-bases', label: '知识库管理', caption: '资产配置', icon: 'knowledge' },
  { to: '/retrieval', label: '知识检索', caption: '效果验证', icon: 'retrieval' },
  { to: '/chat', label: '对话', caption: '知识助手', icon: 'chat' },
  { to: '/providers', label: '模型管理', caption: '模型供给', icon: 'models' },
  { to: '/settings', label: '系统设置', caption: '平台策略', icon: 'settings' },
] as const

const currentSpaceSlug = computed({
  get: () => authStore.currentSpaceSlug,
  set: (slug: string) => authStore.switchSpace(slug),
})

const currentPage = computed(() => ({
  title: (route.meta.title as string) || navItems.find((item) => item.to === route.path)?.label || '工作台',
  description: (route.meta.description as string) || '管理企业知识资产与 AI 模型配置。',
}))

const breadcrumbs = computed(() => {
  const items: Array<{ label: string; to?: string }> = [{ label: 'ZS-RAG', to: '/' }]

  if (route.name === 'knowledge-base-detail') {
    items.push({ label: '知识库管理', to: '/knowledge-bases' })
    items.push({ label: '知识库详情' })
    return items
  }

  items.push({ label: currentPage.value.title })
  return items
})

const userInitial = computed(() => (authStore.currentUser?.username || 'U').charAt(0).toUpperCase())
const spaceWatchReady = ref(false)

watch(
  () => authStore.currentSpaceSlug,
  (value, oldValue) => {
    if (!spaceWatchReady.value) {
      spaceWatchReady.value = true
      return
    }

    if (value && oldValue && value !== oldValue) {
      router.go(0)
    }
  },
)

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
}

.app-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 30;
  width: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 18px 16px 16px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--sidebar-border);
  backdrop-filter: blur(24px);
  transition: width 0.24s ease, padding 0.24s ease;
}

.sidebar-brand,
.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.brand-content {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--brand-primary) 0%, var(--brand-secondary) 100%);
  color: #ffffff;
  box-shadow: 0 14px 30px rgba(37, 99, 235, 0.25);
  flex-shrink: 0;
}

.brand-copy {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.brand-copy strong {
  font-size: 1rem;
  color: var(--text-primary);
}

.brand-copy span {
  color: var(--text-tertiary);
  font-size: 0.74rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

.sidebar-toggle:hover {
  border-color: var(--border-strong);
  color: var(--text-primary);
}

.sidebar-section {
  display: grid;
  gap: 14px;
  min-height: 0;
}

.sidebar-caption {
  margin: 0;
  padding: 0 8px;
  color: var(--text-tertiary);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.sidebar-nav {
  display: grid;
  gap: 8px;
}

.nav-link {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 14px 14px 12px;
  border: 1px solid transparent;
  border-radius: 18px;
  color: var(--sidebar-text);
  transition: transform 0.2s ease, background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}

.nav-link::before {
  content: '';
  position: absolute;
  left: 0;
  top: 14px;
  bottom: 14px;
  width: 3px;
  border-radius: 999px;
  background: transparent;
}

.nav-link:hover {
  transform: translateX(2px);
  border-color: var(--sidebar-border);
  background: var(--sidebar-bg-hover);
  color: var(--sidebar-text-hover);
}

.nav-link.router-link-active {
  border-color: var(--sidebar-border);
  background: var(--sidebar-bg-active);
  color: var(--sidebar-text-active);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.nav-link.router-link-active::before {
  background: var(--brand-primary);
}

.nav-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.04);
  flex-shrink: 0;
}

.nav-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.nav-copy strong {
  font-size: 0.92rem;
  color: currentColor;
}

.nav-copy small {
  color: var(--text-tertiary);
  font-size: 0.76rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-footer {
  margin-top: auto;
  padding: 14px;
  border: 1px solid var(--sidebar-border);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
}

.space-spotlight {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.space-spotlight-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--success-color);
  box-shadow: 0 0 0 6px rgba(22, 163, 74, 0.12);
  flex-shrink: 0;
}

.space-spotlight-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.space-spotlight-copy strong {
  color: var(--text-primary);
  font-size: 0.88rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.space-spotlight-copy span {
  color: var(--text-tertiary);
  font-size: 0.78rem;
}

.app-main {
  flex: 1;
  min-height: 100vh;
  margin-left: var(--sidebar-width);
  transition: margin-left 0.24s ease;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  min-height: var(--header-height);
  padding: 18px 32px;
  background: var(--header-bg);
  backdrop-filter: blur(24px);
  border-bottom: 1px solid var(--header-border);
}

.app-header-main {
  display: grid;
  gap: 10px;
}

.app-breadcrumb {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-tertiary);
  font-size: 0.82rem;
  font-weight: 600;
}

.app-breadcrumb-link,
.app-breadcrumb-current {
  line-height: 1;
}

.app-breadcrumb-link {
  color: var(--text-secondary);
  transition: color 0.2s ease;
}

.app-breadcrumb-link:hover {
  color: var(--brand-primary);
}

.app-breadcrumb-current {
  color: var(--text-primary);
}

.app-breadcrumb-separator {
  opacity: 0.6;
}

.app-title-group {
  display: grid;
  gap: 6px;
}

.app-title-group h1 {
  margin: 0;
  font-size: clamp(1.4rem, 2vw, 1.9rem);
  color: var(--text-primary);
}

.app-title-group p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.95rem;
}

.app-header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  margin-left: auto;
}

.theme-button {
  flex-shrink: 0;
}

.header-user-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-secondary);
  box-shadow: var(--card-shadow-xs);
}

.header-user-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--brand-primary) 0%, var(--brand-secondary) 100%);
  color: #ffffff;
  font-weight: 700;
  flex-shrink: 0;
}

.header-user-copy {
  display: grid;
  gap: 3px;
}

.header-user-copy strong {
  color: var(--text-primary);
  font-size: 0.92rem;
}

.header-user-copy span {
  color: var(--text-tertiary);
  font-size: 0.76rem;
}

.logout-button {
  flex-shrink: 0;
}

.app-content {
  padding: 30px 32px 40px;
}

.app-content-inner {
  max-width: var(--content-max-width);
  margin: 0 auto;
}

.app-layout.sidebar-collapsed .app-sidebar {
  width: var(--sidebar-collapsed-width);
  padding-inline: 12px;
}

.app-layout.sidebar-collapsed .app-main {
  margin-left: var(--sidebar-collapsed-width);
}

.app-layout.sidebar-collapsed .brand-copy,
.app-layout.sidebar-collapsed .sidebar-caption,
.app-layout.sidebar-collapsed .nav-copy,
.app-layout.sidebar-collapsed .space-spotlight-copy {
  opacity: 0;
  width: 0;
  overflow: hidden;
  pointer-events: none;
}

.app-layout.sidebar-collapsed .sidebar-brand,
.app-layout.sidebar-collapsed .sidebar-footer {
  justify-content: center;
}

.app-layout.sidebar-collapsed .nav-link {
  justify-content: center;
  padding-inline: 10px;
}

.app-layout.sidebar-collapsed .nav-link::before {
  top: 10px;
  bottom: 10px;
}

@media (max-width: 1360px) {
  .app-header {
    flex-direction: column;
    align-items: stretch;
  }

  .app-header-actions {
    margin-left: 0;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}

@media (max-width: 1080px) {
  .app-sidebar {
    width: 96px;
    padding-inline: 12px;
  }

  .app-main {
    margin-left: 96px;
  }

  .brand-copy,
  .sidebar-caption,
  .nav-copy,
  .space-spotlight-copy {
    opacity: 0;
    width: 0;
    overflow: hidden;
    pointer-events: none;
  }

  .sidebar-brand,
  .sidebar-footer,
  .nav-link {
    justify-content: center;
  }
}

@media (max-width: 720px) {
  .app-header,
  .app-content {
    padding-inline: 18px;
  }

  .app-header-actions {
    gap: 10px;
  }

  .header-user-copy,
  .logout-button span {
    display: none;
  }

  .logout-button {
    width: 42px;
    padding-inline: 0;
    justify-content: center;
  }
}
</style>
