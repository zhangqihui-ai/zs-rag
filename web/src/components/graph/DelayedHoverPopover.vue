<template>
  <span
    ref="anchorRef"
    class="delayed-hover-anchor"
    :class="{ 'delayed-hover-anchor--disabled': disabled }"
    @mouseenter="onEnter"
    @mouseleave="onLeave"
    @focusin="onEnter"
    @focusout="onLeave"
  >
    <slot />
  </span>
  <Teleport to="body">
    <div
      v-if="visible && !disabled"
      ref="popoverRef"
      class="delayed-hover-popover"
      :style="popoverStyle"
      role="tooltip"
    >
      <slot name="content" />
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, type CSSProperties } from 'vue'

const props = withDefaults(
  defineProps<{
    delayMs?: number
    disabled?: boolean
  }>(),
  {
    delayMs: 700,
    disabled: false,
  },
)

const anchorRef = ref<HTMLElement | null>(null)
const popoverRef = ref<HTMLElement | null>(null)
const visible = ref(false)
const popoverStyle = ref<CSSProperties>({})

let showTimer: ReturnType<typeof setTimeout> | null = null
let hideTimer: ReturnType<typeof setTimeout> | null = null

function clearShowTimer() {
  if (showTimer) {
    clearTimeout(showTimer)
    showTimer = null
  }
}

function clearHideTimer() {
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

async function updatePosition() {
  await nextTick()
  const anchor = anchorRef.value
  const popover = popoverRef.value
  if (!anchor || !popover) {
    return
  }
  const rect = anchor.getBoundingClientRect()
  const popRect = popover.getBoundingClientRect()
  const margin = 8
  let top = rect.bottom + margin
  let left = rect.left

  if (top + popRect.height > window.innerHeight - margin) {
    top = Math.max(margin, rect.top - popRect.height - margin)
  }
  if (left + popRect.width > window.innerWidth - margin) {
    left = Math.max(margin, window.innerWidth - popRect.width - margin)
  }

  popoverStyle.value = {
    top: `${top}px`,
    left: `${left}px`,
  }
}

function onEnter() {
  if (props.disabled) {
    return
  }
  clearHideTimer()
  if (visible.value) {
    return
  }
  clearShowTimer()
  showTimer = setTimeout(() => {
    visible.value = true
    void updatePosition()
  }, props.delayMs)
}

function onLeave() {
  clearShowTimer()
  clearHideTimer()
  hideTimer = setTimeout(() => {
    visible.value = false
  }, 80)
}

onBeforeUnmount(() => {
  clearShowTimer()
  clearHideTimer()
})
</script>

<style scoped>
.delayed-hover-anchor {
  display: inline-flex;
  max-width: 100%;
  cursor: help;
}

.delayed-hover-anchor--disabled {
  cursor: default;
}
</style>

<style>
.delayed-hover-popover {
  position: fixed;
  z-index: 2000;
  max-width: min(360px, calc(100vw - 24px));
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.96);
  color: #fff;
  font-size: 0.82rem;
  line-height: 1.65;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.28);
  pointer-events: none;
  word-break: break-word;
}

.delayed-hover-popover .popover-title {
  margin: 0 0 6px;
  font-size: 0.9rem;
  font-weight: 600;
  color: #f8fafc;
}

.delayed-hover-popover .popover-desc {
  margin: 0;
  color: #e2e8f0;
}

.delayed-hover-popover .popover-sub {
  margin: 8px 0 0;
  font-size: 0.75rem;
  color: #94a3b8;
}
</style>
