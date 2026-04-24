<template>
  <Layout>
    <div class="page-shell settings-view">
      <PageHeader
        eyebrow="System Preferences"
        title="系统设置"
        description="统一管理主题偏好、工作台行为、高风险操作策略与系统环境信息，形成更稳定的企业级后台使用体验。"
      >
        <template #meta>
          <span class="chip chip-brand">平台配置中心</span>
          <span class="chip">{{ authStore.currentSpace?.name || '未选择空间' }}</span>
        </template>
      </PageHeader>

      <div class="page-grid settings-layout">
        <section class="surface-card">
          <div class="section-heading">
            <div>
              <h3>主题与界面</h3>
              <p>支持深色 / 浅色双主题，并保留统一的企业后台视觉语言。</p>
            </div>
          </div>

          <div class="theme-switcher segmented-control">
            <button
              class="segmented-button"
              :class="{ active: appStore.theme === 'light' }"
              type="button"
              @click="appStore.setTheme('light')"
            >
              浅色主题
            </button>
            <button
              class="segmented-button"
              :class="{ active: appStore.theme === 'dark' }"
              type="button"
              @click="appStore.setTheme('dark')"
            >
              深色主题
            </button>
          </div>

          <div class="theme-preview-grid">
            <div class="theme-preview-card light">
              <div class="theme-preview-header"></div>
              <div class="theme-preview-sidebar"></div>
              <div class="theme-preview-body">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
            <div class="theme-preview-card dark">
              <div class="theme-preview-header"></div>
              <div class="theme-preview-sidebar"></div>
              <div class="theme-preview-body">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </section>

        <section class="surface-card">
          <div class="section-heading">
            <div>
              <h3>工作台偏好</h3>
              <p>用于控制日常使用中的关键交互行为与默认开关。</p>
            </div>
          </div>

          <div class="data-list">
            <div class="data-row">
              <div class="data-row-label">
                <strong>紧凑模式导航</strong>
                <span>在较小屏幕上优先使用更高信息密度的导航布局。</span>
              </div>
              <label class="switch">
                <input v-model="preferences.compactMode" type="checkbox" />
              </label>
            </div>
            <div class="data-row">
              <div class="data-row-label">
                <strong>危险操作二次确认</strong>
                <span>删除知识库、Provider 等高风险操作时要求再次确认。</span>
              </div>
              <label class="switch">
                <input v-model="preferences.confirmDangerousAction" type="checkbox" />
              </label>
            </div>
            <div class="data-row">
              <div class="data-row-label">
                <strong>展示引用来源预览</strong>
                <span>在对话与检索页面优先显示命中来源，提升结果可信度。</span>
              </div>
              <label class="switch">
                <input v-model="preferences.showCitationPreview" type="checkbox" />
              </label>
            </div>
          </div>
        </section>

        <section class="surface-card">
          <div class="section-heading">
            <div>
              <h3>当前工作上下文</h3>
              <p>展示登录身份、企业空间与基础访问信息。</p>
            </div>
          </div>

          <div class="context-grid">
            <div class="context-card">
              <span class="context-icon">
                <AppIcon name="user" :size="18" />
              </span>
              <div>
                <strong>{{ authStore.currentUser?.username || '未登录用户' }}</strong>
                <p>{{ authStore.currentUser?.is_admin ? '平台管理员' : '企业成员' }}</p>
              </div>
            </div>
            <div class="context-card">
              <span class="context-icon">
                <AppIcon name="workspace" :size="18" />
              </span>
              <div>
                <strong>{{ authStore.currentSpace?.name || '未选择空间' }}</strong>
                <p>{{ authStore.enterpriseSpaces.length }} 个空间可切换</p>
              </div>
            </div>
            <div class="context-card">
              <span class="context-icon">
                <AppIcon name="server" :size="18" />
              </span>
              <div>
                <strong>{{ apiBaseUrl }}</strong>
                <p>当前 API 接入地址</p>
              </div>
            </div>
          </div>
        </section>

        <section class="surface-card">
          <div class="section-heading">
            <div>
              <h3>安全与治理建议</h3>
              <p>适合企业级后台场景的默认建议，可作为后续开发验收基线。</p>
            </div>
          </div>

          <div class="guideline-list">
            <div class="guideline-item">
              <AppIcon name="shield" :size="16" />
              <span>模型密钥与数据库连接信息应仅在受控表单中展示，并支持审计留痕。</span>
            </div>
            <div class="guideline-item">
              <AppIcon name="status" :size="16" />
              <span>知识库删除、Provider 删除与默认模型变更应具备二次确认与结果通知。</span>
            </div>
            <div class="guideline-item">
              <AppIcon name="spark" :size="16" />
              <span>主题、导航与密度策略应统一通过 design tokens 管理，避免分散硬编码。</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  </Layout>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import AppIcon from '../components/AppIcon.vue'
