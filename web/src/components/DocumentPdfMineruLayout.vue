<template>
  <div class="pdf-mineru-layout">
    <div v-if="loading" class="pdf-mineru-loading">正在加载 PDF…</div>
    <div v-else-if="error" class="status-box error">{{ error }}</div>
    <template v-else>
      <div class="pdf-mineru-toolbar">
        <button type="button" class="btn btn-ghost btn-row-compact" :disabled="pageNum <= 1" @click="goPage(pageNum - 1)">
          上一页
        </button>
        <span class="pdf-mineru-page-label">{{ pageNum }}–{{ displayedEnd }} / {{ numPages }}</span>
        <button
          type="button"
          class="btn btn-ghost btn-row-compact"
          :disabled="pageNum >= numPages"
          @click="goPage(pageNum + 1)"
        >
          下一页
        </button>
        <span class="pdf-mineru-hint">多页连续预览；点击色块联动右侧；滚轮滑到区域底/顶翻页</span>
      </div>
      <ScrollRowWithVSlider
        ref="scrollRowSliderRef"
        scroll-class="pdf-mineru-scroll-wrap"
        @scroll="onPdfScrollAreaScroll"
      >
        <div class="pdf-mineru-pages">
          <section
            v-for="p in displayedPageRange"
            :key="'slab-' + p"
            class="pdf-mineru-page-slab"
            :data-pdf-page="p"
          >
            <div class="pdf-mineru-page-badge">第 {{ p }} 页</div>
            <div class="pdf-mineru-slab-stack">
              <canvas :data-pdf-canvas-page="p" class="pdf-mineru-canvas" />
              <div
                class="pdf-mineru-overlay"
                :style="{
                  width: (pageViewport[p]?.w || 0) + 'px',
                  height: (pageViewport[p]?.h || 0) + 'px',
                }"
              >
                <button
                  v-for="box in boxesForPage(p)"
                  :key="'box-' + p + '-' + box.index"
                  type="button"
                  class="pdf-mineru-box"
                  :class="{
                    active: modelValue === box.index,
                    'citation-focus': citationFocusIndex === box.index,
                    'chunk-range': chunkIndexSet.has(box.index),
                  }"
                  :style="box.style"
                  :data-mineru-block-index="box.index"
                  :title="'块 #' + (box.index + 1)"
                  @click="onBoxClick(box.index)"
                />
              </div>
            </div>
          </section>
        </div>
      </ScrollRowWithVSlider>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'

import { getKnowledgeBaseErrorMessage, knowledgeBaseApi } from '../api/knowledge-base'
import { pdfjs, setupPdfjsWorker } from '../lib/setupPdfjsWorker'
import ScrollRowWithVSlider from './ScrollRowWithVSlider.vue'
import {
  mineruContentExtent,
  mineruPageBox,
  shouldShowMineruBlock,
  type MineruContentItem,
} from '../lib/mineruContentDisplay'

setupPdfjsWorker()

/** 单次连续渲染的页数（从当前「起始页」向下） */
const PAGE_STACK = 5

const props = defineProps<{
  kbId: number
  documentId: number
  items: MineruContentItem[]
  modelValue: number | null
  /** 引文跳转时的强调高亮（可与 modelValue 同时存在） */
  citationFocusIndex?: number | null
  /** 切片对应的全部版面块索引：整段框选 */
  chunkIndices?: number[] | null
}>()

const chunkIndexSet = computed(() => new Set(props.chunkIndices ?? []))

const emit = defineEmits<{
  'update:modelValue': [value: number | null]
  'page-change': [page: number]
  ready: [numPages: number]
}>()

const loading = ref(true)
const error = ref('')
const numPages = ref(0)
const pageNum = ref(1)
const pdfDoc = shallowRef<pdfjs.PDFDocumentProxy | null>(null)
const scrollRowSliderRef = ref<{
  getScrollEl: () => HTMLElement | null
  getRowEl: () => HTMLElement | null
  syncThumb: () => void
} | null>(null)

const pageViewport = ref<Record<number, { w: number; h: number }>>({})
/** PDF 真实页高/页宽（baseHeight / baseWidth），文本层不可用时的兜底映射 */
const pdfAspectHW = ref<number | null>(null)
/**
 * 各页 PDF 文本层在 canvas 像素坐标下的实际文本区域包络。
 * 用于把 MinerU bbox 按轴线性对齐到真实版面（无需假设纵横比/页边距）。
 */
