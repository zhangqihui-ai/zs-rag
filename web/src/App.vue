<template>
  <RouterView :key="viewKey" />
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { useAuthStore } from './stores/auth'

const route = useRoute()
const authStore = useAuthStore()

/**
 * 切换企业空间时 remount 当前页，触发各页 onMounted 重新拉取空间内数据。
 * 初始化完成前不把空间写入 key，避免鉴权尚未就绪时因 slug 校正触发重复挂载、打断列表请求。
 */
const viewKey = computed(() => {
  const routePart = String(route.name ?? route.path)
  if (!authStore.initialized) {
    return routePart
  }
  return `${routePart}::${authStore.currentSpaceSlug}`
})

onMounted(async () => {
  await authStore.ensureInitialized()
})
</script>
