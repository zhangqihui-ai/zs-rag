<template>
  <div class="graph-entity-result-actions">
    <slot />
    <ViewInGraphLink v-if="entityId" :kb-id="kbId" :entity-id="entityId" />
  </div>
</template>

<script setup lang="ts">
import ViewInGraphLink from './ViewInGraphLink.vue'

/** 图检索结果行操作区：展示「在图谱中查看」等按钮。 */
defineProps<{
  kbId: number
  entityId: string
}>()
</script>

<style scoped>
.graph-entity-result-actions {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
</style>