type TextExtent = { minX: number; maxX: number; minY: number; maxY: number }
const pageTextExtent = ref<Record<number, TextExtent>>({})

/** 全文 bbox 内容包络（文本层兜底时使用） */
const contentExtent = computed(() => mineruContentExtent(props.items))

/** 某页 MinerU shown 块在 MinerU 坐标系下的包络 */
function mineruExtentForPage(p0: number): TextExtent | null {
  let minX = Number.POSITIVE_INFINITY
  let minY = Number.POSITIVE_INFINITY
  let maxX = Number.NEGATIVE_INFINITY
  let maxY = Number.NEGATIVE_INFINITY
  for (const it of props.items) {
    if (Number(it.page_idx) !== p0 || !shouldShowMineruBlock(it as MineruContentItem)) {
      continue
    }
    const b = it.bbox
    if (!Array.isArray(b) || b.length < 4) {
      continue
    }
    const x0 = Number(b[0])
    const y0 = Number(b[1])
    const x1 = Number(b[2])
    const y1 = Number(b[3])
    if (![x0, y0, x1, y1].every(Number.isFinite)) {
      continue
    }
    minX = Math.min(minX, x0)
    minY = Math.min(minY, y0)
    maxX = Math.max(maxX, x1)
    maxY = Math.max(maxY, y1)
  }
  if (maxX > minX && maxY > minY) {
    return { minX, maxX, minY, maxY }
  }
  return null
}

async function captureTextExtent(
  page: pdfjs.PDFPageProxy,
  viewport: pdfjs.PageViewport,
  p: number,
): Promise<void> {
  try {
    const tc = await page.getTextContent()
    let minX = Number.POSITIVE_INFINITY
    let minY = Number.POSITIVE_INFINITY
    let maxX = Number.NEGATIVE_INFINITY
    let maxY = Number.NEGATIVE_INFINITY
    for (const raw of tc.items) {
      const item = raw as { str?: string; width?: number; transform?: number[] }
      if (!item.str || !item.str.trim() || !Array.isArray(item.transform)) {
        continue
      }
      const m = pdfjs.Util.transform(viewport.transform, item.transform)
      const baselineX = m[4]
      const baselineY = m[5]
      const fontH = Math.hypot(m[2], m[3])
      const w = (Number(item.width) || 0) * viewport.scale
      const left = baselineX
      const right = baselineX + w
      const top = baselineY - fontH
      const bottom = baselineY
      if (![left, right, top, bottom].every(Number.isFinite)) {
        continue
      }
      minX = Math.min(minX, left)
      maxX = Math.max(maxX, right)
      minY = Math.min(minY, top)
      maxY = Math.max(maxY, bottom)
    }
    if (maxX - minX > 1 && maxY - minY > 1) {
      pageTextExtent.value = { ...pageTextExtent.value, [p]: { minX, maxX, minY, maxY } }
    }
  } catch {
    // 扫描件等无文本层：保持空，boxesForPage 走兜底映射
  }
}

let resizeObserver: ResizeObserver | null = null
let resizeDebounceTimer: ReturnType<typeof setTimeout> | null = null

let stackWheelTarget: HTMLElement | null = null
let stackWheelHandler: ((e: WheelEvent) => void) | null = null

let lastEmittedPdfPage = 1
/** 避免快速切换文档时旧请求先结束把 loading 置 false 或覆盖新文档状态 */
let loadGeneration = 0

function getStackEl(): HTMLElement | null {
  return scrollRowSliderRef.value?.getScrollEl() ?? null
}

function queryCanvasForPage(root: HTMLElement, p: number): HTMLCanvasElement | null {
  return root.querySelector(`canvas[data-pdf-canvas-page="${p}"]`)
}

const displayedPageRange = computed(() => {
  const n = numPages.value
  if (n < 1) {
    return [] as number[]
  }
  const start = pageNum.value
  const end = Math.min(n, start + PAGE_STACK - 1)
  const r: number[] = []
  for (let p = start; p <= end; p++) {
    r.push(p)
  }
  return r
})

const displayedEnd = computed(() => {
  const r = displayedPageRange.value
  return r.length ? r[r.length - 1] : pageNum.value
})

