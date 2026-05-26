<template>
  <div class="space-selector">
    <div class="space-selector-prefix">
      <span class="space-selector-icon">
        <AppIcon name="workspace" :size="16" />
      </span>
      <div class="space-selector-copy">
        <span class="space-selector-label">企业空间</span>
        <strong>{{ selectedSpace?.name || '未配置空间' }}</strong>
      </div>
    </div>

    <div class="space-selector-control">
      <select
        :value="modelValue"
        class="space-select"
        :disabled="spaces.length <= 1"
        @change="handleChange"
      >
        <option v-if="spaces.length === 0" value="">暂无可用空间</option>
        <option v-for="space in spaces" :key="space.id" :value="space.slug">
          {{ space.name }}
        </option>
      </select>
      <AppIcon name="chevron-down" class="space-select-arrow" :size="16" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { EnterpriseSpace } from '../stores/auth'
import AppIcon from './AppIcon.vue'

const props = defineProps<{
  modelValue: string
  spaces: EnterpriseSpace[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const selectedSpace = computed(() => props.spaces.find((space) => space.slug === props.modelValue) || null)

const handleChange = (event: Event) => {
  const target = event.target as HTMLSelectElement
  emit('update:modelValue', target.value)
}
</script>

<style scoped>
.space-selector {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 260px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-secondary);
  box-shadow: var(--card-shadow-xs);
}

.space-selector-prefix {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.space-selector-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  flex-shrink: 0;
}

.space-selector-copy {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.space-selector-copy strong {
  color: var(--text-primary);
  font-size: 0.92rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.space-selector-label {
  color: var(--text-tertiary);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.space-selector-control {
  position: relative;
  margin-left: auto;
  flex-shrink: 0;
}

.space-select {
  min-width: 148px;
  height: 40px;
  padding: 0 36px 0 14px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  appearance: none;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.space-select:hover:not(:disabled) {
  border-color: var(--border-strong);
}

.space-select:focus {
  outline: none;
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 4px var(--brand-primary-light);
  background: var(--bg-secondary);
}

.space-select:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.space-select-arrow {
  position: absolute;
  top: 50%;
  right: 12px;
  transform: translateY(-50%);
  color: var(--text-tertiary);
  pointer-events: none;
}

@media (max-width: 960px) {
  .space-selector {
    min-width: 100%;
  }

  .space-selector-control,
  .space-select {
    width: 100%;
  }
}

@media (max-width: 640px) {
  .space-selector {
    flex-direction: column;
    align-items: stretch;
  }

  .space-selector-control {
    margin-left: 0;
  }
}
</style>
