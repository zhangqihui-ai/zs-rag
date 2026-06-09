<template>
  <div class="llm-picker">
    <div class="custom-select-wrap">
      <select
        v-if="!loading"
        class="custom-select"
        :value="modelValue ?? ''"
        :disabled="disabled"
        @change="onChange(($event.target as HTMLSelectElement).value)"
      >
        <option value="">
          默认{{ defaultModel ? `（${defaultModel.model_name}）` : '' }}
        </option>
        <optgroup
          v-for="group in sortedGroups"
          :key="group.provider_id"
          :label="group.provider_name"
        >
          <option v-for="model in group.models" :key="model.id" :value="model.id">
            {{ model.model_name }}
          </option>
        </optgroup>
      </select>
      <span v-else class="llm-picker-loading">加载中…</span>
      <span class="custom-select-arrow">
        <AppIcon name="chevron-down" :size="14" />
      </span>
    </div>
    <p v-if="showCurrentHint && currentLabel" class="llm-picker-current">当前: {{ currentLabel }}</p>
    <p v-if="!loading && models.length === 0 && !defaultModel" class="llm-picker-empty">
      未发现可用的 LLM，请前往「模型管理」启用对应模型并配置默认 LLM。
    </p>
    <p v-else-if="hint" class="llm-picker-hint">{{ hint }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { DefaultModelOption, ModelItem } from '../../api/model-management'
import AppIcon from '../AppIcon.vue'

const props = withDefaults(
  defineProps<{
    modelValue: number | null
    models: ModelItem[]
    loading: boolean
    defaultModel: DefaultModelOption | null
    disabled?: boolean
    showCurrentHint?: boolean
    hint?: string
  }>(),
  {
    disabled: false,
    showCurrentHint: true,
    hint: '',
  },
)

const emit = defineEmits<{ (e: 'update:modelValue', value: number | null): void }>()

const sortedGroups = computed(() => {
  const byProvider = new Map<number, { provider_id: number; provider_name: string; models: ModelItem[] }>()
  for (const model of props.models) {
    const existing = byProvider.get(model.provider_id)
    if (existing) {
      existing.models.push(model)
      continue
    }
    byProvider.set(model.provider_id, {
      provider_id: model.provider_id,
      provider_name: model.provider_name,
      models: [model],
    })
  }
  return [...byProvider.values()]
    .map((group) => ({
      ...group,
      models: [...group.models].sort((a, b) => a.model_name.localeCompare(b.model_name, 'zh-CN')),
    }))
    .sort((a, b) => a.provider_name.localeCompare(b.provider_name, 'zh-CN'))
})

const currentLabel = computed(() => {
  if (props.modelValue != null) {
    const picked = props.models.find((model) => model.id === props.modelValue)
    if (picked) {
      return `${picked.model_name}（${picked.provider_name}）`
    }
  }
  if (props.defaultModel) {
    return `${props.defaultModel.model_name}（${props.defaultModel.provider_name}）`
  }
  return ''
})

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
.llm-picker {
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
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.custom-select:hover:not(:disabled) {
  border-color: var(--brand-primary);
  background: var(--bg-secondary);
}

.custom-select:focus {
  outline: none;
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 3px var(--brand-primary-light);
  background: var(--bg-secondary);
}

.custom-select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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

.custom-select:focus + .custom-select-arrow {
  color: var(--brand-primary);
}

.llm-picker-loading {
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

.llm-picker-current,
.llm-picker-hint,
.llm-picker-empty {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.llm-picker-empty {
  color: var(--text-tertiary);
}

.custom-select :deep(optgroup) {
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-secondary);
}

.custom-select :deep(option) {
  font-weight: 400;
  color: var(--text-primary);
}
</style>
