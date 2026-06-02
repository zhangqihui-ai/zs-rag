<template>
  <div ref="rootEl" class="kb-select" :class="{ 'kb-select--open': open }">
    <button
      type="button"
      class="kb-select-trigger"
      :aria-expanded="open"
      aria-haspopup="listbox"
      :aria-label="triggerAriaLabel"
      @click.stop="toggleOpen"
    >
      <div class="kb-select-tags-wrap">
        <template v-if="selectedTags.length > 0">
          <span v-for="kb in selectedTags" :key="kb.id" class="kb-tag">
            <span class="kb-tag-dot" :style="{ background: kbAvatarColor(kb.id) }" aria-hidden="true">
              {{ kbInitial(kb) }}
            </span>
            <span class="kb-tag-text">{{ kb.name }}</span>
            <button
              type="button"
              class="kb-tag-remove"
              :aria-label="`移除 ${kb.name}`"
              @click.stop="removeKb(kb.id)"
            >
              ×
            </button>
          </span>
        </template>
        <span v-else class="kb-select-placeholder">{{ placeholder }}</span>
      </div>
      <AppIcon name="chevron-down" :size="16" class="kb-select-chevron" :class="{ 'is-open': open }" />
    </button>

    <Teleport to="body">
      <div
        v-if="open"
        ref="panelEl"
        class="kb-select-panel"
        :style="panelStyle"
        role="listbox"
        aria-multiselectable="true"
        @click.stop
      >
        <div class="kb-select-search">
          <AppIcon name="search" :size="16" class="kb-select-search-icon" />
          <input
            v-model="searchQuery"
            type="search"
            class="input kb-select-search-input"
            placeholder="搜索…"
            aria-label="搜索知识库"
            @keydown.escape.stop="closeWithoutSave"
          />
        </div>
        <div class="kb-select-list scrollbar-pill">
          <label
            v-for="kb in filteredKbs"
            :key="kb.id"
            class="kb-select-row"
            :class="{ 'is-checked': isSelected(kb.id) }"
          >
            <input type="checkbox" class="kb-select-check" :checked="isSelected(kb.id)" @change="toggleKb(kb.id)" />
            <span class="kb-row-dot" :style="{ background: kbAvatarColor(kb.id) }" aria-hidden="true">{{
              kbInitial(kb)
            }}</span>
            <span class="kb-row-text">
              <span class="kb-row-name">{{ kb.name }}</span>
              <span class="kb-row-embed" :title="embeddingLabelTitleForKb(kb)">{{ embeddingLabelForKb(kb) }}</span>
            </span>
          </label>
          <div v-if="filteredKbs.length === 0" class="kb-select-empty">无匹配知识库</div>
        </div>
        <div class="kb-select-footer">
          <button type="button" class="btn-text-inline" @click="clearDraft">清除</button>
          <button type="button" class="btn-text-inline btn-text-inline--primary" @click.stop="saveAndClose">保存</button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { KnowledgeBase } from '../../api/knowledge-base'
import { defaultModelApi, modelApi, type DefaultModelOption, type ModelItem } from '../../api/model-management'
import AppIcon from '../AppIcon.vue'

const props = withDefaults(
  defineProps<{
    modelValue: number[]
    knowledgeBases: KnowledgeBase[]
    /** 由父组件传入时已拉取的 embedding 列表时，避免组件内重复请求 */
    embeddingModels?: ModelItem[]
    embeddingSpaceDefault?: DefaultModelOption | null
    placeholder?: string
    triggerAriaLabel?: string
  }>(),
  {
    placeholder: '选择知识库…',
    triggerAriaLabel: '选择知识库',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: number[]]
}>()

const open = defineModel<boolean>('open', { default: false })

const rootEl = ref<HTMLElement | null>(null)
const panelEl = ref<HTMLElement | null>(null)
/** Teleport 到 body 的 fixed 浮层定位样式，避免被祖先 overflow 裁切 */
const panelStyle = ref<Record<string, string>>({})
/** 下拉内勾选仅改草稿，点「保存」再写回 modelValue */
const draftIds = ref<number[]>([])
const searchQuery = ref('')

