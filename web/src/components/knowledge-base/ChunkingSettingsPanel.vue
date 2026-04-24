<template>
  <div class="chunking-settings">
    <div class="chunking-header">
      <div class="chunking-title-row">
        <h4 class="chunking-title">分段设置</h4>
        <p class="chunking-sub">
          通用模式使用统一分块用于索引与召回；父子分段模式下，子块用于向量检索，父块用于组装上下文（索引侧将随引擎升级逐步对齐）。
        </p>
      </div>
      <button class="btn btn-ghost chunking-toggle-btn" type="button" @click="expanded = !expanded">
        <AppIcon :name="expanded ? 'chevron-up' : 'chevron-down'" :size="16" />
        {{ expanded ? '收起' : '展开' }}
      </button>
    </div>

    <template v-if="expanded">
    <div class="chunking-mode-list" role="radiogroup" aria-label="分段模式">
      <!-- 通用 -->
      <div
        :class="['chunking-card', { 'chunking-card--active': mode === 'general' }]"
        @click="mode = 'general'"
      >
        <div class="chunking-card-head">
          <input v-model="mode" class="chunking-radio" type="radio" value="general" @click.stop />
          <div>
            <div class="chunking-card-title">通用</div>
            <p class="chunking-card-desc">通用文本分块模式，检索与召回使用相同块。</p>
          </div>
        </div>

        <div v-show="mode === 'general'" class="chunking-card-body" @click.stop>
          <div class="chunking-field-row chunking-field-row--tight">
            <label class="field chunking-field chunking-field--id">
              <span class="field-label field-label--compact">
                分段标识符
                <span
                  class="chunking-help"
                  title="按此字符串将原文先切分为大段，再按最大长度细分。支持转义：\\n 换行、\\t 制表符。"
                  >?</span
                >
              </span>
              <input
                v-model="general.delimiter"
                class="input input--chunk-tight"
                type="text"
                placeholder="\n\n"
              />
            </label>
            <label class="field chunking-field chunking-field--num">
              <span class="field-label field-label--compact">分段最大长度</span>
              <div class="chunking-number">
                <input
                  v-model.number="general.max_length"
                  class="input input--chunk-tight chunking-number-input"
                  type="number"
                  min="100"
                  max="5000"
                  step="1"
                />
                <span class="chunking-number-suffix">characters</span>
              </div>
            </label>
            <label class="field chunking-field chunking-field--num">
              <span class="field-label field-label--compact">
                分段重叠长度
                <span
                  class="chunking-help"
                  title="相邻分块间重复字符数，需小于分段最大长度"
                  >?</span
                >
              </span>
              <div class="chunking-number">
                <input
                  v-model.number="general.overlap"
                  class="input input--chunk-tight chunking-number-input"
                  type="number"
                  min="0"
                  max="1000"
                  step="1"
                />
                <span class="chunking-number-suffix">characters</span>
              </div>
            </label>
          </div>

          <div class="chunking-preprocess">
            <span class="field-label field-label--compact">文本预处理规则</span>
            <label class="chunking-check">
              <input v-model="general.collapse_whitespace" type="checkbox" />
              替换掉连续的空格、换行符和制表符
            </label>
          </div>

          <div class="chunking-actions">
            <button class="btn btn-primary" type="button" :disabled="previewLoading" @click="openPreview('general')">
              <AppIcon name="search" :size="16" />
              预览块
            </button>
            <button class="btn btn-ghost" type="button" @click="resetForm('general')">重置</button>
          </div>
        </div>
      </div>

      <!-- 父子分段 -->
      <div
        :class="['chunking-card', { 'chunking-card--active': mode === 'parent_child' }]"
        @click="mode = 'parent_child'"
      >
        <div class="chunking-card-head">
          <input v-model="mode" class="chunking-radio" type="radio" value="parent_child" @click.stop />
          <div>
            <div class="chunking-card-title">父子分段</div>
            <p class="chunking-card-desc">子块用于检索，父块用作上下文（引擎侧能力持续完善中）。</p>
          </div>
        </div>

        <div v-show="mode === 'parent_child'" class="chunking-card-body" @click.stop>
          <div class="chunking-subhead">父块用作上下文</div>
          <div class="parent-mode-row">
            <label class="chunking-segment">
              <input v-model="parent_child.parent_mode" type="radio" value="paragraph" />
              <div>
                <strong>段落</strong>
                <p>按分隔符与最大长度将正文拆为段落级父块。</p>
              </div>
            </label>
            <label class="chunking-segment">
              <input v-model="parent_child.parent_mode" type="radio" value="full_document" />
              <div>
                <strong>全文</strong>
                <p>整篇文档作为一个父块；过长时可能截断（建议单篇控制体量）。</p>
              </div>
            </label>
          </div>

          <template v-if="parent_child.parent_mode === 'paragraph'">
            <div class="chunking-field-row chunking-field-row--tight chunking-field-row--two">
              <label class="field chunking-field chunking-field--id">
                <span class="field-label field-label--compact">
                  父·分段标识
                  <span
                    class="chunking-help"
                    title="父级段落切分使用的分隔符；支持 \\n 等转义。"
                    >?</span
                  >
                </span>
                <input v-model="parent_child.parent_delimiter" class="input input--chunk-tight" type="text" />
              </label>
              <label class="field chunking-field chunking-field--num">
                <span class="field-label field-label--compact">父·分段最大长度</span>
                <div class="chunking-number">
                  <input
                    v-model.number="parent_child.parent_max_length"
                    class="input input--chunk-tight chunking-number-input"
                    type="number"
                    min="100"
                    max="5000"
                  />
                  <span class="chunking-number-suffix">characters</span>
                </div>
              </label>
            </div>
          </template>

          <div class="chunking-subhead">子块用于检索</div>
          <div class="chunking-field-row chunking-field-row--tight">
            <label class="field chunking-field chunking-field--id">
              <span class="field-label field-label--compact">
                子·分段标识
                <span class="chunking-help" title="在父块内进一步切分子块时使用的分隔符。">?</span>
              </span>
              <input v-model="parent_child.child_delimiter" class="input input--chunk-tight" type="text" />
            </label>
            <label class="field chunking-field chunking-field--num">
              <span class="field-label field-label--compact">子·分段最大长度</span>
              <div class="chunking-number">
                <input
                  v-model.number="parent_child.child_max_length"
                  class="input input--chunk-tight chunking-number-input"
                  type="number"
                  min="100"
                  max="5000"
                />
                <span class="chunking-number-suffix">characters</span>
              </div>
            </label>
            <label class="field chunking-field chunking-field--num">
              <span class="field-label field-label--compact">子·分段重叠长度</span>
              <div class="chunking-number">
                <input
                  v-model.number="parent_child.child_overlap"
                  class="input input--chunk-tight chunking-number-input"
                  type="number"
                  min="0"
                  max="1000"
                />
                <span class="chunking-number-suffix">characters</span>
              </div>
            </label>
          </div>

          <div class="chunking-preprocess">
            <span class="field-label field-label--compact">文本预处理规则</span>
            <label class="chunking-check">
              <input v-model="parent_child.collapse_whitespace" type="checkbox" />
              替换掉连续的空格、换行符和制表符
            </label>
          </div>

          <div class="chunking-actions">
            <button
              class="btn btn-primary"
              type="button"
              :disabled="previewLoading"
              @click="openPreview('parent_child')"
            >
              <AppIcon name="search" :size="16" />
              预览块
            </button>
            <button class="btn btn-ghost" type="button" @click="resetForm('parent_child')">重置</button>
          </div>
        </div>
      </div>
    </div>
    </template>

    <div class="chunking-footer" v-if="expanded">
      <button class="btn btn-primary" type="button" :disabled="saving" @click="save">
        {{ saving ? '保存中…' : '保存分段设置' }}
      </button>
      <p v-if="message" :class="['chunking-message', messageType]">{{ message }}</p>
    </div>

    <div v-if="showPreview" class="modal-overlay" @click.self="closePreview">
      <div class="modal-card chunking-preview-modal">
        <div ref="previewRootRef" class="modal-header chunking-preview-header">
          <div>
            <h3>分段预览</h3>
          </div>
          <div class="chunking-preview-header-actions">
            <button class="btn btn-ghost btn-row-compact" type="button" @click="togglePreviewFullscreen">
              <AppIcon :name="isPreviewFullscreen ? 'fullscreen-exit' : 'fullscreen'" :size="16" />
              {{ isPreviewFullscreen ? '退出全屏' : '全屏' }}
            </button>
            <button class="icon-button chunking-preview-close" type="button" @click="closePreview">
              <AppIcon name="close" :size="16" />
            </button>
          </div>
        </div>
        <div class="modal-body">
          <div class="chunking-preview-toolbar">
            <label class="field chunking-preview-field">
              <span class="field-label">选择文档</span>
              <div class="file-select">
                <AppIcon name="folder" :size="18" class="file-select-icon" />
                <select
                  v-model.number="previewDocumentId"
                  class="select file-select-native"
                  :disabled="previewLoading || documentsLoading"
                >
                  <option :value="0">请选择一个文件…</option>
                  <option v-for="doc in previewDocuments" :key="doc.id" :value="doc.id">
                    {{ doc.document_name }}｜{{ doc.file_name }}
                  </option>
                </select>
              </div>
            </label>
            <button
              class="btn btn-primary"
              type="button"
              :disabled="previewLoading || !previewDocumentId"
              @click="runPreview"
            >
              {{ previewLoading ? '生成中…' : '生成预览' }}
            </button>
            <span v-if="previewResult && previewResult.total_chunks > 0" class="chip chip-brand chunking-preview-estimate">
              {{ previewResult.total_chunks }} 预估块
            </span>
          </div>

          <div v-if="previewError" class="status-box error">{{ previewError }}</div>

          <div v-if="previewResult" class="chunking-preview-compare">
            <section class="chunking-preview-pane">
              <div class="chunking-preview-pane-head">
                <strong>原文区间</strong>
                <span class="chip">来自：{{ previewResult.file_name }}</span>
                <span v-if="previewResult.excerpt_truncated" class="chip warn">原文展示已按长度截断</span>
              </div>
              <pre class="chunking-preview-excerpt">{{ previewResult.excerpt }}</pre>
            </section>
            <section class="chunking-preview-pane">
              <div class="chunking-preview-pane-head chunking-preview-chunks-head">
                <div>
                  <strong>切片结果</strong>
                  <p class="chunking-preview-sub">将用于嵌入和召回的切片段落</p>
                  <p v-if="previewResult.mode === 'parent_child'" class="chunking-preview-sub chunking-preview-hint">
                    C-1、C-2…：优先按子分隔符切段；若单段过长会在预览中再拆以便阅读。右侧「展示 a/b 块」为向量子块数。
                  </p>
                </div>
                <span class="chip">
                  展示
                  {{ previewResult.preview_chunk_count }}
                  /
                  {{ previewResult.total_chunks }}
                  块（上限 {{ previewMaxChunks }}）
                </span>
              </div>

              <div class="chunking-preview-chunks-toolbar">
                <div class="chunking-preview-tabs" role="tablist">
                  <button
                    type="button"
                    role="tab"
                    :class="['chunking-preview-tab', { active: previewChunkDisplayMode === 'full' }]"
                    @click="previewChunkDisplayMode = 'full'"
                  >
                    全文
                  </button>
                  <button
                    type="button"
                    role="tab"
                    :class="['chunking-preview-tab', { active: previewChunkDisplayMode === 'preview' }]"
                    @click="previewChunkDisplayMode = 'preview'"
                  >
                    省略
                  </button>
                </div>
                <label class="chunking-preview-search">
                  <AppIcon name="search" class="chunking-preview-search-icon" :size="16" />
                  <input
                    v-model.trim="previewChunkKeywordInput"
                    class="input chunking-preview-search-input"
                    type="search"
                    placeholder="搜索切片正文"
                    @keydown.enter.prevent="applyPreviewChunkKeyword"
                  />
                </label>
              </div>

              <div class="chunking-preview-list chunking-preview-chunk-list">
                <template v-if="previewResult.mode === 'parent_child' && filteredParentChildGroups.length">
                  <article
                    v-for="(grp, pi) in filteredParentChildGroups"
                    :key="'preview-parent-' + grp.parent_index + '-' + pi"
                    class="chunking-preview-item chunking-preview-parent-card"
                  >
                    <div class="chunking-preview-chunk-top">
                      <AppIcon name="grip" class="chunking-preview-chunk-grip" :size="16" />
                      <span class="chunking-preview-chunk-title"
                        >Chunk-{{ grp.parent_index + 1 }} · {{ grp.parent_char_count }} 字符</span
                      >
                      <span class="chunking-preview-parent-chip">父块</span>
                    </div>
                    <div class="chunking-preview-child-flow" role="list">
                      <span
                        v-for="(ch, ci) in grp.children"
                        :key="'preview-child-' + ch.chunk_index"
                        class="chunking-preview-child-chip"
                        role="listitem"
                        :title="`${ch.char_count} 字符`"
                      >
                        <span class="chunking-preview-child-chip-id">C-{{ ci + 1 }}</span>
                        <span class="chunking-preview-child-chip-text">{{ previewChunkDisplayText(ch.content) }}</span>
                      </span>
                    </div>
                  </article>
                </template>
                <template v-else>
                  <article
                    v-for="row in filteredPreviewChunks"
                    :key="'preview-chunk-' + row.chunkNo"
                    class="chunking-preview-item chunking-preview-chunk-card"
                  >
                    <div class="chunking-preview-chunk-top">
                      <AppIcon name="grip" class="chunking-preview-chunk-grip" :size="16" />
                      <span class="chunking-preview-chunk-title"
                        >Chunk-{{ row.chunkNo }} · {{ row.charCount }} 字符</span
                      >
                    </div>
                    <p class="chunking-preview-chunk-body">{{ previewChunkDisplayText(row.content) }}</p>
                  </article>
                </template>
              </div>
            </section>
          </div>

          <p v-else class="chunking-preview-empty">请选择一个文档并点击“生成预览”。</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" type="button" @click="closePreview">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'

