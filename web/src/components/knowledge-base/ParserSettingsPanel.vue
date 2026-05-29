<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import axios from 'axios'

import { getKnowledgeBaseErrorMessage, knowledgeBaseApi, type KnowledgeBase } from '../../api/knowledge-base'
import { fetchParserCapabilities, type ParserCapabilities } from '../../api/system'
import AppIcon from '../AppIcon.vue'

const DEFAULT_PARSERS = {
  pdf: { engine: 'opendataloader', hybrid: false },
  docx: { engine: 'python-docx' },
  excel: { engine: 'html_table' },
  csv: { engine: 'standard' },
  text: { engine: 'native' },
} as const

type PdfEngine = 'opendataloader' | 'mineru' | 'docling'
type ExcelEngine = 'html_table' | 'tsv' | 'mineru'
type DocxEngine = 'python-docx' | 'mineru'
type CsvEngine = 'standard' | 'mineru'
type TextEngine = 'native' | 'mineru'

const props = defineProps<{
  knowledgeBase: KnowledgeBase
}>()

const emit = defineEmits<{
  saved: [kb: KnowledgeBase]
  expandedChange: [expanded: boolean]
}>()

const expanded = ref(false)
const saving = ref(false)
const capabilities = ref<ParserCapabilities | null>(null)
const capabilitiesLoading = ref(true)
const capabilitiesError = ref('')

const mineruEnabled = computed(() => capabilities.value?.mineru.enabled === true)
const showMineruPdfOption = computed(
  () => mineruEnabled.value || pdfEngine.value === 'mineru',
)

async function loadCapabilities() {
  capabilitiesLoading.value = true
  capabilitiesError.value = ''
  try {
    capabilities.value = await fetchParserCapabilities()
  } catch (e) {
    console.error('加载解析器能力失败', e)
    capabilities.value = { mineru: { enabled: false, formats: [] } }
    if (axios.isAxiosError(e)) {
      const status = e.response?.status
      if (status === 404) {
        capabilitiesError.value =
          '无法加载解析引擎列表（接口不存在，HTTP 404）。请更新并重启 backend 镜像后再试。'
      } else if (status) {
        capabilitiesError.value = `无法加载解析引擎列表（HTTP ${status}）。请检查 backend 与 nginx 反代。`
      } else {
        capabilitiesError.value = '无法连接后端以加载解析引擎列表，请确认 backend 已启动且 nginx 已配置 /system/ 反代。'
      }
    } else {
      capabilitiesError.value = `无法加载解析引擎列表：${e instanceof Error ? e.message : String(e)}`
    }
  } finally {
    capabilitiesLoading.value = false
  }
}

onMounted(() => {
  void loadCapabilities()
})

watch(expanded, (open) => {
  emit('expandedChange', open)
  if (open) {
    void nextTick(() => {
      document.getElementById('kb-parser-settings-body')?.scrollIntoView({
        block: 'nearest',
        behavior: 'smooth',
      })
    })
  }
})

function toggleExpanded() {
  expanded.value = !expanded.value
}

function parsersConfig(): Record<string, unknown> {
  const cfg = (props.knowledgeBase.config || {}) as Record<string, unknown>
  const raw = cfg.parsers
  return raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
}

function section(key: 'pdf' | 'docx' | 'excel' | 'csv' | 'text'): Record<string, unknown> {
  const p = parsersConfig()[key]
  if (p && typeof p === 'object') {
    return { ...DEFAULT_PARSERS[key], ...(p as Record<string, unknown>) }
  }
  return { ...DEFAULT_PARSERS[key] }
}

function pdfSection(): Record<string, unknown> {
  const merged = section('pdf')
  const cfg = (props.knowledgeBase.config || {}) as Record<string, unknown>
  const legacy = cfg.pdf_parser
  const hybrid = cfg.pdf_parser_hybrid === true
  let engine: PdfEngine = 'opendataloader'
  if (legacy === 'mineru' || legacy === 'docling') {
    engine = legacy
  } else if (merged.engine === 'mineru' || merged.engine === 'docling') {
    engine = merged.engine as PdfEngine
  }
  return { ...merged, engine, hybrid: merged.hybrid === true || hybrid }
}

const pdfEngine = computed<PdfEngine>(() => {
  const e = pdfSection().engine
  return e === 'mineru' || e === 'docling' ? e : 'opendataloader'
})

const pdfHybrid = computed(() => pdfSection().hybrid === true)

const docxEngine = computed<DocxEngine>(() => {
  const e = section('docx').engine
  return e === 'mineru' ? 'mineru' : 'python-docx'
})

const excelEngine = computed<ExcelEngine>(() => {
  const e = section('excel').engine
  if (e === 'tsv') return 'tsv'
  if (e === 'mineru') return 'mineru'
  return 'html_table'
})

const csvEngine = computed<CsvEngine>(() => {
  const e = section('csv').engine
  return e === 'mineru' ? 'mineru' : 'standard'
})

