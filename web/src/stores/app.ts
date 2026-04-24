import { defineStore } from 'pinia'

import { http } from '../lib/http'

type ThemeMode = 'light' | 'dark'

type HealthResponse = {
  status: string
  database: string
}

const getStoredTheme = (): ThemeMode => {
  const storedTheme = localStorage.getItem('theme')
  if (storedTheme === 'light' || storedTheme === 'dark') {
    return storedTheme
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useAppStore = defineStore('app', {
  state: () => ({
    health: null as HealthResponse | null,
    loading: false,
    error: '' as string,
    theme: getStoredTheme(),
    sidebarCollapsed: localStorage.getItem('sidebar_collapsed') === 'true',
  }),
  getters: {
    isDark: (state) => state.theme === 'dark',
  },
  actions: {
    applyTheme() {
      document.documentElement.setAttribute('data-theme', this.theme)
    },
    setTheme(theme: ThemeMode) {
      this.theme = theme
      localStorage.setItem('theme', theme)
      this.applyTheme()
    },
    toggleTheme() {
      this.setTheme(this.theme === 'light' ? 'dark' : 'light')
    },
    initTheme() {
      this.theme = getStoredTheme()
      this.applyTheme()
    },
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
      localStorage.setItem('sidebar_collapsed', String(this.sidebarCollapsed))
    },
    async fetchHealth() {
      this.loading = true
      this.error = ''
      try {
        const { data } = await http.get<HealthResponse>('/health')
        this.health = data
      } catch (error) {
        this.error = error instanceof Error ? error.message : '后端请求失败'
      } finally {
        this.loading = false
      }
    },
  },
})