import {
  getKnowledgeBaseErrorMessage,
  knowledgeBaseApi,
  type KnowledgeBase,
  type KnowledgeDocument,
  type KnowledgeDocumentChunkingPreviewResponse,
  type ParentChildPreviewGroupItem,
} from '../../api/knowledge-base'
import AppIcon from '../AppIcon.vue'
import {
  DEFAULT_CHUNKING,
  loadChunkingConfig,
  toStoredConfig,
  type ChunkingConfigStored,
  type ChunkingMode,
} from '../../types/chunking'

const props = defineProps<{
  knowledgeBase: KnowledgeBase
}>()

const emit = defineEmits<{
  saved: [KnowledgeBase]
}>()

const mode = ref<ChunkingMode>('general')
const expanded = ref(false)
const general = ref<ChunkingConfigStored['general']>({ ...DEFAULT_CHUNKING.general })
const parent_child = ref<ChunkingConfigStored['parent_child']>({ ...DEFAULT_CHUNKING.parent_child })
const saving = ref(false)
const message = ref('')
const messageType = ref<'ok' | 'err'>('ok')
const showPreview = ref(false)
const previewMode = ref<ChunkingMode>('general')
const previewLoading = ref(false)
const documentsLoading = ref(false)
const previewDocuments = ref<KnowledgeDocument[]>([])
const previewDocumentId = ref<number>(0)
const previewResult = ref<KnowledgeDocumentChunkingPreviewResponse | null>(null)
const previewError = ref('')
const previewRootRef = ref<HTMLElement | null>(null)
const isPreviewFullscreen = ref(false)
const previewMaxChunks = 40
const previewChunkDisplayMode = ref<'full' | 'preview'>('full')
const previewChunkKeyword = ref('')
const previewChunkKeywordInput = ref('')

