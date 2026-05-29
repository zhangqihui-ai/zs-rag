export function resolveApiBaseUrl(): string {
  const env = import.meta.env.VITE_API_BASE_URL?.trim()
  if (env) return env.replace(/\/$/, '')
  if (typeof window !== 'undefined') return window.location.origin
  return 'http://localhost:8000'
}
