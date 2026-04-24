declare module '*.vue' {
  import type { DefineComponent } from 'vue'

  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  /** 普通请求超时（毫秒），默认 30000 */
  readonly VITE_HTTP_TIMEOUT_MS?: string
  /** 上传/重建索引等长请求超时（毫秒），默认 900000（15 分钟） */
  readonly VITE_LONG_REQUEST_TIMEOUT_MS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
