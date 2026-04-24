import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/** 普通 API 请求（默认 30s） */
const defaultTimeoutMs = Number(import.meta.env.VITE_HTTP_TIMEOUT_MS) || 30_000

/**
 * 文档上传 / 重建索引等长耗时请求（后端同步完成解析、分块、向量与 Milvus 写入）
 * 可通过 VITE_LONG_REQUEST_TIMEOUT_MS 覆盖，默认 15 分钟
 */
export const longRequestTimeoutMs = Number(import.meta.env.VITE_LONG_REQUEST_TIMEOUT_MS) || 900_000

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
  if (enterpriseSpace) {
    config.headers['X-Enterprise-Space'] = enterpriseSpace
  }

  return config
})

// 响应拦截器 - 统一错误处理
http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token 过期，清除本地存储并跳转到登录页
      localStorage.removeItem('auth_token')
      localStorage.removeItem('current_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
