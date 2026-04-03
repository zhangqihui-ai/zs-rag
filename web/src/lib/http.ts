import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const http = axios.create({
  baseURL,
  timeout: 30000,
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
