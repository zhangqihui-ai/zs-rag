<template>
  <div class="spreadsheet-original-preview">
    <div v-if="sheets.length > 1" class="spreadsheet-sheet-tabs" role="tablist">
      <button
        v-for="(sheet, index) in sheets"
        :key="`${sheet.name}-${index}`"
        type="button"
        role="tab"
        class="spreadsheet-sheet-tab"
        :class="{ active: index === activeSheetIndex }"
        :aria-selected="index === activeSheetIndex"
        @click="selectSheet(index)"
      >
        {{ sheet.name }}
      </button>
    </div>

    <div v-if="!currentSheet || currentSheet.rows.length === 0" class="spreadsheet-empty">（空表）</div>

    <template v-else>
      <div class="spreadsheet-table-toolbar">
        <span class="spreadsheet-table-meta">
          已显示 {{ displayedRowCount }} / {{ totalDataRows }} 行
          <template v-if="columnCount"> · {{ columnCount }} 列</template>
        </span>
        <button v-if="hasMoreRows" type="button" class="btn btn-ghost btn-sm" @click="loadMoreRows">
          加载更多（+{{ rowBatch }} 行）
        </button>
      </div>

      <div class="spreadsheet-table-wrap chunk-data-table-compact" @click="onTableClick">
        <table class="xlsx-preview-table">
          <thead v-if="headerRow.length">
            <tr>
              <th
                v-for="(cell, colIndex) in headerRow"
                :key="`h-${colIndex}`"
                :title="cell || undefined"
              >
                {{ cell }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in visibleBodyRows" :key="`r-${rowIndex}`">
              <td
                v-for="(cell, colIndex) in row"
                :key="`c-${rowIndex}-${colIndex}`"
                :title="cell || undefined"
                :class="{ 'is-cell-selected': isSelectedCell(rowIndex, colIndex) }"
              >
                {{ cell }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="spreadsheet-cell-detail">
        <div class="spreadsheet-cell-detail-head">
          <span class="spreadsheet-cell-detail-label">{{ selectedLabel || '单元格完整内容' }}</span>
          <button v-if="selectedText" type="button" class="btn btn-ghost btn-sm" @click="clearSelection">
            清除选中
          </button>
        </div>
        <pre v-if="selectedText" class="spreadsheet-cell-detail-body">{{ selectedText }}</pre>
        <p v-else class="spreadsheet-cell-detail-hint">
          点击上方表格中的单元格，在此查看该格全部文本（表格内为固定行高省略显示）
        </p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import {
  SPREADSHEET_INITIAL_ROWS,
  SPREADSHEET_ROW_BATCH,
  type SpreadsheetSheet,
} from '../lib/officePreview'

const props = defineProps<{
  sheets: SpreadsheetSheet[]
}>()

const activeSheetIndex = ref(0)
const visibleLimit = ref(SPREADSHEET_INITIAL_ROWS)
const rowBatch = SPREADSHEET_ROW_BATCH

const selectedRowIndex = ref<number | null>(null)
const selectedColIndex = ref<number | null>(null)
const selectedText = ref('')
const selectedLabel = ref('')

const currentSheet = computed(() => props.sheets[activeSheetIndex.value] ?? null)

const allRows = computed(() => currentSheet.value?.rows ?? [])

const headerRow = computed(() => (allRows.value.length > 1 ? allRows.value[0] ?? [] : []))

const bodyRows = computed(() => (allRows.value.length > 1 ? allRows.value.slice(1) : allRows.value))

const visibleBodyRows = computed(() => bodyRows.value.slice(0, visibleLimit.value))

const totalDataRows = computed(() => bodyRows.value.length)

const displayedRowCount = computed(() => visibleBodyRows.value.length)

const hasMoreRows = computed(() => bodyRows.value.length > visibleLimit.value)

const columnCount = computed(() => headerRow.value.length)

function selectSheet(index: number) {
  activeSheetIndex.value = index
  visibleLimit.value = SPREADSHEET_INITIAL_ROWS
  clearSelection()
}

function loadMoreRows() {
  visibleLimit.value = Math.min(visibleLimit.value + rowBatch, bodyRows.value.length)
}

function isSelectedCell(rowIndex: number, colIndex: number): boolean {
  return selectedRowIndex.value === rowIndex && selectedColIndex.value === colIndex
}

function clearSelection() {
  selectedRowIndex.value = null
  selectedColIndex.value = null
  selectedText.value = ''
  selectedLabel.value = ''
}

function onTableClick(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof HTMLElement)) {
    return
  }
  const cell = target.closest('td')
  if (!cell || !(cell instanceof HTMLTableCellElement)) {
    return
  }
  const row = cell.parentElement
  if (!row || !(row instanceof HTMLTableRowElement)) {
    return
  }
  const tbody = row.parentElement
  if (!tbody || tbody.tagName !== 'TBODY') {
    return
  }
  const rowIndex = Array.from(tbody.children).indexOf(row)
  if (rowIndex < 0) {
    return
  }

  selectedRowIndex.value = rowIndex
  selectedColIndex.value = cell.cellIndex
  selectedText.value = (cell.textContent || '').replace(/\s+/g, ' ').trim()

  const colName = headerRow.value[cell.cellIndex]?.trim()
  const rowNo = rowIndex + 2
  selectedLabel.value = colName ? `第 ${rowNo} 行 · ${colName}` : `第 ${rowNo} 行`
}

watch(
  () => props.sheets,
  () => {
    activeSheetIndex.value = 0
    visibleLimit.value = SPREADSHEET_INITIAL_ROWS
    clearSelection()
  },
)
</script>

<style scoped>
.spreadsheet-original-preview {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  overflow: hidden;
}

.spreadsheet-sheet-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.spreadsheet-sheet-tab {
  padding: 6px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
}

.spreadsheet-sheet-tab.active {
  border-color: var(--brand-primary);
  background: var(--brand-primary-light);
  color: var(--brand-primary);
}

.spreadsheet-table-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.spreadsheet-table-meta {
  font-size: 0.8rem;
  color: var(--text-tertiary);
}

.spreadsheet-table-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-primary);
}

.spreadsheet-empty {
  padding: 24px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 0.88rem;
}

.spreadsheet-cell-detail {
  flex-shrink: 0;
  border: 1px solid color-mix(in srgb, var(--brand-primary) 35%, var(--border-color));
  border-radius: 12px;
  background: color-mix(in srgb, var(--brand-primary) 6%, var(--bg-primary));
  overflow: hidden;
}

.spreadsheet-cell-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.spreadsheet-cell-detail-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}

.spreadsheet-cell-detail-body {
  margin: 0;
  padding: 10px 12px;
  max-height: min(200px, 22vh);
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font: inherit;
  font-size: 0.84rem;
  line-height: 1.5;
  color: var(--text-primary);
}

.spreadsheet-cell-detail-hint {
  margin: 0;
  padding: 8px 12px;
  color: var(--text-tertiary);
  font-size: 0.78rem;
  line-height: 1.45;
}

.spreadsheet-table-wrap :deep(td.is-cell-selected) {
  outline: 2px solid var(--brand-primary);
  outline-offset: -2px;
  background: color-mix(in srgb, var(--brand-primary) 14%, var(--bg-primary)) !important;
}
</style>
