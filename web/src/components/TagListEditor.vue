<template>
  <div class="tag-list-editor">
    <div class="tag-list-editor-head">
      <span class="tag-list-editor-label">{{ label }}</span>
      <button
        v-if="help"
        class="tag-list-editor-help"
        type="button"
        :title="help"
        :aria-label="help"
      >
        ?
      </button>
    </div>
    <div class="tag-list-editor-tags">
      <span v-for="(item, index) in modelValue" :key="`${item}-${index}`" class="tag-list-editor-tag">
        <span>{{ item }}</span>
        <button type="button" class="tag-list-editor-remove" aria-label="删除" @click="removeAt(index)">×</button>
      </span>
      <button
        v-if="modelValue.length < maxItems"
        class="tag-list-editor-add"
        type="button"
        @click="showInput = true"
      >
        {{ addLabel }}
      </button>
    </div>
    <div v-if="showInput" class="tag-list-editor-input-row">
      <input
        ref="inputRef"
        v-model="draft"
        class="input tag-list-editor-input"
        type="text"
        :placeholder="placeholder"
        @keydown.enter.prevent="commitDraft"
        @keydown.esc.prevent="cancelInput"
      />
      <button class="btn btn-primary btn-row-compact" type="button" @click="commitDraft">添加</button>
      <button class="btn btn-ghost btn-row-compact" type="button" @click="cancelInput">取消</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    label: string
    placeholder?: string
    addLabel?: string
    help?: string
    maxItems?: number
  }>(),
  {
    placeholder: '',
    addLabel: '+ 添加',
    help: '',
    maxItems: 12,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const showInput = ref(false)
const draft = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

watch(showInput, async (visible) => {
  if (visible) {
    await nextTick()
    inputRef.value?.focus()
  }
})

function removeAt(index: number) {
  const next = props.modelValue.filter((_, i) => i !== index)
  emit('update:modelValue', next)
}

function commitDraft() {
  const value = draft.value.trim()
  if (!value) {
    return
  }
  if (props.modelValue.includes(value)) {
    draft.value = ''
    return
  }
  if (props.modelValue.length >= props.maxItems) {
    return
  }
  emit('update:modelValue', [...props.modelValue, value])
  draft.value = ''
  showInput.value = false
}

function cancelInput() {
  draft.value = ''
  showInput.value = false
}
</script>

<style scoped>
.tag-list-editor {
  display: grid;
  gap: 8px;
}

.tag-list-editor-head {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tag-list-editor-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.tag-list-editor-help {
  width: 18px;
  height: 18px;
  padding: 0;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--bg-primary);
  color: var(--text-tertiary);
  font-size: 0.72rem;
  line-height: 1;
  cursor: help;
}

.tag-list-editor-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-list-editor-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  font-size: 0.82rem;
  color: var(--text-primary);
}

.tag-list-editor-remove {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0 2px;
}

.tag-list-editor-remove:hover {
  color: var(--danger-color, #dc2626);
}

.tag-list-editor-add {
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px dashed color-mix(in srgb, var(--border-color) 80%, var(--brand-primary));
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.82rem;
  cursor: pointer;
}

.tag-list-editor-add:hover {
  border-color: var(--brand-primary);
  color: var(--brand-primary);
}

.tag-list-editor-input-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.tag-list-editor-input {
  flex: 1;
  min-width: 160px;
}
</style>
