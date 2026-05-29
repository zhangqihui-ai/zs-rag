import axios from 'axios'
import { resolveApiBaseUrl } from './apiBaseUrl'

const baseURL = resolveApiBaseUrl()

/** 普通 API 请求（默认 30s） */
const defaultTimeoutMs = Number(import.meta.env.VITE_HTTP_TIMEOUT_MS) || 30_000

/**
 * 文档上传 / 重建索引等长耗时请求（后端同步完成解析、分块、向量与 Milvus 写入）
 * 可通过 VITE_LONG_REQUEST_TIMEOUT_MS 覆盖，默认 15 分钟
 */
export const longRequestTimeoutMs = Number(import.meta.env.VITE_LONG_REQUEST_TIMEOUT_MS) || 900_000

/** 知识库详情页文档列表/元数据等（解析进行中后端可能繁忙，避免 30s 误报） */
export const documentRequestTimeoutMs =
  Number(import.meta.env.VITE_DOCUMENT_REQUEST_TIMEOUT_MS) || longRequestTimeoutMs

export const http = axios.create({
  baseURL,
  timeout: defaultTimeoutMs,
})

// 请求拦截器 - 添加认证 Token 和企业空间上下文
http.interceptors.request.use((config) => {
  // 从 localStorage 获取 token
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  // 从 localStorage 获取当前企业空间
  const enterpriseSpace = localStorage.getItem('current_enterprise_space')
  if (enterpriseSpace && !config.headers['X-Enterprise-Space']) {
    config.headers['X-Enterprise-Space'] = enterpriseSpace
  }

  return config
})

function isLoginRequest(url: string | undefined): boolean {
  if (!url) return false
  return url.includes('/auth/login')
}

// 响应拦截器 - 统一错误处理
http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const requestUrl = error.config?.url ?? ''
      const onLoginPage =
        typeof window !== 'undefined' && window.location.pathname === '/login'

      // 登录失败或未建立会话的 401：留在登录页展示错误，勿清 token / 硬跳转
      if (isLoginRequest(requestUrl) || onLoginPage) {
        return Promise.reject(error)
      }

      // Token 过期，清除本地存储并跳转到登录页（iframe 内跳转会破坏嵌入体验，交由页面自行展示错误）
      localStorage.removeItem('auth_token')
      localStorage.removeItem('current_user')
      let inIframe = false
      try {
        inIframe = window.self !== window.top
      } catch {
        inIframe = true
      }
      if (!inIframe) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)
