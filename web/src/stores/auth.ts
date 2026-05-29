import { defineStore } from 'pinia'

import { getApiErrorMessage } from '../lib/apiError'
import { http } from '../lib/http'
import type { EnterpriseSpaceWithRole } from '../api/enterprise-space'

export type MembershipRole = 'space_admin' | 'member'

export interface User {
  id: number
  username: string
  email: string | null
  is_active: boolean
  is_admin: boolean
  is_bootstrap_admin?: boolean
}

export interface MembershipInfo {
  enterprise_space_id: number
  role: MembershipRole
  space: EnterpriseSpace
}

export interface EnterpriseSpace {
  id: number
  name: string
  slug: string
  description?: string
  role?: MembershipRole
}

export interface LoginParams {
  username: string
  password: string
}

export interface UserDetail extends User {
  memberships: MembershipInfo[]
  is_bootstrap_admin: boolean
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('auth_token') || '',
    user: null as UserDetail | null,
    enterpriseSpaces: [] as EnterpriseSpace[],
    currentSpaceSlug: localStorage.getItem('current_enterprise_space') || 'default',
    loading: false,
    error: '',
    initialized: false,
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
    currentUser: (state) => state.user,
    currentSpace: (state) => state.enterpriseSpaces.find((space) => space.slug === state.currentSpaceSlug) || null,
    hasAnySpace: (state) => state.enterpriseSpaces.length > 0,
    needsSpaceAssignment: (state) => !state.user?.is_admin && state.enterpriseSpaces.length === 0,
    isSystemAdmin: (state) => Boolean(state.user?.is_admin),
    isBootstrapAdmin: (state) => Boolean(state.user?.is_bootstrap_admin),
    currentSpaceRole: (state): MembershipRole | null => {
      const space = state.enterpriseSpaces.find((item) => item.slug === state.currentSpaceSlug)
      return space?.role ?? null
    },
    canManageSpaces: (state) => Boolean(state.user?.is_admin),
    canManageUsers: (state) => {
      if (state.user?.is_admin) return true
      const space = state.enterpriseSpaces.find((item) => item.slug === state.currentSpaceSlug)
      return space?.role === 'space_admin'
    },
    roleLabel: (state): string => {
      if (state.user?.is_admin) return '平台管理员'
      const space = state.enterpriseSpaces.find((item) => item.slug === state.currentSpaceSlug)
      if (space?.role === 'space_admin') return '空间管理员'
      return '企业成员'
    },
  },

  actions: {
    async init() {
      if (!this.token) {
        this.initialized = true
        return
      }
      try {
        await Promise.all([this.fetchUserInfo(), this.fetchEnterpriseSpaces()])
      } catch (error) {
        console.error('Failed to initialize auth state:', error)
        this.logout()
      } finally {
        this.initialized = true
      }
    },

    async login(params: LoginParams) {
      this.loading = true
      this.error = ''
      try {
        const { data } = await http.post<{ access_token: string; token_type: string }>('/auth/login', params)
        this.token = data.access_token
        localStorage.setItem('auth_token', data.access_token)
        this.initialized = false
        await Promise.all([this.fetchUserInfo(), this.fetchEnterpriseSpaces()])
        this.initialized = true
        return data
      } catch (error) {
        this.error = getApiErrorMessage(error, '登录失败')
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchUserInfo() {
      const { data } = await http.get<UserDetail>('/auth/me')
      this.user = data
      localStorage.setItem('current_user', JSON.stringify(data))
    },

    async fetchEnterpriseSpaces() {
      const { data } = await http.get<EnterpriseSpaceWithRole[]>('/enterprise-spaces')
      this.enterpriseSpaces = data.map((space) => ({
        id: space.id,
        name: space.name,
        slug: space.slug,
        description: space.description,
        role: space.role,
      }))
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
      this.initialized = true
      localStorage.removeItem('auth_token')
      localStorage.removeItem('current_user')
      localStorage.removeItem('current_enterprise_space')
    },

    postLoginRoute(): string {
      return this.needsSpaceAssignment ? '/no-space' : '/'
    },
  },
})
