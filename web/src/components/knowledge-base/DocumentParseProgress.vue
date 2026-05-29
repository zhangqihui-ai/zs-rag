<script setup lang="ts">
defineProps<{
  percent: number
  title?: string
}>()

const emit = defineEmits<{
  openLog: []
  cancel: []
}>()
</script>

<template>
  <div class="doc-parse-progress" :title="title || '点击查看解析日志'">
    <button class="doc-parse-progress-main" type="button" @click="emit('openLog')">
      <span class="doc-parse-progress-track" aria-hidden="true">
        <span class="doc-parse-progress-fill" :style="{ width: `${Math.min(Math.max(percent, 0), 100)}%` }" />
      </span>
      <span class="doc-parse-progress-pct">{{ Math.round(percent) }}%</span>
    </button>
    <button
      class="doc-parse-progress-cancel"
      type="button"
      title="停止解析"
      aria-label="停止解析"
      @click.stop="emit('cancel')"
    >
      ×
    </button>
  </div>
</template>

<style scoped>
.doc-parse-progress {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 176px;
  flex-shrink: 0;
}

.doc-parse-progress-main {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: 1 1 auto;
  min-width: 0;
  padding: 2px 4px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 4px;
}

.doc-parse-progress-main:hover {
  background: rgba(59, 130, 246, 0.06);
}

.doc-parse-progress-track {
  display: block;
  width: 88px;
  height: 4px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.12);
  overflow: hidden;
  flex-shrink: 0;
}

.doc-parse-progress-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--brand-primary, #3b82f6);
  transition: width 0.25s ease;
}

.doc-parse-progress-pct {
  font-size: 11px;
  line-height: 1;
  color: var(--text-secondary, #64748b);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
  min-width: 2.5em;
  text-align: right;
}

.doc-parse-progress-cancel {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: #ef4444;
  color: #fff;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  flex-shrink: 0;
}

.doc-parse-progress-cancel:hover {
  background: #dc2626;
}
</style>
