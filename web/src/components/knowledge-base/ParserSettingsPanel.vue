<script setup lang="ts">
import { computed, ref } from 'vue'

import { getKnowledgeBaseErrorMessage, knowledgeBaseApi, type KnowledgeBase } from '../../api/knowledge-base'
import AppIcon from '../AppIcon.vue'

const DEFAULT_PARSERS = {
  pdf: { engine: 'opendataloader', hybrid: false },
  docx: { engine: 'python-docx' },
  excel: { engine: 'html_table' },
  csv: { engine: 'standard' },
  text: { engine: 'native' },
} as const

type PdfEngine = 'opendataloader' | 'mineru' | 'docling'
type ExcelEngine = 'html_table' | 'tsv'

const props = defineProps<{
  knowledgeBase: KnowledgeBase
}>()

const emit = defineEmits<{
  saved: [kb: KnowledgeBase]
}>()

const expanded = ref(false)
const saving = ref(false)

function parsersConfig(): Record<string, unknown> {
  const cfg = (props.knowledgeBase.config || {}) as Record<string, unknown>
  const raw = cfg.parsers
  return raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
}

function pdfSection(): Record<string, unknown> {
  const p = parsersConfig().pdf
  if (p && typeof p === 'object') {
    return { ...DEFAULT_PARSERS.pdf, ...(p as Record<string, unknown>) }
  }
  const cfg = (props.knowledgeBase.config || {}) as Record<string, unknown>
  const legacy = cfg.pdf_parser
  const hybrid = cfg.pdf_parser_hybrid === true
  let engine: PdfEngine = 'opendataloader'
  if (legacy === 'mineru' || legacy === 'docling') {
    engine = legacy
  }
  return { engine, hybrid }
}

const pdfEngine = computed<PdfEngine>(() => {
  const e = pdfSection().engine
  return e === 'mineru' || e === 'docling' ? e : 'opendataloader'
})

const pdfHybrid = computed(() => pdfSection().hybrid === true)

const excelEngine = computed<ExcelEngine>(() => {
  const ex = parsersConfig().excel
  if (ex && typeof ex === 'object' && (ex as Record<string, unknown>).engine === 'tsv') {
    return 'tsv'
  }
  return 'html_table'
})

async function saveParsers(patch: Record<string, unknown>) {
  if (!props.knowledgeBase.id) {
    return
  }
  saving.value = true
  try {
    const prev = (props.knowledgeBase.config || {}) as Record<string, unknown>
    const prevParsers = (prev.parsers && typeof prev.parsers === 'object'
      ? prev.parsers
      : {}) as Record<string, unknown>
    const nextParsers = { ...prevParsers, ...patch }
    const nextConfig = { ...prev, parsers: nextParsers } as Record<string, unknown>
    delete nextConfig.pdf_parser
    delete nextConfig.pdf_parser_hybrid
    const updated = await knowledgeBaseApi.update(props.knowledgeBase.id, { config: nextConfig })
    emit('saved', updated)
  } catch (e) {
    alert(getKnowledgeBaseErrorMessage(e, '保存解析器配置失败'))
  } finally {
    saving.value = false
  }
}

async function onPdfEngineChange(evt: Event) {
  const val = (evt.target as HTMLSelectElement).value as PdfEngine
  const section = { ...pdfSection(), engine: val }
  if (val !== 'opendataloader') {
    section.hybrid = false
  }
  await saveParsers({ pdf: section })
}

async function onPdfHybridChange(evt: Event) {
  const checked = (evt.target as HTMLInputElement).checked
  await saveParsers({ pdf: { ...pdfSection(), hybrid: checked } })
}

async function onExcelEngineChange(evt: Event) {
  const val = (evt.target as HTMLSelectElement).value as ExcelEngine
  await saveParsers({ excel: { engine: val } })
}

async function restoreDefaults() {
  await saveParsers({ ...DEFAULT_PARSERS })
}
</script>

