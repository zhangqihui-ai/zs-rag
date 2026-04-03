<template>
  <div class="space-selector">
    <label class="label">企业空间</label>
    <select
      :value="modelValue"
      @input="handleChange"
      class="select"
    >
      <option
        v-for="space in spaces"
        :key="space.id"
        :value="space.slug"
      >
        {{ space.name }}
      </option>
    </select>
  </div>
</template>

<script setup lang="ts">
import type { EnterpriseSpace } from '../stores/auth'

defineProps<{
  modelValue: string
  spaces: EnterpriseSpace[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const handleChange = (event: Event) => {
  const target = event.target as HTMLSelectElement
  emit('update:modelValue', target.value)
}
</script>

<style scoped>
.space-selector {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.label {
  font-size: 0.75rem;
  color: #64748b;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.select {
  padding: 8px 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  color: #e2e8f0;
  font-size: 0.9rem;
  cursor: pointer;
  width: 100%;
  transition: all 0.2s;
}

.select:focus {
  outline: none;
  border-color: #7dd3fc;
  background: rgba(255, 255, 255, 0.08);
}

.select option {
  background: #1e293b;
  color: #e2e8f0;
}

.select:hover {
  border-color: rgba(124, 211, 252, 0.3);
}
</style>