import Layout from '../components/Layout.vue'
import PageHeader from '../components/PageHeader.vue'
import { useAppStore } from '../stores/app'
import { useAuthStore } from '../stores/auth'

type WorkspacePreferences = {
  compactMode: boolean
  confirmDangerousAction: boolean
  showCitationPreview: boolean
}

const STORAGE_KEY = 'workspace_preferences'
const authStore = useAuthStore()
const appStore = useAppStore()
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const preferences = ref<WorkspacePreferences>({
  compactMode: false,
  confirmDangerousAction: true,
  showCitationPreview: true,
})

onMounted(() => {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (!stored) {
    return
  }

  try {
    preferences.value = {
      ...preferences.value,
      ...(JSON.parse(stored) as WorkspacePreferences),
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY)
  }
})

watch(
  preferences,
  (value) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
  },
  { deep: true },
)
</script>

<style scoped>
.settings-layout {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.theme-switcher {
  width: fit-content;
}

.theme-preview-grid,
.context-grid,
.guideline-list {
  display: grid;
  gap: 16px;
}

.theme-preview-grid,
.context-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 18px;
}

.theme-preview-card,
.context-card,
.guideline-item {
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: var(--bg-tertiary);
}

.theme-preview-card {
  position: relative;
  min-height: 180px;
  overflow: hidden;
  padding: 14px;
}

.theme-preview-header {
  height: 24px;
  border-radius: 999px;
  margin-bottom: 12px;
}

.theme-preview-sidebar {
  position: absolute;
  top: 54px;
  left: 14px;
  width: 56px;
  height: calc(100% - 68px);
  border-radius: 16px;
}

.theme-preview-body {
  margin-left: 72px;
  display: grid;
  gap: 12px;
}

.theme-preview-body span {
  display: block;
  height: 24px;
  border-radius: 12px;
}

.theme-preview-card.light {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}

.theme-preview-card.light .theme-preview-header,
.theme-preview-card.light .theme-preview-body span {
  background: rgba(37, 99, 235, 0.14);
}

.theme-preview-card.light .theme-preview-sidebar {
  background: #e2e8f0;
}

.theme-preview-card.dark {
  background: linear-gradient(180deg, #07111f 0%, #10213a 100%);
}

.theme-preview-card.dark .theme-preview-header,
.theme-preview-card.dark .theme-preview-body span {
  background: rgba(96, 165, 250, 0.16);
}

.theme-preview-card.dark .theme-preview-sidebar {
  background: rgba(15, 23, 42, 0.68);
}

.context-card,
.guideline-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px;
}

.context-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  flex-shrink: 0;
}

.context-card strong {
  color: var(--text-primary);
}

.context-card p,
.guideline-item span {
  margin: 6px 0 0;
  color: var(--text-secondary);
  line-height: 1.65;
}

@media (max-width: 1180px) {
  .settings-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .theme-preview-grid,
  .context-grid {
    grid-template-columns: 1fr;
  }
}
</style>
