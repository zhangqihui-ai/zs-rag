<template>
  <div v-if="html.trim()" class="chunk-data-table-panel">
    <div
      ref="tableWrapRef"
      class="chunk-data-table-wrap chunk-data-table-compact"
      :class="wrapClass"
      v-html="html"
      @click="onTableClick"
    />
    <div class="chunk-data-table-cell-detail">
      <div class="chunk-data-table-cell-detail-head">
        <span class="chunk-data-table-cell-detail-label">{{ selectedLabel || '单元格完整内容' }}</span>
        <button
          v-if="selectedText"
          type="button"
          class="btn btn-ghost btn-sm"
          @click="clearSelection"
        >
          清除选中
        </button>
      </div>
      <pre v-if="selectedText" class="chunk-data-table-cell-detail-body">{{ selectedText }}</pre>
      <p v-else class="chunk-data-table-cell-detail-hint">点击上方表格中的单元格，在此查看该格全部文本（表格内仍为固定行高省略显示）</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = defineProps<{
  html: string
  /** 附加在表格容器上的 class，如 retrieval-chunk-content-table */
  wrapClass?: string
}>()

const tableWrapRef = ref<HTMLElement | null>(null)
const selectedText = ref('')
const selectedLabel = ref('')

const CELL_SELECTED_CLASS = 'is-cell-selected'

function clearSelection() {
  selectedText.value = ''
  selectedLabel.value = ''
  tableWrapRef.value?.querySelectorAll(`.${CELL_SELECTED_CLASS}`).forEach((el) => {
    el.classList.remove(CELL_SELECTED_CLASS)
  })
}

function columnLabelForCell(cell: HTMLTableCellElement): string | null {
  const table = cell.closest('table')
  if (!table) {
    return null
  }
  const row = cell.parentElement
  if (!row || !(row instanceof HTMLTableRowElement)) {
    return null
  }
  const cellIndex = cell.cellIndex
  const headerRow = table.querySelector('thead tr') ?? table.querySelector('tr')
  if (!headerRow) {
    return null
  }
  const headerCell = headerRow.cells.item(cellIndex)
  if (!headerCell) {
    return null
  }
  const text = (headerCell.textContent || '').replace(/\s+/g, ' ').trim()
  return text || null
}

function onTableClick(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof HTMLElement)) {
    return
  }
  const cell = target.closest('td, th')
  if (!cell || !(cell instanceof HTMLTableCellElement)) {
    return
  }
  const wrap = tableWrapRef.value
  if (!wrap || !wrap.contains(cell)) {
    return
  }

  wrap.querySelectorAll(`.${CELL_SELECTED_CLASS}`).forEach((el) => {
    el.classList.remove(CELL_SELECTED_CLASS)
  })
  cell.classList.add(CELL_SELECTED_CLASS)

  const fullText = (cell.textContent || '').replace(/\s+/g, ' ').trim()
  selectedText.value = fullText
  const col = columnLabelForCell(cell)
  const tag = cell.tagName.toLowerCase() === 'th' ? '表头' : '单元格'
  selectedLabel.value = col ? `${tag} · ${col}` : tag
}

watch(
  () => props.html,
  () => {
    clearSelection()
    void nextTick(() => {
      tableWrapRef.value?.querySelectorAll('td, th').forEach((el) => {
        el.setAttribute('tabindex', '0')
        el.setAttribute('role', 'button')
      })
    })
  },
)
</script>

<style scoped>
.chunk-data-table-panel {
  display: grid;
  gap: 10px;
}

.chunk-data-table-wrap {
  margin: 0;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  overflow: auto;
  max-height: min(420px, 50vh);
}

.chunk-data-table-cell-detail {
  border: 1px solid color-mix(in srgb, var(--brand-primary) 35%, var(--border-color));
  border-radius: 12px;
  background: color-mix(in srgb, var(--brand-primary) 6%, var(--bg-primary));
  overflow: hidden;
}

.chunk-data-table-cell-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.chunk-data-table-cell-detail-label {
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--text-primary);
}

.chunk-data-table-cell-detail-body {
  margin: 0;
  padding: 12px 14px;
  max-height: min(240px, 30vh);
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font: inherit;
  font-size: 0.86rem;
  line-height: 1.55;
  color: var(--text-primary);
}

.chunk-data-table-cell-detail-hint {
  margin: 0;
  padding: 10px 14px;
  color: var(--text-tertiary);
  font-size: 0.8rem;
  line-height: 1.45;
}

.chunk-data-table-wrap :deep(td),
.chunk-data-table-wrap :deep(th) {
  cursor: pointer;
}

.chunk-data-table-wrap :deep(td.is-cell-selected),
.chunk-data-table-wrap :deep(th.is-cell-selected) {
  outline: 2px solid var(--brand-primary);
  outline-offset: -2px;
  background: color-mix(in srgb, var(--brand-primary) 14%, var(--bg-primary)) !important;
  position: relative;
  z-index: 1;
}
</style>
