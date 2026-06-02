<template>
  <div ref="rootEl" class="space-selector" :class="{ 'space-selector--open': open }">
    <div class="space-selector-prefix">
      <span class="space-selector-icon">
        <AppIcon name="workspace" :size="16" />
      </span>
      <div class="space-selector-copy">
        <span class="space-selector-label">企业空间</span>
      </div>
    </div>

    <div class="space-selector-control">
      <button
        type="button"
        class="space-select-trigger"
        :class="{ 'is-open': open }"
        :disabled="spaces.length <= 1"
        :aria-expanded="open"
        aria-haspopup="listbox"
        @click.stop="toggleOpen"
      >
        <span class="space-select-value">{{ selectedLabel }}</span>
        <AppIcon name="chevron-down" class="space-select-arrow" :class="{ 'is-open': open }" :size="16" />
      </button>

      <Teleport to="body">
        <div
          v-if="open"
          ref="panelEl"
          class="space-select-panel"
          :style="panelStyle"
          role="listbox"
          @click.stop
        >
          <button
            v-for="space in spaces"
            :key="space.id"
            type="button"
            class="space-select-option"
            :class="{ 'is-active': space.slug === modelValue }"
            role="option"
            :aria-selected="space.slug === modelValue"
            @click="selectSpace(space.slug)"
          >
            <span class="space-select-option-text">{{ space.name }}</span>
            <AppIcon v-if="space.slug === modelValue" name="check" :size="15" class="space-select-option-check" />
          </button>
          <div v-if="spaces.length === 0" class="space-select-empty">暂无可用空间</div>
        </div>
      </Teleport>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import type { EnterpriseSpace } from '../stores/auth'
import AppIcon from './AppIcon.vue'

const props = defineProps<{
  modelValue: string
  spaces: EnterpriseSpace[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)
const panelEl = ref<HTMLElement | null>(null)
const panelStyle = ref<Record<string, string>>({})

const selectedLabel = computed(() => {
  const match = props.spaces.find((s) => s.slug === props.modelValue)
  return match?.name || (props.spaces.length === 0 ? '暂无可用空间' : '选择空间')
})

function updatePanelPosition() {
  const trigger = rootEl.value?.querySelector('.space-select-trigger') as HTMLElement | null
  if (!trigger) {
    return
  }
  const rect = trigger.getBoundingClientRect()
  panelStyle.value = {
    position: 'fixed',
    top: `${Math.round(rect.bottom + 6)}px`,
    left: `${Math.round(rect.left)}px`,
    minWidth: `${Math.round(rect.width)}px`,
    zIndex: '1200',
  }
}

function selectSpace(slug: string) {
  if (slug !== props.modelValue) {
    emit('update:modelValue', slug)
  }
  open.value = false
}

function toggleOpen() {
  if (props.spaces.length <= 1) {
    return
  }
  open.value = !open.value
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
      document.addEventListener('click', onDocumentClick)
      window.addEventListener('resize', onReposition)
      window.addEventListener('scroll', onReposition, true)
    })
  } else {
    document.removeEventListener('click', onDocumentClick)
    window.removeEventListener('resize', onReposition)
    window.removeEventListener('scroll', onReposition, true)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  window.removeEventListener('resize', onReposition)
  window.removeEventListener('scroll', onReposition, true)
})
</script>

<style scoped>
.space-selector {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding: 8px 12px;
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

.space-selector-label {
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: 600;
  white-space: nowrap;
}

.space-selector-control {
  position: relative;
  margin-left: auto;
  flex-shrink: 0;
}

.space-select-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 148px;
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

.space-select-trigger:hover:not(:disabled) {
  border-color: var(--border-strong);
  background: var(--bg-secondary);
}

.space-select-trigger.is-open {
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 4px var(--brand-primary-light);
  background: var(--bg-secondary);
}

.space-select-trigger:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.space-select-value {
  flex: 1;
  min-width: 0;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.space-select-arrow {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform 0.2s ease;
}

.space-select-arrow.is-open {
  transform: rotate(180deg);
}

@media (max-width: 960px) {
  .space-selector {
    min-width: 100%;
  }

  .space-selector-control,
  .space-select-trigger {
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

/* 浮层 Teleport 到 body；Vue scoped 会为模板元素注入 data-v，故 scoped 仍命中 */
.space-select-panel {
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
  animation: space-select-pop 0.14s ease;
}

@keyframes space-select-pop {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.space-select-option {
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

.space-select-option:hover {
  background: var(--bg-tertiary);
}

.space-select-option.is-active {
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  font-weight: 600;
}

.space-select-option-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.space-select-option-check {
  flex-shrink: 0;
  color: var(--brand-primary);
}

.space-select-empty {
  padding: 14px 12px;
  text-align: center;
  font-size: 0.86rem;
  color: var(--text-tertiary);
}
</style>
