<template>
  <RouterView :key="viewKey" />
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { useAuthStore } from './stores/auth'

const route = useRoute()
const authStore = useAuthStore()

/** 切换企业空间时 remount 当前页，触发各页 onMounted 重新拉取空间内数据 */
const viewKey = computed(() => `${String(route.name ?? route.path)}::${authStore.currentSpaceSlug}`)

onMounted(async () => {
  await authStore.init()
})
</script>
