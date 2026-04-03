<template>
  <RouterView />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()

onMounted(async () => {
  // 初始化用户信息和企业空间
  await authStore.init()
})
</script>

<style scoped>
/* Shell styles removed - now handled by Layout component */
</style>