function updatePanelPosition() {
  const trigger = rootEl.value
  if (!trigger) {
    return
  }
  const rect = trigger.getBoundingClientRect()
  const gap = 6
  const spaceBelow = window.innerHeight - rect.bottom - 12
  const spaceAbove = rect.top - 12
  const openBelow = spaceBelow >= 240 || spaceBelow >= spaceAbove
  const maxHeight = Math.max(180, Math.min(360, openBelow ? spaceBelow : spaceAbove))
  const style: Record<string, string> = {
    position: 'fixed',
    left: `${Math.round(rect.left)}px`,
    width: `${Math.round(rect.width)}px`,
    right: 'auto',
    maxHeight: `${Math.round(maxHeight)}px`,
    zIndex: '1000',
  }
  if (openBelow) {
    style.top = `${Math.round(rect.bottom + gap)}px`
  } else {
    style.top = `${Math.round(rect.top - gap - maxHeight)}px`
  }
  panelStyle.value = style
}
const internalEmbeddingModels = ref<ModelItem[]>([])
const internalEmbeddingDefault = ref<DefaultModelOption | null>(null)

const embeddingList = computed(() =>
  props.embeddingModels !== undefined ? props.embeddingModels : internalEmbeddingModels.value,
)

const embeddingDefaultEffective = computed(() =>
  props.embeddingSpaceDefault !== undefined ? props.embeddingSpaceDefault : internalEmbeddingDefault.value,
)

const embeddingModelById = computed(() => {
  const m = new Map<number, ModelItem>()
  for (const item of embeddingList.value) {
    m.set(item.id, item)
  }
  return m
})

function embeddingLabelForKb(kb: KnowledgeBase): string {
  const labelFromSyncedModel = (id: number): string | null => {
    const model = embeddingModelById.value.get(id)
    if (model) {
      return `${model.model_name}@${model.provider_name}`
    }
    return null
  }
  if (kb.embedding_model_id != null) {
    const synced = labelFromSyncedModel(kb.embedding_model_id)
    if (synced) {
      return synced
    }
    return `模型 #${kb.embedding_model_id}`
  }
  const d = embeddingDefaultEffective.value
  if (d) {
    const synced = labelFromSyncedModel(d.model_id)
    if (synced) {
      return synced
    }
    return `${d.model_name}@${d.provider_name}`
  }
  const first = embeddingList.value[0]
  if (first) {
    return `${first.model_name}@${first.provider_name}`
  }
  return '暂无可用 Embedding'
}

function embeddingLabelTitleForKb(kb: KnowledgeBase): string | undefined {
  if (kb.embedding_model_id != null) {
    return undefined
  }
  return '知识库未单独指定向量模型，使用工作区默认 Embedding（若未设置默认则取首个可用模型）'
}

const filteredKbs = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const list = props.knowledgeBases.filter((kb) => kb.status === 'active')
  if (!q) {
    return list
  }
  return list.filter((kb) => {
    if (kb.name.toLowerCase().includes(q)) {
      return true
    }
    return embeddingLabelForKb(kb).toLowerCase().includes(q)
  })
})

const selectedTags = computed(() => {
  const ids = open.value ? new Set(draftIds.value) : new Set(props.modelValue)
  if (ids.size === 0) {
    return []
  }
  return props.knowledgeBases.filter((kb) => ids.has(kb.id))
})

function kbInitial(kb: KnowledgeBase): string {
  const s = kb.name.trim() || '?'
  return s.slice(0, 1).toUpperCase()
}

function kbAvatarColor(kbId: number): string {
  const hue = (kbId * 53) % 360
  return `hsl(${hue} 48% 44%)`
}

function isSelected(kbId: number): boolean {
  return open.value ? draftIds.value.includes(kbId) : props.modelValue.includes(kbId)
}

function toggleKb(kbId: number) {
  if (!open.value) {
    return
  }
  const s = new Set(draftIds.value)
  if (s.has(kbId)) {
    s.delete(kbId)
  } else {
    s.add(kbId)
  }
  draftIds.value = Array.from(s)
}

function removeKb(kbId: number) {
  if (open.value) {
    if (!draftIds.value.includes(kbId)) {
      return
    }
    toggleKb(kbId)
    return
  }
  if (!props.modelValue.includes(kbId)) {
    return
  }
  const s = new Set(props.modelValue)
  s.delete(kbId)
  emit('update:modelValue', Array.from(s))
}

function clearDraft() {
  draftIds.value = []
}

function saveAndClose() {
  emit('update:modelValue', [...draftIds.value])
  open.value = false
  searchQuery.value = ''
}

function closeWithoutSave() {
  open.value = false
  searchQuery.value = ''
}

function toggleOpen() {
  open.value = !open.value
}