function syncPreviewFullscreen() {
  const doc = window.document
  const fs =
    doc.fullscreenElement ||
    (doc as Document & { webkitFullscreenElement?: Element | null }).webkitFullscreenElement
  isPreviewFullscreen.value = fs === previewRootRef.value?.closest('.chunking-preview-modal')
}

function initFromKb(kb: KnowledgeBase) {
  const c = loadChunkingConfig(kb.config, kb.default_chunk_size, kb.default_chunk_overlap)
  mode.value = c.mode
  general.value = { ...c.general }
  parent_child.value = { ...c.parent_child }
  message.value = ''
}

watch(
  () => [props.knowledgeBase.id, props.knowledgeBase.updated_at] as const,
  () => {
    initFromKb(props.knowledgeBase)
  },
  { immediate: true },
)

function unescapeDelimiter(s: string) {
  return s.replace(/\\n/g, '\n').replace(/\\t/g, '\t').replace(/\\r/g, '\r')
}

function openPreview(target: ChunkingMode) {
  previewMode.value = target
  showPreview.value = true
  previewLoading.value = false
  previewError.value = ''
  previewResult.value = null
  previewDocumentId.value = 0
  void loadPreviewDocuments()
}

function closePreview() {
  showPreview.value = false
  previewLoading.value = false
  previewError.value = ''
  previewResult.value = null
  previewDocumentId.value = 0
  previewChunkDisplayMode.value = 'full'
  previewChunkKeyword.value = ''
  previewChunkKeywordInput.value = ''
  // 如果处于全屏，退出
  const doc = window.document
  const fs =
    doc.fullscreenElement ||
    (doc as Document & { webkitFullscreenElement?: Element | null }).webkitFullscreenElement
  if (fs) {
    const exit =
      doc.exitFullscreen?.bind(doc) ||
      (doc as Document & { webkitExitFullscreen?: () => void }).webkitExitFullscreen?.bind(doc)
    exit?.()
  }
}