function boxesForPage(p: number): { index: number; style: Record<string, string> }[] {
  if (!pdfDoc.value || !props.items.length) {
    return []
  }
  const p0 = p - 1
  const dim = pageViewport.value[p]
  if (!dim || dim.w <= 0 || dim.h <= 0) {
    return []
  }
  const vw = dim.w
  const vh = dim.h

  // 主路：用 PDF 文本层真实区域，把 MinerU 文本区域按轴线性对齐（最精确）
  const textExt = pageTextExtent.value[p]
  const mExt = mineruExtentForPage(p0)
  const useTextMap = !!textExt && !!mExt && textExt.maxX - textExt.minX > 1 && textExt.maxY - textExt.minY > 1
  const sx = useTextMap ? (textExt!.maxX - textExt!.minX) / (mExt!.maxX - mExt!.minX) : 0
  const sy = useTextMap ? (textExt!.maxY - textExt!.minY) / (mExt!.maxY - mExt!.minY) : 0

  // 兜底：无文本层（扫描件）时按 PDF 纵横比 + 内容包络推算页面尺寸
  const aspectHW = pdfAspectHW.value ?? dim.h / dim.w
  const { pageW, pageH } = mineruPageBox(contentExtent.value, aspectHW)

  const out: { index: number; style: Record<string, string> }[] = []
  props.items.forEach((it, index) => {
    if (!shouldShowMineruBlock(it as MineruContentItem)) {
      return
    }
    if (Number(it.page_idx) !== p0) {
      return
    }
    const b = it.bbox
    if (!Array.isArray(b) || b.length < 4) {
      return
    }
    const x0 = Number(b[0])
    const y0 = Number(b[1])
    const x1 = Number(b[2])
    const y1 = Number(b[3])
    if (![x0, y0, x1, y1].every(Number.isFinite)) {
      return
    }
    let left: number
    let top: number
    let w: number
    let h: number
    if (useTextMap) {
      left = textExt!.minX + (x0 - mExt!.minX) * sx
      top = textExt!.minY + (y0 - mExt!.minY) * sy
      w = (x1 - x0) * sx
      h = (y1 - y0) * sy
    } else {
      left = (x0 / pageW) * vw
      top = (y0 / pageH) * vh
      w = ((x1 - x0) / pageW) * vw
      h = ((y1 - y0) / pageH) * vh
    }
    if (w < 2 || h < 2) {
      return
    }
    out.push({
      index,
      style: {
        left: `${left}px`,
        top: `${top}px`,
        width: `${w}px`,
        height: `${h}px`,
      },
    })
  })
  return out
}

function onBoxClick(index: number) {
  emit('update:modelValue', props.modelValue === index ? null : index)
}

function detectDominantPdfPage(scrollRoot: HTMLElement): number | null {
  const cr = scrollRoot.getBoundingClientRect()
  const anchorY = cr.top + Math.min(120, cr.height * 0.22)
  let bestPage: number | null = null
  let bestDist = Number.POSITIVE_INFINITY
  scrollRoot.querySelectorAll<HTMLElement>('.pdf-mineru-page-slab[data-pdf-page]').forEach((node) => {
    const r = node.getBoundingClientRect()
    if (r.bottom <= cr.top + 2 || r.top >= cr.bottom - 2) {
      return
    }
    const raw = node.dataset.pdfPage
    const page = raw != null ? Number(raw) : NaN
    if (!Number.isFinite(page) || page < 1) {
      return
    }
    const mid = (r.top + r.bottom) / 2
    const dist = Math.abs(mid - anchorY)
    if (dist < bestDist) {
      bestDist = dist
      bestPage = page
    }
  })
  return bestPage
}

function onPdfScrollAreaScroll() {
  const el = getStackEl()
  if (!el) {
    return
  }
  const p = detectDominantPdfPage(el)
  if (p != null && p !== lastEmittedPdfPage) {
    lastEmittedPdfPage = p
    emit('page-change', p)
  }
}

async function scrollStackToTop() {
  await nextTick()
  const el = getStackEl()
  if (el) {
    el.scrollTop = 0
    scrollRowSliderRef.value?.syncThumb()
  }
}

async function scrollStackToBottom() {
  await nextTick()
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  const el = getStackEl()
  if (el) {
    el.scrollTop = Math.max(0, el.scrollHeight - el.clientHeight)
    scrollRowSliderRef.value?.syncThumb()
  }
}

const WHEEL_EDGE_PX = 6

