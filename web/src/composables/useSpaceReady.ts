import { onBeforeUnmount, onMounted } from 'vue'

import { useAuthStore } from '../stores/auth'

/** Wait until auth + enterprise space context is ready (deduped across router/App). */
export async function waitForSpaceContextReady(): Promise<void> {
  const authStore = useAuthStore()
  await authStore.ensureInitialized()
}

export function useSpaceReadyLoader(callback: () => void | Promise<void>) {
  let cancelled = false

  onMounted(() => {
    void (async () => {
      try {
        await waitForSpaceContextReady()
        if (cancelled) {
          return
        }
        await callback()
      } catch (error) {
        if (!cancelled) {
          console.error('useSpaceReadyLoader failed', error)
        }
      }
    })()
  })

  onBeforeUnmount(() => {
    cancelled = true
  })
}