function applyPreviewChunkKeyword() {
  previewChunkKeyword.value = previewChunkKeywordInput.value.trim()
}

type PreviewChunkRow = { content: string; chunkNo: number; charCount: number }

function previewChunkUnicodeLen(text: string): number {
  return [...text].length
}

const filteredPreviewChunks = computed((): PreviewChunkRow[] => {
  const chunks = previewResult.value?.chunks || []
  const kw = previewChunkKeyword.value.trim().toLowerCase()
  const rows: PreviewChunkRow[] = chunks.map((c, i) => ({
    content: c,
    chunkNo: i + 1,
    charCount: previewChunkUnicodeLen(c),
  }))
  if (!kw) {
    return rows
  }
  return rows.filter((row) => row.content.toLowerCase().includes(kw))
})

const filteredParentChildGroups = computed((): ParentChildPreviewGroupItem[] => {
  const groups = previewResult.value?.parent_child_groups
  if (!groups?.length) {
    return []
  }
  const kw = previewChunkKeyword.value.trim().toLowerCase()
  if (!kw) {
    return groups
  }
  return groups.filter((g) => {
    const inParent = (g.parent_preview || '').toLowerCase().includes(kw)
    const inChild = g.children.some((c) => c.content.toLowerCase().includes(kw))
    return inParent || inChild
  })
})

