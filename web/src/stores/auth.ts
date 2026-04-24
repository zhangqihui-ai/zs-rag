import { defineStore } from 'pinia'

import { http } from '../lib/http'

export interface User {
  id: number
  username: string
  email: string
  is_active: boolean
  is_admin: boolean
}

export interface LoginParams {
  username: string
  password: string
}

export interface EnterpriseSpace {
  id: number
  name: string
  slug: string
  description?: string
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('auth_token') || '',
    user: null as User | null,
    enterpriseSpaces: [] as EnterpriseSpace[],
    currentSpaceSlug: localStorage.getItem('current_enterprise_space') || 'default',
    loading: false,
    error: '',
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
    currentUser: (state) => state.user,
    currentSpace: (state) => state.enterpriseSpaces.find((space) => space.slug === state.currentSpaceSlug) || null,
  },

  actions: {
    async init() {
      if (!this.token) {
        return
      }
      try {
        await Promise.all([this.fetchUserInfo(), this.fetchEnterpriseSpaces()])
      } catch (error) {
        console.error('Failed to initialize auth state:', error)
        this.logout()
      }
    },

    async login(params: LoginParams) {
      this.loading = true
      this.error = ''
      try {
        const { data } = await http.post<{ access_token: string; token_type: string }>('/auth/login', params)
        this.token = data.access_token
        localStorage.setItem('auth_token', data.access_token)
        await Promise.all([this.fetchUserInfo(), this.fetchEnterpriseSpaces()])
        return data
      } catch (error) {
        this.error = error instanceof Error ? error.message : '登录失败'
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchUserInfo() {
      const { data } = await http.get<User>('/auth/me')
      this.user = data
      localStorage.setItem('current_user', JSON.stringify(data))
    },

    async fetchEnterpriseSpaces() {
      const { data } = await http.get<EnterpriseSpace[]>('/enterprise-spaces')
      this.enterpriseSpaces = data
      if (data.length > 0) {
        const currentSpaceExists = data.some((space) => space.slug === this.currentSpaceSlug)
        if (!currentSpaceExists) {
          this.currentSpaceSlug = data[0].slug
          localStorage.setItem('current_enterprise_space', data[0].slug)
        }
      }
    },

    switchSpace(spaceSlug: string) {
      this.currentSpaceSlug = spaceSlug
      localStorage.setItem('current_enterprise_space', spaceSlug)
    },

    logout() {
      this.token = ''
      this.user = null
      this.enterpriseSpaces = []
      this.currentSpaceSlug = 'default'
      localStorage.removeItem('auth_token')
      localStorage.removeItem('current_user')
      localStorage.removeItem('current_enterprise_space')
    },
  },
})
