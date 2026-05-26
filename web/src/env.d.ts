/// <reference types="vite/client" />

declare module '*?url' {
  const src: string
  export default src
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'

  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}

// 扩展 vue-router 的 RouteMeta（须 import 以免覆盖 vue-router 原有导出）
import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    /** 允许未携带 token 访问（如登录页、嵌入入口） */
    public?: boolean
    title?: string
    description?: string
    noSpaceAllowed?: boolean
    requiresSystemAdmin?: boolean
    requiresSpaceAdmin?: boolean
  }
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_HTTP_TIMEOUT_MS?: string
  readonly VITE_LONG_REQUEST_TIMEOUT_MS?: string
  readonly VITE_DOCUMENT_REQUEST_TIMEOUT_MS?: string
  readonly VITE_FILE_DOWNLOAD_TIMEOUT_MS?: string
  readonly VITE_PDF_PARSE_TIMEOUT_MS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
