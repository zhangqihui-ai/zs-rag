<template>
  <aside class="graph-node-drawer" :class="{ open: Boolean(detail) }">
    <div class="graph-node-drawer-head">
      <h4>节点详情</h4>
      <button class="icon-button" type="button" aria-label="关闭详情" @click="$emit('close')">
        <AppIcon name="close" :size="16" />
      </button>
    </div>

    <div v-if="loading" class="graph-node-drawer-body">
      <p class="graph-node-muted">加载中…</p>
    </div>

    <div v-else-if="error" class="graph-node-drawer-body">
      <p class="graph-node-error">{{ error }}</p>
    </div>

    <div v-else-if="detail" class="graph-node-drawer-body">
      <div class="graph-node-field">
        <span class="graph-node-label">名称</span>
        <strong>{{ detail.label }}</strong>
      </div>
      <div class="graph-node-field">
        <span class="graph-node-label">ID</span>
        <code class="graph-node-code">{{ detail.id }}</code>
      </div>
      <div v-if="detail.entity_type" class="graph-node-field">
        <span class="graph-node-label">entity_type</span>
        <span class="chip chip-brand">{{ detail.entity_type }}</span>
      </div>
      <div v-if="detail.file_path" class="graph-node-field">
        <span class="graph-node-label">file_path</span>
        <button
          v-if="detail.document_id"
          type="button"
          class="graph-node-link"
          @click="openDocument"
        >
          {{ detail.file_path }}
        </button>
        <span v-else class="graph-node-value">{{ detail.file_path }}</span>
      </div>
      <div v-if="detail.created_at" class="graph-node-field">
        <span class="graph-node-label">created_at</span>
        <span class="graph-node-value">{{ detail.created_at }}</span>
      </div>
      <div v-if="detail.description" class="graph-node-field">
        <span class="graph-node-label">description</span>
        <p class="graph-node-description">{{ detail.description }}</p>
      </div>
      <div v-if="detail.source_id" class="graph-node-field">
        <span class="graph-node-label">source_id</span>
        <button
          v-if="detail.document_id"
          type="button"
          class="graph-node-link"
          @click="openDocument"
        >
          {{ detail.source_id }}
        </button>
        <span v-else class="graph-node-value">{{ detail.source_id }}</span>
      </div>
      <div v-if="detail.tags && detail.tags.length > 0" class="graph-node-field">
        <span class="graph-node-label">标签</span>
        <div class="graph-node-tags">
          <span v-for="tag in detail.tags" :key="tag" class="chip">{{ tag }}</span>
        </div>
      </div>
      <div class="graph-node-field">
        <span class="graph-node-label">度数</span>
        <span class="graph-node-value">{{ detail.degree }}</span>
      </div>
    </div>

    <div v-else class="graph-node-drawer-body">
      <p class="graph-node-muted">点击画布中的节点查看详情</p>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

import type { GraphNodeDetail } from '../../api/graph-knowledge-base'
import AppIcon from '../AppIcon.vue'

const props = defineProps<{
  kbId: number
  detail: GraphNodeDetail | null
  loading?: boolean
  error?: string
}>()

defineEmits<{
  close: []
}>()

const router = useRouter()

function openDocument() {
  if (!props.detail?.document_id) {
    return
  }
  router.push({
    name: 'knowledge-document-detail',
    params: {
      kbId: String(props.kbId),
      docId: String(props.detail.document_id),
    },
  })
}
</script>

<style scoped>
.graph-node-drawer {
  display: flex;
  flex-direction: column;
  width: 300px;
  flex-shrink: 0;
  border-left: 1px solid var(--border-color);
  background: var(--bg-elevated);
  min-height: 0;
  align-self: stretch;
}

.graph-node-drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-color);
}

.graph-node-drawer-head h4 {
  margin: 0;
  font-size: 0.95rem;
}

.graph-node-drawer-body {
  flex: 1;
  overflow: auto;
  padding: 14px 16px;
  display: grid;
  gap: 14px;
}

.graph-node-field {
  display: grid;
  gap: 6px;
}

.graph-node-label {
  font-size: 0.78rem;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.graph-node-value,
.graph-node-description {
  margin: 0;
  font-size: 0.88rem;
  color: var(--text-secondary);
  line-height: 1.55;
  word-break: break-word;
}

.graph-node-code {
  font-size: 0.82rem;
  word-break: break-all;
}

.graph-node-link {
  padding: 0;
  border: none;
  background: none;
  color: var(--brand-primary);
  text-align: left;
  cursor: pointer;
  font-size: 0.88rem;
  word-break: break-all;
}

.graph-node-link:hover {
  text-decoration: underline;
}

.graph-node-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.graph-node-muted {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 0.88rem;
}

.graph-node-error {
  margin: 0;
  color: var(--danger-color);
  font-size: 0.88rem;
}
</style>
