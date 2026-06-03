<template>
  <div ref="rootEl" class="app-select" :class="{ 'app-select--open': open }">
    <span v-if="label" class="app-select-label">{{ label }}</span>
    <button
      type="button"
      class="app-select-trigger"
      :class="{ 'is-open': open }"
      :disabled="disabled"
      :aria-expanded="open"
      aria-haspopup="listbox"
      :aria-label="label || '选择'"
      @click.stop="toggleOpen"
    >
      <span class="app-select-value">{{ selectedLabel }}</span>
      <AppIcon name="chevron-down" class="app-select-arrow" :class="{ 'is-open': open }" :size="16" />
    </button>

    <div
      v-if="open"
      ref="panelEl"
      class="app-select-panel"
      :style="panelStyle"
      role="listbox"
      @pointerdown.stop
    >
      <button
        v-for="opt in options"
        :key="String(opt.value)"
        type="button"
        class="app-select-option"
        :class="{ 'is-active': opt.value === modelValue }"
        role="option"
        :aria-selected="opt.value === modelValue"
        @pointerdown.stop.prevent="selectOption(opt.value)"
      >
        <span class="app-select-option-text">{{ opt.label }}</span>
        <AppIcon v-if="opt.value === modelValue" name="check" :size="15" class="app-select-option-check" />
      </button>
      <div v-if="options.length === 0" class="app-select-empty">暂无选项</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import AppIcon from './AppIcon.vue'

export type AppSelectOption = {
  value: string
  label: string
}

const props = withDefaults(
  defineProps<{
    modelValue: string
    options: AppSelectOption[]
    label?: string
    disabled?: boolean
    placeholder?: string
  }>(),
  {
    label: '',
    disabled: false,
    placeholder: '请选择',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)
const panelEl = ref<HTMLElement | null>(null)
const panelStyle = ref<Record<string, string>>({})
let outsideListenerTimer: ReturnType<typeof setTimeout> | null = null

const selectedLabel = computed(() => {
  const match = props.options.find((opt) => opt.value === props.modelValue)
  return match?.label || props.placeholder
})

function updatePanelPosition() {
  const trigger = rootEl.value?.querySelector('.app-select-trigger') as HTMLElement | null
  if (!trigger) {
    return
  }
  const rect = trigger.getBoundingClientRect()
  panelStyle.value = {
    position: 'fixed',
    top: `${Math.round(rect.bottom + 6)}px`,
    left: `${Math.round(rect.left)}px`,
    minWidth: `${Math.round(rect.width)}px`,
    zIndex: '9999',
  }
}

function selectOption(value: string) {
  if (!open.value) {
    return
  }
  emit('update:modelValue', value)
  open.value = false
}

function toggleOpen() {
  if (props.disabled) {
    return
  }
  open.value = !open.value
}

function removeOutsideListeners() {
  if (outsideListenerTimer !== null) {
    clearTimeout(outsideListenerTimer)
    outsideListenerTimer = null
  }
  document.removeEventListener('click', onDocumentClick)
  window.removeEventListener('resize', onReposition)
  window.removeEventListener('scroll', onReposition, true)
}

function onDocumentClick(ev: MouseEvent) {
  if (!open.value) {
    return
  }
  const t = ev.target as Node | null
  if (t && (rootEl.value?.contains(t) || panelEl.value?.contains(t))) {
    return
  }
  open.value = false
}

function onReposition() {
  if (open.value) {
    updatePanelPosition()
  }
}

watch(open, (v) => {
  if (v) {
    void nextTick(() => {
      updatePanelPosition()
      outsideListenerTimer = setTimeout(() => {
        outsideListenerTimer = null
        document.addEventListener('click', onDocumentClick)
        window.addEventListener('resize', onReposition)
        window.addEventListener('scroll', onReposition, true)
      }, 0)
    })
  } else {
    removeOutsideListeners()
  }
})

onBeforeUnmount(() => {
  removeOutsideListeners()
})
</script>

<style scoped>
.app-select {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  position: relative;
}

.app-select-label {
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: 600;
  white-space: nowrap;
}

.app-select-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  height: 40px;
  padding: 0 12px 0 14px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.app-select-trigger:hover:not(:disabled) {
  border-color: var(--border-strong);
  background: var(--bg-secondary);
}

.app-select-trigger.is-open {
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 4px var(--brand-primary-light);
  background: var(--bg-secondary);
}

.app-select-trigger:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.app-select-value {
  flex: 1;
  min-width: 0;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-select-arrow {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform 0.2s ease;
}

.app-select-arrow.is-open {
  transform: rotate(180deg);
}

.app-select-panel {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px;
  max-height: min(320px, 60vh);
  overflow-y: auto;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.16);
  animation: app-select-pop 0.14s ease;
  pointer-events: auto;
}

@keyframes app-select-pop {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.app-select-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  padding: 9px 12px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-primary);
  font-size: 0.9rem;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.app-select-option:hover {
  background: var(--bg-tertiary);
}

.app-select-option.is-active {
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  font-weight: 600;
}

.app-select-option-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-select-option-check {
  flex-shrink: 0;
  color: var(--brand-primary);
}

.app-select-empty {
  padding: 14px 12px;
  text-align: center;
  font-size: 0.86rem;
  color: var(--text-tertiary);
}
</style>
