<template>
  <button
    v-if="kbId && entityId"
    type="button"
    class="btn btn-ghost btn-row btn-row-compact view-in-graph-link"
    @click="goToGraph"
  >
    <AppIcon name="graph" :size="14" />
    在图谱中查看
  </button>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

import AppIcon from '../AppIcon.vue'
import { navigateToGraphEntity } from '../../lib/graphNavigation'

const props = defineProps<{
  kbId: number
  entityId: string
}>()

const router = useRouter()

function goToGraph() {
  navigateToGraphEntity(router, props.kbId, props.entityId)
}
</script>

<style scoped>
.view-in-graph-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
</style>