function onDocumentClick(ev: MouseEvent) {
  if (!open.value) {
    return
  }
  const t = ev.target as Node | null
  if (t && (rootEl.value?.contains(t) || panelEl.value?.contains(t))) {
    return
  }
  saveAndClose()
}

function onReposition() {
  if (open.value) {
    updatePanelPosition()
  }
}

watch(open, (v) => {
  if (v) {
    draftIds.value = [...props.modelValue]
    void nextTick(() => {
      updatePanelPosition()
      document.addEventListener('click', onDocumentClick)
      window.addEventListener('resize', onReposition)
      window.addEventListener('scroll', onReposition, true)
    })
  } else {
    document.removeEventListener('click', onDocumentClick)
    window.removeEventListener('resize', onReposition)
    window.removeEventListener('scroll', onReposition, true)
    searchQuery.value = ''
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  window.removeEventListener('resize', onReposition)
  window.removeEventListener('scroll', onReposition, true)
})

onMounted(async () => {
  if (props.embeddingModels !== undefined) {
    return
  }
  try {
    const res = await modelApi.getModels({
      view: 'flat',
      model_type: 'embedding',
      is_enabled: true,
    })
    internalEmbeddingModels.value = (res as ModelItem[]) ?? []
  } catch {
    internalEmbeddingModels.value = []
  }
  try {
    const data = await defaultModelApi.getDefaults()
    internalEmbeddingDefault.value = data.embedding ?? null
  } catch {
    internalEmbeddingDefault.value = null
  }
})
</script>

<style scoped>
.kb-select {
  position: relative;
  z-index: 1;
}

.kb-select--open {
  z-index: 12;
}

.kb-select-trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 46px;
  padding: 8px 12px;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.kb-select-trigger:hover {
  border-color: var(--border-strong);
  background: var(--bg-secondary);
}

.kb-select--open .kb-select-trigger {
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 3px var(--brand-primary-light);
}

.kb-select-tags-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex: 1;
  min-width: 0;
  align-items: center;
}

.kb-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 100%;
  padding: 3px 6px 3px 4px;
  border-radius: 999px;
  background: var(--brand-primary-light);
  border: 1px solid rgba(37, 99, 235, 0.28);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
}

.kb-tag-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 999px;
  font-size: 0.65rem;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
}

.kb-tag-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}

.kb-tag-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  margin-left: 1px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.kb-tag-remove:hover {
  background: rgba(37, 99, 235, 0.15);
  color: var(--brand-primary);
}

.kb-select-placeholder {
  font-size: 0.9rem;
  color: var(--text-quaternary);
}

.kb-select-chevron {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform 0.2s ease;
}

.kb-select-chevron.is-open {
  transform: rotate(180deg);
}

.kb-select-panel {
  position: fixed;
  display: flex;
  flex-direction: column;
  max-height: min(360px, 52vh);
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.12);
  overflow: hidden;
}

.kb-select-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.kb-select-search-icon {
  flex-shrink: 0;
  color: var(--text-tertiary);
}

.kb-select-search-input {
  flex: 1;
  min-width: 0;
  min-height: 38px;
  padding: 0 10px;
  border-radius: 10px;
}

.kb-select-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 6px;
}

.kb-select-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 10px;
  margin-bottom: 4px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.kb-select-row:hover {
  background: var(--bg-tertiary);
}

.kb-select-row.is-checked {
  background: var(--brand-primary-light);
}

.kb-select-check {
  margin-top: 4px;
  flex-shrink: 0;
}

.kb-row-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 10px;
  font-size: 0.75rem;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
}

.kb-row-text {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 10px;
  min-width: 0;
  flex: 1;
}

.kb-row-name {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
  word-break: break-word;
}

.kb-row-embed {
  display: inline-block;
  max-width: 100%;
  padding: 2px 8px;
  border-radius: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  font-size: 0.72rem;
  font-weight: 500;
  color: var(--text-secondary);
  word-break: break-all;
}

.kb-select-empty {
  padding: 20px 12px;
  text-align: center;
  font-size: 0.88rem;
  color: var(--text-tertiary);
}

.kb-select-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 10px 12px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.btn-text-inline {
  border: none;
  background: none;
  padding: 4px 8px;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--brand-primary);
  cursor: pointer;
  border-radius: 6px;
}

.btn-text-inline:hover:not(:disabled) {
  background: rgba(37, 99, 235, 0.08);
}

.btn-text-inline--primary {
  font-weight: 700;
  color: var(--brand-primary);
}
</style>