function previewChunkDisplayText(text: string) {
  if (previewChunkDisplayMode.value === 'full') {
    return text
  }
  const t = text.trim()
  if (t.length <= 180) {
    return t
  }
  return `${t.slice(0, 180)}…`
}

async function togglePreviewFullscreen() {
  const modal = previewRootRef.value?.closest('.chunking-preview-modal') as HTMLElement | null
  if (!modal) {
    return
  }
  const doc = window.document
  try {
    const fs =
      doc.fullscreenElement ||
      (doc as Document & { webkitFullscreenElement?: Element | null }).webkitFullscreenElement
    if (!fs) {
      const req =
        modal.requestFullscreen?.bind(modal) ||
        (modal as HTMLElement & { webkitRequestFullscreen?: () => void }).webkitRequestFullscreen?.bind(modal)
      if (req) {
        await Promise.resolve(req())
      }
    } else {
      const exit =
        doc.exitFullscreen?.bind(doc) ||
        (doc as Document & { webkitExitFullscreen?: () => void }).webkitExitFullscreen?.bind(doc)
      if (exit) {
        await Promise.resolve(exit())
      }
    }
  } catch {
    /* 浏览器拒绝全屏或不支持 */
  }
}

window.document.addEventListener('fullscreenchange', syncPreviewFullscreen)
window.document.addEventListener('webkitfullscreenchange', syncPreviewFullscreen)

onUnmounted(() => {
  window.document.removeEventListener('fullscreenchange', syncPreviewFullscreen)
  window.document.removeEventListener('webkitfullscreenchange', syncPreviewFullscreen)
})

