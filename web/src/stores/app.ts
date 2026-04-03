import { defineStore } from 'pinia'

import { http } from '../lib/http'

type HealthResponse = {
  status: string
  database: string
}

export const useAppStore = defineStore('app', {
  state: () => ({
    health: null as HealthResponse | null,
    loading: false,
    error: '' as string,
  }),
  actions: {
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