async function handleStackWheel(e: WheelEvent) {
  const el = getStackEl()
  if (!el || numPages.value <= 1) {
    return
  }
  if (Math.abs(e.deltaY) < 1 && Math.abs(e.deltaX) >= Math.abs(e.deltaY)) {
    return
  }
  const { scrollTop, scrollHeight, clientHeight } = el
  const atBottom = scrollTop + clientHeight >= scrollHeight - WHEEL_EDGE_PX
  const atTop = scrollTop <= WHEEL_EDGE_PX
  const noOverflow = scrollHeight <= clientHeight + WHEEL_EDGE_PX

  if (e.deltaY > 0) {
    if ((noOverflow || atBottom) && pageNum.value < numPages.value) {
      e.preventDefault()
      pageNum.value = pageNum.value + 1
      await renderVisiblePages()
      await scrollStackToTop()
    }
  } else if (e.deltaY < 0) {
    if ((noOverflow || atTop) && pageNum.value > 1) {
      e.preventDefault()
      pageNum.value = pageNum.value - 1
      await renderVisiblePages()
      await scrollStackToBottom()
    }
  }
}

function teardownStackWheel() {
  if (stackWheelTarget && stackWheelHandler) {
    stackWheelTarget.removeEventListener('wheel', stackWheelHandler)
  }
  stackWheelTarget = null
  stackWheelHandler = null
}

function setupStackWheel() {
  teardownStackWheel()
  const el = getStackEl()
  if (!el) {
    return
  }
  stackWheelTarget = el
  stackWheelHandler = (e: WheelEvent) => {
    void handleStackWheel(e)
  }
  el.addEventListener('wheel', stackWheelHandler, { passive: false })
}

function teardownResizeObserver() {
  if (resizeDebounceTimer != null) {
    clearTimeout(resizeDebounceTimer)
    resizeDebounceTimer = null
  }
  resizeObserver?.disconnect()
  resizeObserver = null
  teardownStackWheel()
}

function setupResizeObserver() {
  teardownResizeObserver()
  const el = getStackEl()
  if (!el || typeof ResizeObserver === 'undefined') {
    return
  }
  resizeObserver = new ResizeObserver(() => {
    if (!pdfDoc.value) {
      return
    }
    if (resizeDebounceTimer != null) {
      clearTimeout(resizeDebounceTimer)
    }
    resizeDebounceTimer = setTimeout(() => {
      resizeDebounceTimer = null
      void (async () => {
        await renderVisiblePages()
      })()
    }, 120)
  })
  resizeObserver.observe(el)
}

async function goPage(n: number) {
  if (n < 1 || n > numPages.value) {
    return
  }
  pageNum.value = n
  await renderVisiblePages()
  await scrollStackToTop()
}

const FIT_PADDING_PX = 20
const SCALE_MIN = 0.15
const SCALE_MAX = 2.5

function computePageScale(page: pdfjs.PDFPageProxy, canvas: HTMLCanvasElement): number {
  const base = page.getViewport({ scale: 1 })
  const bw = Math.max(base.width || 1, 1)
  let cw = getStackEl()?.clientWidth ?? 0
  if (cw < 64) {
    cw = scrollRowSliderRef.value?.getRowEl()?.clientWidth ?? 0
  }
  if (cw < 64) {
    cw = canvas.closest('.pdf-mineru-pages')?.clientWidth ?? 0
  }
  if (cw < 64) {
    cw = canvas.parentElement?.clientWidth ?? 0
  }
  if (cw < 64) {
    cw = 720
  }
  const targetW = Math.max(64, cw - FIT_PADDING_PX * 2)
  const s = targetW / bw
  return Math.min(SCALE_MAX, Math.max(SCALE_MIN, s))
}

async function renderVisiblePages() {
  const doc = pdfDoc.value
  if (!doc) {
    return
  }
  const pages = displayedPageRange.value
  if (pages.length === 0) {
    return
  }
  for (let attempt = 0; attempt < 24; attempt++) {
    await nextTick()
    const root = getStackEl()
    if (!root) {
      continue
    }
    let all = true
    for (const p of pages) {
      if (!queryCanvasForPage(root, p)) {
        all = false
        break
      }
    }
    if (all) {
      break
    }
  }
  const root = getStackEl()
  if (!root) {
    return
  }
  for (const p of pages) {
    const canvas = queryCanvasForPage(root, p)
    if (!canvas) {
      continue
    }
    const page = await doc.getPage(p)
    const base = page.getViewport({ scale: 1 })
    if (base.width > 0 && base.height > 0) {
      pdfAspectHW.value = base.height / base.width
    }
    const scale = computePageScale(page, canvas)
    const viewport = page.getViewport({ scale })
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      continue
    }
    canvas.width = viewport.width
    canvas.height = viewport.height
    pageViewport.value = {
      ...pageViewport.value,
      [p]: { w: viewport.width, h: viewport.height },
    }
    await page.render({ canvasContext: ctx, viewport }).promise
    if (!pageTextExtent.value[p]) {
      await captureTextExtent(page, viewport, p)
    }
  }
  await nextTick()
  scrollRowSliderRef.value?.syncThumb()
}

