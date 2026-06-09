import { watch, type WatchStopHandle } from 'vue'

import { useAuthStore } from '../stores/auth'

type EnterpriseSpaceChangeOptions = {
  /** 同步回调（如切换空间后立即跳转），避免 remount 前先渲染错误上下文 */
  flush?: 'pre' | 'post' | 'sync'
  /** 为 true 时首次赋值也触发（默认跳过，与 onMounted 分工） */
  immediate?: boolean
}

/**
 * 企业空间切换回调（默认跳过首次赋值，避免与 onMounted 重复加载）。
 */
export function useEnterpriseSpaceChange(
  onSpaceChange: (slug: string, previousSlug: string | undefined) => void | Promise<void>,
  options?: EnterpriseSpaceChangeOptions,
): WatchStopHandle {
  const authStore = useAuthStore()
  let ready = options?.immediate ?? false

  return watch(
    () => authStore.currentSpaceSlug,
    (slug, previousSlug) => {
      if (!ready) {
        ready = true
        if (!options?.immediate) {
          return
        }
      }
      if (slug === previousSlug) {
        return
      }
      void onSpaceChange(slug, previousSlug)
    },
    { flush: options?.flush ?? 'post' },
  )
}
