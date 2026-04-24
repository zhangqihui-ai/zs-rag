<template>
  <div class="rerank-picker">
    <div class="custom-select-wrap">
      <select
        v-if="!loading"
        class="custom-select"
        :value="modelValue ?? ''"
        @change="onChange(($event.target as HTMLSelectElement).value)"
      >
        <option value="">
          {{ defaultModel ? `默认（${defaultModel.model_name}）` : '请选择 Rerank 模型' }}
        </option>
        <option v-for="model in models" :key="model.id" :value="model.id">
          {{ model.model_name }}（{{ model.provider_name }}）
        </option>
      </select>
      <span v-else class="rerank-picker-loading">加载中…</span>
      <span class="custom-select-arrow">
        <AppIcon name="chevron-down" :size="14" />
      </span>
    </div>
    <p v-if="!loading && models.length === 0" class="rerank-picker-empty">
      未发现可用的 Rerank 模型，请前往「模型管理」启用对应模型。
    </p>
  </div>
</template>

<script setup lang="ts">
import AppIcon from '../AppIcon.vue'
import type { DefaultModelOption, ModelItem } from '../../api/model-management'

defineProps<{
  modelValue: number | null
  models: ModelItem[]
  loading: boolean
  defaultModel: DefaultModelOption | null
}>()

const emit = defineEmits<{ (e: 'update:modelValue', value: number | null): void }>()

function onChange(raw: string) {
  if (!raw) {
    emit('update:modelValue', null)
    return
  }
  const id = Number(raw)
  emit('update:modelValue', Number.isFinite(id) ? id : null)
}
</script>

<style scoped>
.rerank-picker {
  display: grid;
  gap: 6px;
}

.custom-select-wrap {
  position: relative;
  width: 100%;
}

.custom-select {
  width: 100%;
  height: 40px;
  padding: 0 36px 0 14px;
  appearance: none;
  -webkit-appearance: none;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-size: 0.9rem;
  cursor: pointer;
}

.custom-select:hover,
.custom-select:focus {
  outline: none;
  border-color: var(--brand-primary);
  background: var(--bg-secondary);
}

.custom-select:focus {
  box-shadow: 0 0 0 3px var(--brand-primary-light);
}

.custom-select-arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--text-tertiary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.rerank-picker-loading {
  display: flex;
  align-items: center;
  min-height: 40px;
  padding: 0 14px;
  color: var(--text-tertiary);
  font-size: 0.9rem;
  border: 1px dashed var(--border-color);
  border-radius: 12px;
  background: var(--bg-tertiary);
}

.rerank-picker-empty {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-tertiary);
}
</style>
