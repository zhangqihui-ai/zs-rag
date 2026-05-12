<template>
  <div ref="rowRef" class="srv-root">
    <div
      ref="scrollElRef"
      class="srv-scroll scrollbar-pill"
      :class="scrollClass"
      @scroll.passive="onInnerScroll"
    >
      <div ref="contentRef" class="srv-scroll-content">
        <slot />
      </div>
    </div>
    <div
      v-show="trackVisible"
      class="srv-vslider"
      role="scrollbar"
      aria-label="纵向滚动"
      aria-orientation="vertical"
      :aria-valuenow="ariaPercent"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div ref="trackRef" class="srv-vslider-track" @mousedown="onTrackMouseDown">
        <div
          class="srv-vslider-thumb"
          :style="thumbStyle"
          @mousedown.stop="onThumbMouseDown"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 为 true 时轨道始终显示；无溢出时拇指铺满轨道（仍可点轨道，滚动不变） */
    alwaysShow?: boolean
    /** 传给内层滚动容器的额外 class */
    scrollClass?: string | string[] | Record<string, boolean>
  }>(),
  { alwaysShow: true },
)

const emit = defineEmits<{
  scroll: [e: Event]
}>()

/** 与 syncThumb 一致：小于约 1 设备像素的可滚高度仍视为可交互（否则拇指/轨道 mousedown 被错误忽略） */
const SCROLL_RANGE_EPS = 0.25

const MIN_THUMB_H = 36
/** 拇指在轨道上至少能移动的行程（px）；否则按比例算出的拇指会“撑满”轨道、几乎拖不动 */
const MIN_THUMB_TRAVEL_PX = 36
const TRACK_INNER_PAD = 6

const rowRef = ref<HTMLElement | null>(null)
const scrollElRef = ref<HTMLElement | null>(null)
const contentRef = ref<HTMLElement | null>(null)
const trackRef = ref<HTMLElement | null>(null)

const thumbTop = ref(0)
const thumbH = ref(40)

const thumbStyle = computed(() => ({
  height: `${thumbH.value}px`,
  top: `${thumbTop.value}px`,
}))

const trackVisible = computed(() => props.alwaysShow || hasOverflow.value)

const hasOverflow = ref(false)

const ariaPercent = computed(() => {
  const el = scrollElRef.value
  if (!el) {
    return 0
  }
  const range = Math.max(el.scrollHeight - el.clientHeight, 1e-6)
  return Math.round((el.scrollTop / range) * 100)
})

function syncThumb() {
  const el = scrollElRef.value
  const track = trackRef.value
  if (!el || !track) {
    return
  }
  const { scrollTop, scrollHeight, clientHeight } = el
  hasOverflow.value = scrollHeight - clientHeight > SCROLL_RANGE_EPS
  const trackH = track.clientHeight
  if (trackH < 8) {
    return
  }

  if (!hasOverflow.value) {
    if (props.alwaysShow) {
      thumbH.value = Math.max(48, trackH - 8)
      thumbTop.value = 4
    }
    return
  }

  const range = Math.max(scrollHeight - clientHeight, 1e-6)
  const inner = Math.max(0, trackH - TRACK_INNER_PAD)
  const thProp = (clientHeight / Math.max(scrollHeight, 1)) * trackH
  const thUncapped = Math.max(MIN_THUMB_H, Math.min(inner, thProp))
  const thMax = Math.max(MIN_THUMB_H, inner - MIN_THUMB_TRAVEL_PX)
  const th = Math.min(thUncapped, thMax)
  const maxThumbTop = Math.max(0, trackH - th)
  const top = (scrollTop / range) * maxThumbTop
  thumbH.value = th
  thumbTop.value = top
}

function onInnerScroll(e: Event) {
  syncThumb()
  emit('scroll', e)
}

let thumbDrag: {
  startY: number
  startScroll: number
  maxScroll: number
  trackH: number
  thumbH: number
} | null = null

function onThumbMove(e: MouseEvent) {
  if (!thumbDrag || !scrollElRef.value) {
    return
  }
  const { startY, startScroll, maxScroll, trackH, thumbH } = thumbDrag
  const avail = Math.max(1, trackH - thumbH)
  const dy = e.clientY - startY
  const next = Math.min(maxScroll, Math.max(0, startScroll + (dy / avail) * maxScroll))
  scrollElRef.value.scrollTop = next
  syncThumb()
}