async function loadPdf() {
  const gen = ++loadGeneration
  teardownResizeObserver()
  loading.value = true
  error.value = ''
  pdfDoc.value = null
  numPages.value = 0
  pageViewport.value = {}
  pdfAspectHW.value = null
  pageTextExtent.value = {}
  try {
    const blob = await knowledgeBaseApi.fetchDocumentFileBlob(props.kbId, props.documentId)
    if (gen !== loadGeneration) {
      return
    }
    const buf = await blob.arrayBuffer()
    if (gen !== loadGeneration) {
      return
    }
    const pdfParseMs = Number(import.meta.env.VITE_PDF_PARSE_TIMEOUT_MS) || 120_000
    const task = pdfjs.getDocument({ data: buf })
    const doc = await Promise.race([
      task.promise,
      new Promise<pdfjs.PDFDocumentProxy>((_, reject) => {
        setTimeout(() => {
          reject(new Error(`PDF 解析超时（>${Math.round(pdfParseMs / 1000)}s），请尝试重新打开或下载原文排查`))
        }, pdfParseMs)
      }),
    ])
    if (gen !== loadGeneration) {
      void doc.destroy()
      return
    }
    pdfDoc.value = doc
    numPages.value = doc.numPages
    pageNum.value = 1
    lastEmittedPdfPage = 1
  } catch (e) {
    if (gen === loadGeneration) {
      error.value = getKnowledgeBaseErrorMessage(e, '加载 PDF 失败')
    }
  } finally {
    if (gen === loadGeneration) {
      loading.value = false
    }
  }
  if (gen !== loadGeneration) {
    return
  }
  if (pdfDoc.value) {
    await nextTick()
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
    await nextTick()
    await renderVisiblePages()
    setupResizeObserver()
    setupStackWheel()
    const el = getStackEl()
    const p = el ? detectDominantPdfPage(el) : null
    if (p != null) {
      lastEmittedPdfPage = p
      emit('page-change', p)
    }
    emit('ready', numPages.value)
    resolveReadyWaiters()
  }
}

watch(
  () => [props.kbId, props.documentId],
  () => {
    void loadPdf()
  },
)

watch(
  () => props.modelValue,
  async (idx) => {
    if (idx == null || !props.items.length) {
      return
    }
    const it = props.items[idx]
    if (!it || typeof it.page_idx !== 'number') {
      return
    }
    const want = it.page_idx + 1
    if (want !== pageNum.value && want >= 1 && want <= numPages.value) {
      pageNum.value = want
      await renderVisiblePages()
      await scrollStackToTop()
    }
  },
)

watch(pageNum, (n) => {
  lastEmittedPdfPage = n
  emit('page-change', n)
})

onMounted(() => {
  void loadPdf()
})

let readyWaiters: Array<() => void> = []

function resolveReadyWaiters() {
  if (loading.value || !pdfDoc.value || numPages.value < 1) {
    return
  }
  const waiters = readyWaiters
  readyWaiters = []
  waiters.forEach((fn) => fn())
}

async function whenReady(): Promise<void> {
  if (!loading.value && pdfDoc.value && numPages.value > 0) {
    return
  }
  return new Promise<void>((resolve) => {
    readyWaiters.push(resolve)
  })
}

async function scrollPageSlabIntoView(page: number) {
  await nextTick()
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  const root = getStackEl()
  const slab = root?.querySelector<HTMLElement>(`.pdf-mineru-page-slab[data-pdf-page="${page}"]`)
  slab?.scrollIntoView({ behavior: 'auto', block: 'start' })
}

async function scrollBlockIntoView(index: number) {
  await nextTick()
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  const root = getStackEl()
  const btn = root?.querySelector<HTMLElement>(`button[data-mineru-block-index="${index}"]`)
  btn?.scrollIntoView({ behavior: 'auto', block: 'center' })
}