async function loadPreviewDocuments() {
  if (!props.knowledgeBase?.id) {
    return
  }
  documentsLoading.value = true
  try {
    const res = await knowledgeBaseApi.listDocuments(props.knowledgeBase.id, { page: 1, page_size: 100 })
    previewDocuments.value = res.items
    if (!previewDocumentId.value && res.items.length > 0) {
      // listDocuments 默认按 created_at desc；这里选第一个即可视作“最近上传/更新”
      previewDocumentId.value = res.items[0].id
    }
  } catch (e) {
    previewError.value = getKnowledgeBaseErrorMessage(e, '加载文档列表失败')
  } finally {
    documentsLoading.value = false
  }
}

function buildCurrentChunkingConfig(): Record<string, unknown> {
  const current =
    previewMode.value === 'parent_child'
      ? { mode: 'parent_child', general: general.value, parent_child: parent_child.value }
      : { mode: 'general', general: general.value, parent_child: parent_child.value }
  return current as unknown as Record<string, unknown>
}

async function runPreview() {
  if (!props.knowledgeBase?.id || !previewDocumentId.value) {
    return
  }
  previewLoading.value = true
  previewError.value = ''
  previewResult.value = null
  previewChunkKeyword.value = ''
  previewChunkKeywordInput.value = ''
  previewChunkDisplayMode.value = 'full'
  try {
    previewResult.value = await knowledgeBaseApi.previewChunking(props.knowledgeBase.id, {
      document_id: previewDocumentId.value,
      chunking_config: buildCurrentChunkingConfig(),
      max_pages: 2,
      max_chars: 8000,
      max_chunks: previewMaxChunks,
    })
  } catch (e) {
    previewError.value = getKnowledgeBaseErrorMessage(e, '生成预览失败')
  } finally {
    previewLoading.value = false
  }
}
function resetForm(which: 'all' | ChunkingMode) {
  if (which === 'all' || which === 'general') {
    general.value = { ...DEFAULT_CHUNKING.general }
  }
  if (which === 'all' || which === 'parent_child') {
    parent_child.value = { ...DEFAULT_CHUNKING.parent_child }
  }
  if (which === 'all') {
    mode.value = 'general'
  }
  message.value = '已恢复为表单默认值，需点击「保存」才会同步到服务器。'
  messageType.value = 'ok'
}

function validate(): string | null {
  if (mode.value === 'general') {
    if (general.value.overlap >= general.value.max_length) {
      return '通用模式：分段重叠长度必须小于分段最大长度。'
    }
  } else {
    if (parent_child.value.child_overlap >= parent_child.value.child_max_length) {
      return '父子模式：子·分段重叠长度必须小于子·分段最大长度。'
    }
  }
  return null
}

