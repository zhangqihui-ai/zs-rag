<template>
  <DelayedHoverPopover v-if="type" :delay-ms="700">
    <span class="graph-type-chip" :style="{ '--type-color': color }">
      <span class="graph-type-dot"></span>
      <span>{{ type }}</span>
    </span>
    <template #content>
      <p class="popover-title">{{ meta.labelZh }}</p>
      <p class="popover-desc">{{ meta.description }}</p>
      <p v-if="showEnglishHint" class="popover-sub">英文标签：{{ type }}</p>
    </template>
  </DelayedHoverPopover>
  <span v-else>—</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { colorForEntityType } from '../../lib/graphEntityColors'
import { getEntityTypeMeta } from '../../lib/graphEntityTypeMeta'
import DelayedHoverPopover from './DelayedHoverPopover.vue'

const props = defineProps<{
  type: string
}>()

const color = computed(() => colorForEntityType(props.type))
const meta = computed(() => getEntityTypeMeta(props.type))
const showEnglishHint = computed(() => meta.value.labelZh.toLowerCase() !== props.type.trim().toLowerCase())
</script>

<style scoped>
.graph-type-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 9px 2px 7px;
  border-radius: 999px;
  font-size: 0.78rem;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--type-color) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--type-color) 32%, transparent);
  white-space: nowrap;
  cursor: help;
}

.graph-type-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--type-color, #94a3b8);
  flex-shrink: 0;
}
</style>