function onThumbUp() {
  window.removeEventListener('mousemove', onThumbMove)
  thumbDrag = null
}

function onThumbMouseDown(e: MouseEvent) {
  e.preventDefault()
  const el = scrollElRef.value
  const track = trackRef.value
  if (!el || !track) {
    return
  }
  const rawRange = el.scrollHeight - el.clientHeight
  if (rawRange <= SCROLL_RANGE_EPS) {
    return
  }
  const maxScroll = Math.max(rawRange, 1e-6)
  thumbDrag = {
    startY: e.clientY,
    startScroll: el.scrollTop,
    maxScroll,
    trackH: Math.max(track.clientHeight, 1),
    thumbH: thumbH.value,
  }
  window.addEventListener('mousemove', onThumbMove, { passive: false })
  window.addEventListener('mouseup', onThumbUp, { once: true })
}

function onTrackMouseDown(e: MouseEvent) {
  e.preventDefault()
  if ((e.target as HTMLElement).classList.contains('srv-vslider-thumb')) {
    return
  }
  const el = scrollElRef.value
  const track = trackRef.value
  if (!el || !track) {
    return
  }
  const rawRange = el.scrollHeight - el.clientHeight
  if (rawRange <= SCROLL_RANGE_EPS) {
    return
  }
  const maxScroll = Math.max(rawRange, 1e-6)
  const rect = track.getBoundingClientRect()
  const th = thumbH.value
  const trackH = Math.max(rect.height, 1)
  const y = e.clientY - rect.top
  const maxThumbTop = Math.max(0, trackH - th)
  const thumbTopClamped = Math.min(maxThumbTop, Math.max(0, y - th / 2))
  const ratio = maxThumbTop < 1e-6 ? 0 : thumbTopClamped / maxThumbTop
  el.scrollTop = ratio * maxScroll
  syncThumb()
}

defineExpose({
  getScrollEl: () => scrollElRef.value,
  syncThumb,
  getRowEl: () => rowRef.value,
})

let resizeObserver: ResizeObserver | null = null
let mutationObserver: MutationObserver | null = null

onMounted(() => {
  void nextTick(() => {
    syncThumb()
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => syncThumb())
      const el = scrollElRef.value
      const tr = trackRef.value
      const cr = contentRef.value
      if (el) {
        resizeObserver.observe(el)
      }
      if (tr) {
        resizeObserver.observe(tr)
      }
      if (cr) {
        resizeObserver.observe(cr)
      }
    }
    
    if (typeof MutationObserver !== 'undefined' && contentRef.value) {
      mutationObserver = new MutationObserver(() => syncThumb())
      mutationObserver.observe(contentRef.value, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true,
        attributeFilter: ['style', 'class']
      })
    }
  })
})

onUnmounted(() => {
  onThumbUp()
  resizeObserver?.disconnect()
  resizeObserver = null
  mutationObserver?.disconnect()
  mutationObserver = null
})

</script>

<style scoped>
.srv-root {
  position: relative;
  z-index: 0;
  flex: 1;
  min-width: 0;
  min-height: 0;
  width: 100%;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 8px;
}

.srv-scroll {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow-x: auto;
  overflow-y: scroll;
  box-sizing: border-box;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.srv-scroll::-webkit-scrollbar {
  display: none;
}

.srv-scroll-content {
  min-height: 100%;
  display: flex;
  flex-direction: column;
}

.srv-vslider {
  position: relative;
  z-index: 2;
  flex-shrink: 0;
  align-self: stretch;
  width: 14px;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 2px 0 4px;
  user-select: none;
  pointer-events: auto;
  opacity: 1;
}

.srv-vslider-track {
  flex: 1;
  min-height: 48px;
  position: relative;
  width: 10px;
  margin: 0 auto;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.22);
  cursor: pointer;
  pointer-events: auto;
}

.srv-vslider-thumb {
  position: absolute;
  left: 0;
  right: 0;
  width: 10px;
  margin: 0 auto;
  border-radius: 999px;
  background: #aeb8c6;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12);
  cursor: grab;
  box-sizing: border-box;
  min-height: 36px;
  pointer-events: auto;
}

.srv-vslider-thumb:active {
  cursor: grabbing;
  background: #8b95a8;
}
</style>