async function focusBlockInternal(index: number) {
  const it = props.items[index]
  if (!it || typeof it.page_idx !== 'number') {
    return
  }
  const want = it.page_idx + 1
  if (want >= 1 && want <= numPages.value) {
    if (want !== pageNum.value) {
      pageNum.value = want
      await renderVisiblePages()
      await scrollStackToTop()
    }
    emit('update:modelValue', index)
    await scrollBlockIntoView(index)
  }
}

async function goToCitationPage(page: number, blockIndex: number | null = null) {
  await whenReady()
  if (page < 1 || page > numPages.value) {
    return
  }
  if (blockIndex != null && props.items.length > 0) {
    await focusBlockInternal(blockIndex)
    return
  }
  if (page !== pageNum.value) {
    pageNum.value = page
    await renderVisiblePages()
    await scrollStackToTop()
  }
  await scrollPageSlabIntoView(page)
}

defineExpose({
  whenReady,
  isReady: () => !loading.value && pdfDoc.value != null && numPages.value > 0,
  async goToPage(n: number) {
    await whenReady()
    await goPage(n)
  },
  getPageNum: () => pageNum.value,
  async goToCitationPage(page: number, blockIndex: number | null = null) {
    await goToCitationPage(page, blockIndex)
  },
  async focusBlock(index: number | null) {
    if (index == null) {
      return
    }
    await whenReady()
    await focusBlockInternal(index)
  },
})

onUnmounted(() => {
  loadGeneration += 1
  teardownResizeObserver()
  void pdfDoc.value?.destroy()
  pdfDoc.value = null
})
</script>

<style scoped>
.pdf-mineru-layout {
  width: 100%;
  min-width: 0;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  overflow: hidden;
}

.pdf-mineru-scroll-wrap {
  flex: 1;
  min-height: 0;
  min-width: 0;
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}

.pdf-mineru-loading {
  padding: 48px 16px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.pdf-mineru-toolbar {
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 12px;
  padding: 2px 12px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.pdf-mineru-toolbar .btn {
  font-size: 0.76rem;
  padding: 3px 9px;
}

.pdf-mineru-page-label {
  font-size: 0.76rem;
  color: var(--text-secondary);
  min-width: 96px;
  text-align: center;
}

.pdf-mineru-hint {
  margin-left: auto;
  font-size: 0.72rem;
  color: var(--text-tertiary);
}

.pdf-mineru-pages {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 10px 4px 14px 2px;
}

.pdf-mineru-page-slab {
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: var(--bg-tertiary);
  padding: 8px 8px 10px;
}

.pdf-mineru-page-badge {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}

.pdf-mineru-slab-stack {
  position: relative;
  display: block;
  width: 100%;
  max-width: 100%;
}

.pdf-mineru-canvas {
  display: block;
  vertical-align: top;
}

.pdf-mineru-overlay {
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: none;
}

.pdf-mineru-box {
  position: absolute;
  pointer-events: auto;
  margin: 0;
  padding: 0;
  border: 2px solid rgba(37, 99, 235, 0.55);
  border-radius: 4px;
  background: rgba(59, 130, 246, 0.12);
  cursor: pointer;
  box-sizing: border-box;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.pdf-mineru-box:hover {
  background: rgba(59, 130, 246, 0.22);
  border-color: rgba(37, 99, 235, 0.85);
}

.pdf-mineru-box.chunk-range {
  background: rgba(250, 204, 21, 0.2);
  border-color: #d97706;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.22);
}

.pdf-mineru-box.active {
  background: rgba(59, 130, 246, 0.32);
  border-color: #1d4ed8;
  box-shadow: 0 0 0 2px rgba(29, 78, 216, 0.25);
}

.pdf-mineru-box.citation-focus {
  background: rgba(250, 204, 21, 0.35);
  border-color: #d97706;
  box-shadow:
    0 0 0 3px rgba(245, 158, 11, 0.35),
    0 0 12px rgba(245, 158, 11, 0.45);
  animation: pdf-mineru-citation-pulse 1.6s ease-in-out 3;
}

@keyframes pdf-mineru-citation-pulse {
  0%,
  100% {
    box-shadow:
      0 0 0 3px rgba(245, 158, 11, 0.35),
      0 0 12px rgba(245, 158, 11, 0.45);
  }
  50% {
    box-shadow:
      0 0 0 5px rgba(245, 158, 11, 0.55),
      0 0 18px rgba(245, 158, 11, 0.65);
  }
}
</style>