async function save() {
  const err = validate()
  if (err) {
    message.value = err
    messageType.value = 'err'
    return
  }
  saving.value = true
  message.value = ''
  try {
    const stored = toStoredConfig({ mode: mode.value, general: general.value, parent_child: parent_child.value })
    const prev = (props.knowledgeBase.config || {}) as Record<string, unknown>
    const nextConfig = { ...prev, chunking: stored } as Record<string, unknown>
    const payload: {
      default_chunk_size: number
      default_chunk_overlap: number
      config: Record<string, unknown>
    } = {
      config: nextConfig,
      default_chunk_size: props.knowledgeBase.default_chunk_size,
      default_chunk_overlap: props.knowledgeBase.default_chunk_overlap,
    }
    if (mode.value === 'general') {
      payload.default_chunk_size = general.value.max_length
      payload.default_chunk_overlap = general.value.overlap
    } else {
      payload.default_chunk_size = parent_child.value.child_max_length
      payload.default_chunk_overlap = parent_child.value.child_overlap
    }
    const updated = await knowledgeBaseApi.update(props.knowledgeBase.id, payload)
    message.value = '分段设置已保存。'
    messageType.value = 'ok'
    emit('saved', updated)
  } catch (e) {
    message.value = getKnowledgeBaseErrorMessage(e, '保存失败')
    messageType.value = 'err'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.chunking-settings {
  display: grid;
  gap: 16px;
}

.chunking-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.chunking-title-row {
  display: grid;
  gap: 4px;
}

.chunking-title {
  margin: 0;
  font-size: 1.05rem;
  color: var(--text-primary);
}

.chunking-sub {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.chunking-toggle-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 32px;
  padding: 4px 12px;
  font-size: 0.85rem;
  border-radius: 10px;
}

.chunking-mode-list {
  display: grid;
  gap: 12px;
}

.chunking-card {
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 16px 18px;
  background: var(--bg-elevated);
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.chunking-card--active {
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 1px var(--brand-primary-light);
}

.chunking-card-head {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.chunking-radio {
  margin-top: 4px;
  accent-color: var(--brand-primary);
}

.chunking-card-title {
  font-weight: 600;
  color: var(--text-primary);
}

.chunking-card-desc {
  margin: 4px 0 0;
  font-size: 0.88rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.chunking-card-body {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
  display: grid;
  gap: 14px;
}

/* 单排：三列等宽；两列行用 .chunking-field-row--two */
.chunking-field-row--tight {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  align-items: end;
  width: 100%;
  min-width: 0;
}

.chunking-field-row--tight.chunking-field-row--two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.chunking-field-row--tight .chunking-field {
  min-width: 0;
}

.field-label--compact {
  font-size: 0.75rem;
  line-height: 1.25;
  color: var(--text-secondary);
}

.input--chunk-tight {
  min-height: 32px;
  padding: 5px 8px;
  font-size: 0.82rem;
  width: 100%;
  box-sizing: border-box;
}

.chunking-number {
  display: flex;
  align-items: stretch;
  width: 100%;
  min-width: 0;
}

.chunking-number-input {
  flex: 1 1 0;
  min-width: 0;
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}

.chunking-number-suffix {
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  font-size: 0.82rem;
  color: var(--text-tertiary);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-left: none;
  border-top-right-radius: 12px;
  border-bottom-right-radius: 12px;
  white-space: nowrap;
}

.chunking-field {
  display: grid;
  gap: 4px;
}

.chunking-subhead {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 4px 0 0;
}

.parent-mode-row {
  display: grid;
  gap: 8px;
}

.chunking-segment {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  cursor: pointer;
}

.chunking-segment input {
  margin-top: 4px;
  accent-color: var(--brand-primary);
}

.chunking-segment strong {
  display: block;
  color: var(--text-primary);
  font-size: 0.92rem;
}

.chunking-segment p {
  margin: 4px 0 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.45;
}

.chunking-preprocess {
  display: grid;
  gap: 8px;
}

.chunking-check {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 0.9rem;
  color: var(--text-secondary);
  cursor: pointer;
}

.chunking-check input {
  margin-top: 2px;
  accent-color: var(--brand-primary);
}

.chunking-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.chunking-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
}

.chunking-message {
  font-size: 0.9rem;
  margin: 0;
}

.chunking-message.ok {
  color: var(--success-color);
}

.chunking-message.err {
  color: var(--danger-color);
}

.chunking-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  margin-left: 4px;
  border-radius: 50%;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-tertiary);
  border: 1px solid var(--border-color);
  cursor: help;
  vertical-align: middle;
}

.chunking-preview-modal {
  max-width: 1120px;
  width: 100%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.chunking-preview-modal:fullscreen,
.chunking-preview-modal:-webkit-full-screen {
  max-width: 100vw;
  width: 100vw;
  max-height: 100vh;
  height: 100vh;
  border-radius: 0;
}

.chunking-preview-modal:fullscreen .modal-body,
.chunking-preview-modal:-webkit-full-screen .modal-body {
  overflow: hidden;
}

.chunking-preview-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.chunking-preview-estimate {
  flex-shrink: 0;
}

.chunking-preview-header {
  position: relative;
  padding-right: 120px;
}

.chunking-preview-header-actions {
  position: absolute;
  right: 12px;
  top: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.chunking-preview-close {
  position: static;
}

.chunking-preview-field {
  min-width: 280px;
  flex: 1 1 280px;
}

.file-select {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.file-select:focus-within {
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 2px var(--brand-primary-light);
  background: var(--bg-elevated);
}

.file-select-icon {
  flex: 0 0 auto;
  color: var(--text-tertiary);
}

.file-select-native {
  flex: 1 1 0;
  min-width: 0;
  border: none;
  background: transparent;
  padding: 0;
  font-size: 0.92rem;
  color: var(--text-primary);
  outline: none;
}

.file-select-native:disabled {
  opacity: 0.6;
}

.chunking-preview-compare {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 12px;
  min-height: 0;
}

@media (max-width: 980px) {
  .chunking-preview-compare {
    grid-template-columns: 1fr;
  }
}

.chunking-preview-pane {
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--bg-tertiary);
  padding: 12px;
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-rows: auto 1fr;
}

.chunking-preview-pane-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.chunking-preview-chunks-head {
  align-items: flex-start;
}

.chunking-preview-sub {
  margin: 4px 0 0;
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

.chunking-preview-hint {
  margin-top: 6px;
  font-size: 0.78rem;
  color: var(--text-tertiary);
  line-height: 1.45;
}

.chunking-preview-chunks-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 8px 0 10px;
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 10px;
}

.chunking-preview-tabs {
  display: inline-flex;
  gap: 6px;
  padding: 4px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
}

.chunking-preview-tab {
  border: none;
  background: transparent;
  padding: 6px 10px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.chunking-preview-tab.active {
  background: var(--bg-secondary);
  color: var(--text-primary);
  box-shadow: 0 6px 14px rgba(15, 23, 42, 0.06);
}

.chunking-preview-search {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
}

.chunking-preview-search-icon {
  position: absolute;
  left: 10px;
  color: var(--text-tertiary);
}

.chunking-preview-search-input {
  padding-left: 32px;
  min-width: 220px;
}

.chunking-preview-chunk-list {
  gap: 10px;
}

.chunking-preview-chunk-card {
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  display: grid;
  gap: 8px;
}

.chunking-preview-chunk-top {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: 0.78rem;
}

.chunking-preview-chunk-grip {
  flex-shrink: 0;
  opacity: 0.55;
  color: var(--text-tertiary);
}

.chunking-preview-chunk-title {
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--text-tertiary);
  letter-spacing: 0.01em;
}

/* 通用预览：父级标题略加重 */
.chunking-preview-chunk-card .chunking-preview-chunk-title {
  font-weight: 700;
  color: var(--text-secondary);
}

.chunking-preview-parent-card {
  display: grid;
  gap: 10px;
}

.chunking-preview-parent-card .chunking-preview-chunk-top {
  color: var(--text-secondary);
}

.chunking-preview-parent-card .chunking-preview-chunk-title {
  font-size: 0.84rem;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}

.chunking-preview-parent-chip {
  margin-left: auto;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.chunking-preview-child-flow {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 10px;
  align-items: flex-start;
  line-height: 1.55;
}

.chunking-preview-child-chip {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 8px;
  max-width: 100%;
  padding: 6px 10px 7px;
  border-radius: 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.04);
}

.chunking-preview-parent-card .chunking-preview-child-chip-id {
  flex-shrink: 0;
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.03em;
  color: var(--text-tertiary);
  opacity: 0.92;
}

.chunking-preview-child-chip-text {
  font-size: 0.84rem;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  min-width: 0;
}

.chunking-preview-chip {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.12);
  color: var(--success-color);
  border: 1px solid rgba(34, 197, 94, 0.18);
}

.chunking-preview-chunk-body {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.6;
  color: var(--text-primary);
  font-size: 0.88rem;
}

.chunking-preview-pane-head strong {
  color: var(--text-primary);
}

.chunking-preview-excerpt {
  margin: 0;
  white-space: pre-wrap;
  font-size: 0.88rem;
  line-height: 1.6;
  color: var(--text-primary);
  overflow: auto;
}

.chunking-preview-meta {
  font-size: 0.86rem;
  color: var(--text-secondary);
  margin: 0;
}

.chunking-preview-list {
  overflow: auto;
  display: grid;
  gap: 10px;
  margin-top: 0;
}

.chunking-preview-item {
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  display: grid;
  gap: 6px;
}

.chunking-preview-idx {
  font-size: 0.75rem;
  color: var(--text-tertiary);
  font-weight: 600;
}

.chunking-preview-item p {
  margin: 0;
  font-size: 0.88rem;
  color: var(--text-primary);
  white-space: pre-wrap;
  line-height: 1.5;
}

.chunking-preview-empty {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 0.9rem;
}
</style>