<template>
  <div class="parser-settings">
    <div class="parser-header">
      <div class="parser-title-row">
        <h4 class="parser-title">解析器</h4>
        <p class="parser-sub">按文件类型选择解析引擎；复杂 PDF 推荐 MinerU，Excel 默认 HTML 表格。</p>
      </div>
      <button class="btn btn-ghost parser-toggle-btn" type="button" @click="expanded = !expanded">
        <AppIcon :name="expanded ? 'chevron-up' : 'chevron-down'" :size="16" />
        {{ expanded ? '收起' : '展开' }}
      </button>
    </div>

    <template v-if="expanded">
      <div class="parser-rows">
        <div class="parser-row">
          <label class="parser-label">PDF</label>
          <div class="parser-field">
            <div class="custom-select-wrap">
              <select
                class="custom-select"
                :value="pdfEngine"
                :disabled="saving"
                @change="onPdfEngineChange"
              >
                <option value="opendataloader">OpenDataLoader（普通 PDF，本地 CPU）</option>
                <option value="mineru">MinerU（复杂研报 / 多表 / 扫描件）</option>
                <option value="docling">Docling（即将支持）</option>
              </select>
              <span class="custom-select-arrow"><AppIcon name="chevron-down" :size="14" /></span>
            </div>
            <p v-if="pdfEngine === 'mineru'" class="parser-hint">适合复杂研报、扫描 PDF、表格较多的文档。</p>
            <p v-else-if="pdfEngine === 'opendataloader'" class="parser-hint">适合普通 PDF；复杂表格可改选 MinerU。</p>
            <label v-if="pdfEngine === 'opendataloader'" class="parser-check">
              <input type="checkbox" :checked="pdfHybrid" :disabled="saving" @change="onPdfHybridChange" />
              Hybrid 模式（扫描件 / 复杂页，需 odl-hybrid sidecar）
            </label>
          </div>
        </div>

        <div class="parser-row">
          <label class="parser-label">Word</label>
          <div class="parser-field">
            <div class="custom-select-wrap">
              <select class="custom-select" disabled>
                <option value="python-docx">python-docx（段落 + 表格）</option>
              </select>
            </div>
          </div>
        </div>

        <div class="parser-row">
          <label class="parser-label">Excel</label>
          <div class="parser-field">
            <div class="custom-select-wrap">
              <select
                class="custom-select"
                :value="excelEngine"
                :disabled="saving"
                @change="onExcelEngineChange"
              >
                <option value="html_table">HTML 表格（推荐，保留结构）</option>
                <option value="tsv">TSV 文本（兼容旧行为）</option>
              </select>
              <span class="custom-select-arrow"><AppIcon name="chevron-down" :size="14" /></span>
            </div>
            <p class="parser-hint">HTML 模式对齐 RAGFlow Spreadsheet，检索与展示更优。</p>
          </div>
        </div>

        <div class="parser-row">
          <label class="parser-label">CSV</label>
          <div class="parser-field">
            <div class="custom-select-wrap">
              <select class="custom-select" disabled>
                <option value="standard">标准 CSV 解析</option>
              </select>
            </div>
          </div>
        </div>

        <div class="parser-row">
          <label class="parser-label">文本</label>
          <div class="parser-field">
            <div class="custom-select-wrap">
              <select class="custom-select" disabled>
                <option value="native">Markdown / 纯文本</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div class="parser-actions">
        <button class="btn btn-ghost" type="button" :disabled="saving" @click="restoreDefaults">
          恢复默认
        </button>
        <span v-if="saving" class="parser-saving">保存中…</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.parser-settings {
  display: grid;
  gap: 12px;
  margin-top: 8px;
}

.parser-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.parser-title-row {
  display: grid;
  gap: 4px;
}

.parser-title {
  margin: 0;
  font-size: 1.05rem;
  color: var(--text-primary);
}

.parser-sub {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.parser-toggle-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 32px;
  padding: 4px 12px;
  font-size: 0.85rem;
  border-radius: 10px;
}

.parser-rows {
  display: grid;
  gap: 14px;
  padding: 4px 0;
}

.parser-row {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 12px;
  align-items: start;
}

.parser-label {
  font-weight: 600;
  font-size: 0.92rem;
  color: var(--text-primary);
  padding-top: 8px;
}

.parser-field {
  display: grid;
  gap: 6px;
}

.parser-hint {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.45;
}

.parser-check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  color: var(--text-secondary);
}

.parser-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.parser-saving {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.custom-select-wrap {
  position: relative;
  max-width: 420px;
}

.custom-select {
  width: 100%;
  appearance: none;
  padding: 8px 36px 8px 12px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-size: 0.9rem;
}

.custom-select-arrow {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--text-secondary);
}
</style>