const textEngine = computed<TextEngine>(() => {
  const e = section('text').engine
  return e === 'mineru' ? 'mineru' : 'native'
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
  const sec: Record<string, unknown> = { ...pdfSection(), engine: val }
  if (val !== 'opendataloader') {
    sec.hybrid = false
  }
  await saveParsers({ pdf: sec })
}

async function onPdfHybridChange(evt: Event) {
  const checked = (evt.target as HTMLInputElement).checked
  await saveParsers({ pdf: { ...pdfSection(), hybrid: checked } })
}

async function onDocxEngineChange(evt: Event) {
  const val = (evt.target as HTMLSelectElement).value as DocxEngine
  await saveParsers({ docx: { engine: val } })
}

async function onExcelEngineChange(evt: Event) {
  const val = (evt.target as HTMLSelectElement).value as ExcelEngine
  await saveParsers({ excel: { engine: val } })
}

async function onCsvEngineChange(evt: Event) {
  const val = (evt.target as HTMLSelectElement).value as CsvEngine
  await saveParsers({ csv: { engine: val } })
}

async function onTextEngineChange(evt: Event) {
  const val = (evt.target as HTMLSelectElement).value as TextEngine
  await saveParsers({ text: { engine: val } })
}

async function restoreDefaults() {
  await saveParsers({ ...DEFAULT_PARSERS })
}
</script>

<template>
  <div :class="['parser-settings', { 'parser-settings--expanded': expanded }]">
    <div class="parser-header">
      <div class="parser-title-row">
        <h4 class="parser-title">解析器</h4>
        <p v-if="!expanded" class="parser-sub">
          按文件类型选择解析引擎；复杂 PDF 推荐 MinerU。部署 MinerU 后可为 Word / Excel / CSV / 文本选用 MinerU。
        </p>
      </div>
      <button
        class="btn btn-ghost parser-toggle-btn"
        type="button"
        :aria-expanded="expanded"
        aria-controls="kb-parser-settings-body"
        @click.stop="toggleExpanded"
      >
        <AppIcon :name="expanded ? 'chevron-up' : 'chevron-down'" :size="16" />
        {{ expanded ? '收起' : '展开' }}
      </button>
    </div>

    <div v-if="expanded" id="kb-parser-settings-body" class="parser-body">
      <p v-if="capabilitiesError" class="parser-error">{{ capabilitiesError }}</p>
      <p v-if="capabilitiesLoading" class="parser-loading">正在加载可用解析引擎…</p>
      <div v-else class="parser-rows">
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
                <option v-if="showMineruPdfOption" value="mineru">MinerU（复杂研报 / 多表 / 扫描件）</option>
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
              <select
                class="custom-select"
                :value="docxEngine"
                :disabled="saving"
                @change="onDocxEngineChange"
              >
                <option value="python-docx">python-docx（段落 + 表格）</option>
                <option v-if="mineruEnabled" value="mineru">MinerU（复杂版式 / 扫描件）</option>
              </select>
              <span class="custom-select-arrow"><AppIcon name="chevron-down" :size="14" /></span>
            </div>
            <p v-if="!mineruEnabled" class="parser-hint">启用 MinerU 后可选用 MinerU 解析 Word。</p>
            <p v-else-if="docxEngine === 'mineru'" class="parser-hint">复杂版式或扫描 Word 推荐 MinerU。</p>
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
                <option v-if="mineruEnabled" value="mineru">MinerU（复杂表格 / 扫描件）</option>
              </select>
              <span class="custom-select-arrow"><AppIcon name="chevron-down" :size="14" /></span>
            </div>
            <p class="parser-hint">HTML 模式对齐 RAGFlow Spreadsheet；MinerU 适合复杂或扫描表格。</p>
          </div>
        </div>

        <div class="parser-row">
          <label class="parser-label">CSV</label>
          <div class="parser-field">
            <div class="custom-select-wrap">
              <select
                class="custom-select"
                :value="csvEngine"
                :disabled="saving"
                @change="onCsvEngineChange"
              >
                <option value="standard">标准 CSV 解析</option>
                <option v-if="mineruEnabled" value="mineru">MinerU</option>
              </select>
              <span class="custom-select-arrow"><AppIcon name="chevron-down" :size="14" /></span>
            </div>
            <p v-if="!mineruEnabled" class="parser-hint">启用 MinerU 后可选用 MinerU 解析 CSV。</p>
          </div>
        </div>

        <div class="parser-row">
          <label class="parser-label">文本</label>
          <div class="parser-field">
            <div class="custom-select-wrap">
              <select
                class="custom-select"
                :value="textEngine"
                :disabled="saving"
                @change="onTextEngineChange"
              >
                <option value="native">Markdown / 纯文本（本地）</option>
                <option v-if="mineruEnabled" value="mineru">MinerU</option>
              </select>
              <span class="custom-select-arrow"><AppIcon name="chevron-down" :size="14" /></span>
            </div>
            <p v-if="!mineruEnabled" class="parser-hint">启用 MinerU 后可对 .md / .txt 选用 MinerU。</p>
          </div>
        </div>
      </div>

      <div v-if="!capabilitiesLoading" class="parser-actions">
        <button class="btn btn-ghost" type="button" :disabled="saving" @click="restoreDefaults">
          恢复默认
        </button>
        <span v-if="saving" class="parser-saving">保存中…</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.parser-settings {
  display: grid;
  gap: 12px;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid var(--border-color);
  position: relative;
}

.parser-settings--expanded {
  position: relative;
  z-index: 5;
  overflow: visible;
}

.parser-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.parser-title-row {
  display: grid;
  gap: 4px;
  flex: 1 1 240px;
  min-width: 0;
}

.parser-body {
  display: grid;
  gap: 12px;
  overflow: visible;
  scroll-margin-top: 12px;
  scroll-margin-bottom: 24px;
}

.parser-error {
  margin: 0;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 0.88rem;
  line-height: 1.45;
  color: var(--danger-color);
  background: color-mix(in srgb, var(--danger-color) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--danger-color) 28%, var(--border-color));
}

.parser-loading {
  margin: 0;
  font-size: 0.88rem;
  color: var(--text-secondary);
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
