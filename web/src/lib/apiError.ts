import axios from 'axios'

export function getApiErrorMessage(error: unknown, fallback = '请求失败'): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined
    const message = data?.message ?? data?.detail
    if (typeof message === 'string' && message.trim()) {
      return message.trim()
    }
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}
