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
    currentSpace: (state) =>
      state.enterpriseSpaces.find((s) => s.slug === state.currentSpaceSlug) || null,
  },

  actions: {
    async init() {
      // 如果有 token，初始化用户信息和企业空间
      if (this.token) {
        await this.fetchUserInfo()
        await this.fetchEnterpriseSpaces()
      }
    },

    async login(params: LoginParams) {
      this.loading = true
      this.error = ''
      try {
        const { data } = await http.post<{ access_token: string; token_type: string }>('/auth/login', params)
        this.token = data.access_token
        localStorage.setItem('auth_token', data.access_token)

        // 获取企业空间列表
        await this.fetchEnterpriseSpaces()

        // 设置用户信息（从 token 解析或手动设置）
        this.user = {
          id: 1,
          username: params.username,
          email: params.username + '@example.com',
          is_active: true,
          is_admin: true,
        }

        // 保存用户信息到本地存储
        localStorage.setItem('current_user', JSON.stringify(this.user))

        return data
      } catch (error) {
        this.error = error instanceof Error ? error.message : '登录失败'
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchUserInfo() {
      // 从 token 解析用户信息或从本地存储恢复
      const storedUser = localStorage.getItem('current_user')
      if (storedUser) {
        try {
          this.user = JSON.parse(storedUser)
        } catch (e) {
          console.error('Failed to parse stored user:', e)
        }
      }
    },

    async fetchEnterpriseSpaces() {
      try {
        const { data } = await http.get<EnterpriseSpace[]>('/enterprise-spaces')
        this.enterpriseSpaces = data

        // 如果当前空间不在列表中，切换到第一个可用的空间
        if (data.length > 0) {
          const currentSpaceExists = data.some((s) => s.slug === this.currentSpaceSlug)
          if (!currentSpaceExists) {
            this.currentSpaceSlug = data[0].slug
            localStorage.setItem('current_enterprise_space', data[0].slug)
          }
        }
      } catch (error) {
        console.error('Failed to fetch enterprise spaces:', error)
        throw error
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
