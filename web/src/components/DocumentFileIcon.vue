<template>
  <span :class="['doc-file-icon', `doc-file-icon--${kind}`]" aria-hidden="true">
    <svg viewBox="0 0 20 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        :fill="fillColor"
        d="M4 2.5A1.5 1.5 0 0 1 5.5 1H12l5.5 5.5V21.5A1.5 1.5 0 0 1 16 23H5.5A1.5 1.5 0 0 1 4 21.5V2.5Z"
      />
      <path :fill="foldColor" d="M12 1v5.5H17.5L12 1Z" />
      <text
        v-if="badge"
        x="10"
        y="17"
        text-anchor="middle"
        fill="#fff"
        font-size="6.5"
        font-weight="600"
        font-family="system-ui, -apple-system, 'Segoe UI', sans-serif"
      >
        {{ badge }}
      </text>
    </svg>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  ext?: string | null
}>()

const kind = computed(() => {
  const e = (props.ext || '').replace(/^\./, '').toLowerCase()
  if (e === 'pdf') return 'pdf'
  if (e === 'docx' || e === 'doc') return 'word'
  if (e === 'xlsx' || e === 'xls' || e === 'xlsm') return 'excel'
  if (e === 'csv') return 'csv'
  if (e === 'md' || e === 'txt') return 'text'
  return 'generic'
})

const badge = computed(() => {
  const map: Record<string, string> = {
    pdf: 'PDF',
    word: 'W',
    excel: 'X',
    csv: 'CSV',
    text: 'T',
  }
  return map[kind.value] || ''
})

const fillColor = computed(() => {
  const map: Record<string, string> = {
    pdf: '#E85D4C',
    word: '#4A90D9',
    excel: '#3D9A5F',
    csv: '#5B8DEF',
    text: '#8B909A',
    generic: '#A8ADB8',
  }
  return map[kind.value]
})

const foldColor = computed(() => {
  const map: Record<string, string> = {
    pdf: '#C94A3A',
    word: '#3A7BC8',
    excel: '#2E8049',
    csv: '#4A78D4',
    text: '#727682',
    generic: '#9096A3',
  }
  return map[kind.value]
})
</script>

<style scoped>
.doc-file-icon {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 22px;
}

.doc-file-icon svg {
  width: 18px;
  height: 22px;
  display: block;
}
</style>
