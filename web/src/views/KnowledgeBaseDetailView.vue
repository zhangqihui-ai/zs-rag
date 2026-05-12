<template>
  <Layout>
    <div class="page-shell knowledge-detail-view">
      <div v-if="notice.text" :class="['notice-bar', notice.type]">
        <AppIcon :name="notice.type === 'error' ? 'status' : 'check'" :size="16" />
        <p>{{ notice.text }}</p>
      </div>

      <div v-if="loading" class="surface-card loading-skeleton panel-skeleton"></div>

      <div v-else-if="error" class="surface-card error-panel">
        <div>
          <h3>知识库详情加载失败</h3>
          <p>{{ error }}</p>
        </div>
        <div class="action-row">
          <router-link to="/knowledge-bases" class="btn btn-ghost">返回列表</router-link>
          <button class="btn btn-secondary" type="button" @click="loadPage">重试</button>
        </div>
      </div>

      <template v-else-if="knowledgeBase">
        <div class="knowledge-detail-layout">
          <aside class="detail-sidebar">
            <section class="surface-card section-nav-card">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                type="button"
                :class="['section-nav-item', { active: activeTab === tab.key }]"
                @click="activeTab = tab.key"
              >
                <span class="section-nav-icon">
                  <AppIcon :name="tab.icon" :size="16" />
                </span>
                <span class="section-nav-copy">
                  <strong>{{ tab.label }}</strong>
                  <small>{{ tab.caption }}</small>
                </span>
              </button>
            </section>
          </aside>

          <section class="detail-main">
            <section v-if="activeTab === 'documents'" class="surface-card content-card">
              <div class="section-heading">
                <div>
                  <h3>文件列表</h3>
                  <p>查看当前知识库中的文档、处理状态与分块情况。</p>
                </div>
                <div class="toolbar-row toolbar-actions">
                  <button class="btn btn-secondary" type="button" @click="refreshDocuments">
                    <AppIcon name="refresh" :size="16" />
                    刷新
                  </button>
                  <button class="btn btn-primary" type="button" @click="openUploadModal">
                    <AppIcon name="plus" :size="16" />
                    新增文件
                  </button>
                </div>
              </div>

              <div class="toolbar-row documents-toolbar">
                <label class="field toolbar-field toolbar-field-search">
                  <span class="field-label">搜索</span>
                  <div class="input-wrap">
                    <AppIcon name="search" class="input-icon" :size="16" />
                    <input v-model.trim="documentKeyword" class="input" type="text" placeholder="按文档名称搜索" />
                  </div>
                </label>

                <label class="field toolbar-field">
                  <span class="field-label">状态</span>
                  <select v-model="documentStatusFilter" class="select">
                    <option value="all">全部</option>
                    <option value="uploaded">待解析</option>
                    <option value="parsing">解析中</option>
                    <option value="chunking">分块中</option>
                    <option value="indexing">索引中</option>
                    <option value="indexed">已完成</option>
                    <option value="failed">失败</option>
                  </select>
                </label>

                <label class="field toolbar-field">
                  <span class="field-label">排序</span>
                  <select v-model="sortOrder" class="select">
                    <option value="newest">上传时间：最新优先</option>
                    <option value="oldest">上传时间：最早优先</option>
                    <option value="name">名称：A-Z</option>
                  </select>
                </label>
              </div>

              <div v-if="documentsLoading" class="loading-skeleton document-skeleton"></div>

              <EmptyState
                v-else-if="filteredDocuments.length === 0"
                :title="documents.length === 0 ? '还没有文档' : '没有匹配的文档'"
                :description="documents.length === 0 ? '上传文件后，点击「开始解析」完成分块与向量索引。' : '请调整搜索关键词或筛选条件。'"
              >
                <template #icon>
                  <AppIcon name="folder" :size="20" />
                </template>
                <template #actions>
                  <button v-if="documents.length === 0" class="btn btn-primary" type="button" @click="openUploadModal">
                    <AppIcon name="plus" :size="16" />
                    添加文件
                  </button>
                </template>
              </EmptyState>

              <template v-else>
                <div class="document-table document-table-head">
                  <span>名称</span>
                  <span>上传时间</span>
                  <span>来源</span>
                  <span>状态</span>
                  <span>分块数</span>
                  <span>解析器</span>
                  <span class="table-actions-head">动作</span>
                </div>

                <div class="document-table-body">
                  <article v-for="document in filteredDocuments" :key="document.id" class="document-row">
                    <div
                      class="document-main-cell doc-preview-trigger"
                      title="点击查看原文与切片"
                      role="button"
                      tabindex="0"
                      @click="goToDocumentDetail(document)"
                      @keydown.enter.prevent="goToDocumentDetail(document)"
                      @keydown.space.prevent="goToDocumentDetail(document)"
                    >
                      <strong>{{ document.document_name }}</strong>
                      <p>{{ document.file_name }}</p>
                    </div>
                    <span class="document-meta-cell">{{ formatDate(document.created_at) }}</span>
                    <span class="document-meta-cell">{{ formatSource(document) }}</span>
                    <span>
                      <span :class="['status-pill', statusToneMap[document.status] || 'info']">
                        {{ statusLabelMap[document.status] || document.status }}
                      </span>
                    </span>
                    <span class="document-meta-cell">{{ document.chunk_count }}</span>
                    <span class="document-meta-cell">{{ document.parser_type.toUpperCase() }}</span>
                    <div class="row-actions document-row-actions">
                      <template v-if="['parsing', 'chunking', 'indexing'].includes(document.status)">
                        <span class="row-actions-muted">处理中…</span>
                      </template>
                      <template v-else>
                        <button
                          v-if="document.status === 'uploaded' || document.status === 'failed'"
                          class="btn btn-primary btn-row btn-row-compact"
                          type="button"
                          :disabled="processingDocumentIds.includes(document.id)"
                          @click="parseDocumentAction(document.id)"
                        >
                          {{ processingDocumentIds.includes(document.id) ? '解析中…' : document.status === 'failed' ? '重新解析' : '开始解析' }}
                        </button>
                        <button
                          v-if="document.status === 'indexed'"
                          class="btn btn-ghost btn-row btn-row-compact"
                          type="button"
                          :disabled="processingDocumentIds.includes(document.id)"
                          @click="reindexDocumentAction(document.id)"
                        >
                          {{ processingDocumentIds.includes(document.id) ? '重建中…' : '重建索引' }}
                        </button>
                      </template>
                      <button
                        v-if="parseLogVisibleFor(document)"
                        type="button"
                        class="parse-log-dot-btn"
                        :title="parseLogDotTitle(document)"
                        :aria-label="parseLogDotTitle(document)"
                        @click.stop="openParseLogModal(document)"
                      >
                        <span class="parse-log-dot" :class="parseLogDotClass(document)" />
                      </button>
                      <button
                        class="btn btn-danger btn-row btn-row-compact"
                        type="button"
                        :disabled="deletingDocumentIds.includes(document.id)"
                        @click="deleteDocumentAction(document.id)"
                      >
                        {{ deletingDocumentIds.includes(document.id) ? '删除中...' : '删除' }}
                      </button>
                      <div class="kebab-menu" @click.stop>
                        <button
                          class="btn btn-ghost btn-row btn-row-compact kebab-trigger"
                          type="button"
                          :disabled="processingDocumentIds.includes(document.id)"
                          :aria-expanded="openChunkingMenuForId === document.id"
                          aria-haspopup="menu"
                          :title="documentChunkingTitle(document)"
                          @click="toggleChunkingMenu(document.id)"
                        >
                          …
                          <span class="sr-only">分段设置</span>
                        </button>
                        <div
                          v-if="openChunkingMenuForId === document.id"
                          class="kebab-popover"
                          role="menu"
                          aria-label="分段设置"
                        >
                          <div class="kebab-title">分段设置</div>
                          <button
                            class="kebab-item"
                            type="button"
                            role="menuitemradio"
                            :aria-checked="documentChunkingMode(document) === 'inherit'"
                            @click="setDocumentChunkingMode(document, 'inherit')"
                          >
                            <span>跟随知识库</span>
                            <span v-if="documentChunkingMode(document) === 'inherit'" class="kebab-check">✓</span>
                          </button>
                          <button
                            class="kebab-item"
                            type="button"
                            role="menuitemradio"
                            :aria-checked="documentChunkingMode(document) === 'general'"
                            @click="setDocumentChunkingMode(document, 'general')"
                          >
                            <span>通用分段</span>
                            <span v-if="documentChunkingMode(document) === 'general'" class="kebab-check">✓</span>
                          </button>
                          <button
                            class="kebab-item"
                            type="button"
                            role="menuitemradio"
                            :aria-checked="documentChunkingMode(document) === 'parent_child'"
                            @click="setDocumentChunkingMode(document, 'parent_child')"
                          >
                            <span>父子分段</span>
                            <span v-if="documentChunkingMode(document) === 'parent_child'" class="kebab-check">✓</span>
                          </button>
                        </div>
                      </div>
                    </div>
                    <div v-if="document.error_message" class="document-row-error status-box error">
                      {{ document.error_message }}
                    </div>
                  </article>
                </div>
              </template>
            </section>

            <section v-else-if="activeTab === 'retrieval'" class="surface-card content-card retrieval-card">
              <div class="section-heading">
                <div>
                  <h3>检索测试</h3>
                  <p>快速验证当前知识库的召回效果与默认检索模式。</p>
                </div>
              </div>

              <div class="retrieval-layout">
                <form class="retrieval-form retrieval-panel retrieval-panel--left" @submit.prevent="submitSearch">
                  <div class="retrieval-query-block">
                    <label class="field retrieval-search-field">
                      <span class="field-label retrieval-query-label">检索问题</span>
                      <textarea
                        v-model.trim="searchQuery"
                        class="textarea"
                        rows="4"
                        placeholder="例如：合同审批流程需要哪些材料？"
                      ></textarea>
                    </label>
                    <div class="retrieval-query-actions">
                      <button class="btn btn-primary" type="submit" :disabled="searching || !searchQuery">
                        {{ searching ? '检索中...' : '开始检索' }}
                      </button>
                    </div>
                  </div>

                  <RetrievalConfigForm v-model="searchForm" />

                  <div class="retrieval-submit-row">
                    <button class="btn btn-ghost" type="button" :disabled="searching" @click="resetSearchForm">
                      还原为知识库默认
                    </button>
                  </div>
                </form>

                <div class="retrieval-panel retrieval-panel--right">
                  <div class="retrieval-result-head">
                    <div class="retrieval-result-head-title">
                      <h4>检索结果</h4>
                      <p v-if="!searchResults && !searching && !searchError">
                        输入问题并点击「开始检索」以查看召回片段。
                      </p>
                    </div>
                    <div v-if="searchResults" class="retrieval-result-meta">
                      <span class="chip chip-brand">{{ retrievalModeLabelMap[searchResults.mode] }}</span>
                      <span class="chip">共 {{ searchResults.total }} 条结果</span>
                    </div>
                  </div>

                  <div class="retrieval-result-body">
                    <div v-if="searching" class="loading-skeleton document-skeleton"></div>
                    <div v-else-if="searchError" class="status-box error">{{ searchError }}</div>
                    <EmptyState
                      v-else-if="!searchResults || searchResults.results.length === 0"
                      title="暂无检索结果"
                      description="输入一个问题后即可查看召回片段。"
                      compact
                    >
                      <template #icon>
                        <AppIcon name="retrieval" :size="18" />
                      </template>
                    </EmptyState>
                    <div v-else class="search-result-list">
                      <article
                        v-for="result in searchResults.results"
                        :key="result.chunk_uid"
                        class="search-result-card"
                      >
                        <div class="search-result-header">
                          <strong>{{ result.document_name }}</strong>
                          <span class="chip">Score {{ formatScore(result.score) }}</span>
                        </div>
                        <p>{{ result.content }}</p>
                        <div class="search-result-meta-row">
                          <span>Chunk #{{ result.chunk_index }}</span>
                          <span v-if="result.citation.page_no">页码 {{ result.citation.page_no }}</span>
                          <span
                            v-if="
                              searchResults?.mode === 'hybrid' &&
                              (result.vector_score != null || result.keyword_score != null)
                            "
                          >
                            向量 {{ formatScore(result.vector_score ?? 0) }} · 全文
                            {{ formatScore(result.keyword_score ?? 0) }}
                          </span>
                        </div>
                      </article>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section v-else-if="activeTab === 'logs'" class="surface-card content-card">
              <div class="section-heading">
                <div>
                  <h3>处理日志</h3>
                  <p>基于当前文档状态汇总最近活动，便于快速排查问题。</p>
                </div>
              </div>

              <EmptyState v-if="activityItems.length === 0" title="暂无日志" description="上传文档后会在这里展示最近处理活动。" compact>
                <template #icon>
                  <AppIcon name="clock" :size="18" />
                </template>
              </EmptyState>

              <div v-else class="activity-list">
                <article v-for="item in activityItems" :key="item.id" class="activity-card">
                  <div class="activity-header">
                    <div>
                      <strong>{{ item.title }}</strong>
                      <p>{{ item.time }}</p>
                    </div>
                    <span :class="['status-pill', item.tone]">{{ item.status }}</span>
                  </div>
                  <p class="activity-message">{{ item.message }}</p>
                </article>
              </div>
            </section>

            <section v-else class="surface-card content-card">
              <div class="section-heading">
                <div>
                  <h3>知识库配置</h3>
                </div>
              </div>

              <div class="pdf-parser-section">
                <div class="pdf-parser-row">
                  <h4 class="pdf-parser-label">Embedding 模型</h4>
                  <div class="pdf-parser-field">
                    <div class="custom-select-wrap pdf-parser-select-wrap">
                      <select
                        v-if="!embeddingModelsLoading"
                        class="custom-select"
                        :value="knowledgeBase?.embedding_model_id ?? ''"
                        :disabled="savingEmbeddingModel"
                        @change="(e) => saveEmbeddingModel((e.target as HTMLSelectElement).value ? Number((e.target as HTMLSelectElement).value) : null)"
                      >
                        <option value="">
                          默认{{ defaultEmbeddingModel ? `（${defaultEmbeddingModel.model_name}）` : '' }}
                        </option>
                        <option
                          v-for="model in embeddingModels"
                          :key="model.id"
                          :value="model.id"
                        >
                          {{ model.model_name }}（{{ model.provider_name }}）
                        </option>
                      </select>
                      <span v-else class="embedding-model-loading">加载中…</span>
                      <span class="custom-select-arrow">
                        <AppIcon name="chevron-down" :size="14" />
                      </span>
                    </div>
                    <span v-if="savingEmbeddingModel" class="embedding-model-saving">保存中…</span>
                  </div>
                </div>
              </div>

              <div class="pdf-parser-section">
                <div class="pdf-parser-row">
                  <h4 class="pdf-parser-label">PDF 解析器</h4>
                  <div class="pdf-parser-field">
                    <div class="custom-select-wrap pdf-parser-select-wrap">
                      <select
                        class="custom-select"
                        :value="pdfParser"
                        :disabled="savingPdfParser"
                        @change="onPdfParserChange($event)"
                      >
                        <option value="mineru">MinerU（推荐）</option>
                        <option value="docling">Docling（即将支持）</option>
                      </select>
                      <span class="custom-select-arrow">
                        <AppIcon name="chevron-down" :size="14" />
                      </span>
                    </div>
                    <span v-if="savingPdfParser" class="embedding-model-saving">保存中…</span>
                  </div>
                </div>
                <div v-if="pdfParser === 'docling'" class="embedding-model-warning">
                  <AppIcon name="status" :size="14" />
                  <span>Docling 引擎尚未上线，当前仍使用 MinerU 完成 PDF 与图片解析；功能就绪后会自动切换。</span>
                </div>
              </div>

              <ChunkingSettingsPanel
                v-if="knowledgeBase"
                :knowledge-base="knowledgeBase"
                @saved="onChunkingSettingsSaved"
              />

              <RetrievalSettingsPanel
                v-if="knowledgeBase"
                :knowledge-base="knowledgeBase"
                @saved="onRetrievalSettingsSaved"
              />

              <div class="data-list kb-config-follow">
                <div class="data-row">
                  <div class="data-row-label">
                    <strong>当前默认分块（用于索引）</strong>
                    <span>与上方「通用」或「父子-子块」中保存的最大长度/重叠一致</span>
                  </div>
                  <div class="data-row-value">
                    {{ knowledgeBase.default_chunk_size }} / {{ knowledgeBase.default_chunk_overlap }}（字符）
                  </div>
                </div>
                <div class="data-row">
                  <div class="data-row-label">
                    <strong>能力开关</strong>
                    <span>当前知识库已启用的扩展能力</span>
                  </div>
                  <div class="feature-chip-row">
                    <span :class="['chip', knowledgeBase.vector_db_enabled ? 'chip-brand' : '']">向量检索</span>
                    <span :class="['chip', knowledgeBase.graph_db_enabled ? 'chip-brand' : '']">图谱能力</span>
                  </div>
                </div>
              </div>
            </section>
          </section>
        </div>
      </template>

      <div v-if="showUploadModal" class="modal-overlay" @click.self="closeUploadModal">
        <div class="modal-card upload-modal">
          <div class="modal-header">
            <div>
              <h3>上传文件</h3>
              <p>{{ knowledgeBase?.name || '当前知识库' }} · 支持 txt / md / pdf / docx / csv / Excel（xls、xlsx）。</p>
            </div>
            <button class="icon-button" type="button" @click="closeUploadModal">
              <AppIcon name="close" :size="16" />
            </button>
          </div>

          <div class="modal-body upload-modal-body">
            <input
              ref="fileInputRef"
              class="hidden-file-input"
              type="file"
              accept=".txt,.md,.pdf,.docx,.csv,.xls,.xlsx,.xlsm"
              @change="handleFileChange"
            />

            <button
              type="button"
              :class="['upload-dropzone', { dragging: isDragOver }]"
              @click="openNativeFilePicker"
              @dragover.prevent="isDragOver = true"
              @dragleave.prevent="isDragOver = false"
              @drop.prevent="handleFileDrop"
            >
              <span class="upload-dropzone-icon">
                <AppIcon name="plus" :size="22" />
              </span>
              <strong>点击或拖拽文件到此处上传</strong>
              <p>单次上传 1 个文件；支持 txt、md、pdf、docx、csv、Excel（xls / xlsx / xlsm）。旧版 Word（.doc）请另存为 docx。</p>
            </button>

            <div v-if="uploadFile" class="selected-file-card">
              <div>
                <strong>{{ uploadFile.name }}</strong>
                <p>{{ formatFileSize(uploadFile.size) }}</p>
              </div>
              <button class="btn btn-ghost" type="button" @click="clearSelectedFile">移除</button>
            </div>

            <div class="helper-panel">
              <span>当前默认分块：{{ knowledgeBase?.default_chunk_size }} / {{ knowledgeBase?.default_chunk_overlap }}</span>
              <span>默认检索模式：{{ knowledgeBase ? retrievalModeLabelMap[knowledgeBase.default_retrieval_mode] : '-' }}</span>
            </div>

            <div v-if="uploadError" class="status-box error">{{ uploadError }}</div>
          </div>

          <div class="modal-footer">
            <button class="btn btn-ghost" type="button" @click="closeUploadModal">取消</button>
            <button class="btn btn-primary" type="button" :disabled="uploading || !uploadFile" @click="submitUpload">
              {{ uploading ? '上传中...' : '保存并上传' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="showParseLogModal" class="modal-overlay" @click.self="closeParseLogModal">
        <div class="modal-card parse-log-modal">
          <div class="modal-header">
            <div>
              <h3>{{ parseLogKind === 'reindex' ? '重建索引进度' : '解析进度' }}</h3>
              <p>{{ parseLogTitle }}</p>
            </div>
            <div class="parse-log-header-actions">
              <span
                v-if="parseLogPhase === 'running'"
                class="status-pill info"
              >进行中</span>
              <span
                v-else-if="parseLogPhase === 'success'"
                class="status-pill success"
              >成功</span>
              <span
                v-else-if="parseLogPhase === 'error'"
                class="status-pill error"
              >失败</span>
              <button class="icon-button" type="button" @click="closeParseLogModal">
                <AppIcon name="close" :size="16" />
              </button>
            </div>
          </div>
          <div ref="parseLogScrollRef" class="modal-body parse-log-body">
            <p v-if="parseLogLoading" class="parse-log-empty">加载日志…</p>
            <template v-else>
              <div v-for="(line, idx) in parseLogLines" :key="idx" class="parse-log-line">
                <span class="parse-log-time">{{ line.t }}</span>
                <span class="parse-log-text">{{ line.text }}</span>
              </div>
              <p
                v-if="parseLogLines.length === 0 && parseLogPhase !== 'success' && parseLogPhase !== 'error'"
                class="parse-log-empty"
              >
                等待日志…
              </p>
              <p
                v-else-if="parseLogLines.length === 0 && parseLogPhase === 'success'"
                class="parse-log-empty parse-log-empty-hint"
              >
                暂无解析过程日志。完成解析或重建索引后，日志会保存在服务器，之后可随时在此查看。
              </p>
              <p
                v-else-if="parseLogLines.length === 0 && parseLogPhase === 'error'"
                class="parse-log-empty parse-log-empty-hint"
              >
                暂无已保存的解析过程日志。失败原因见文档列表中的错误说明。
              </p>
            </template>
          </div>
          <div class="modal-footer">
            <button class="btn btn-primary" type="button" @click="closeParseLogModal">关闭</button>
          </div>
        </div>
      </div>
    </div>
    <Teleport to="body">
      <Transition name="kb-detail-toast">
        <div v-if="toastText" class="kb-detail-toast" role="status" aria-live="polite">{{ toastText }}</div>
      </Transition>
    </Teleport>
  </Layout>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  getKnowledgeBaseErrorMessage,
  knowledgeBaseApi,
  streamDocumentProcess,
  type KnowledgeBase,
  type KnowledgeDocument,
  type KnowledgeSearchResponse,
  type RetrievalMode,
} from '../api/knowledge-base'
import { modelApi, defaultModelApi, getErrorMessage as getModelErrorMessage, type ModelItem, type DefaultModelOption } from '../api/model-management'
import AppIcon from '../components/AppIcon.vue'
import ChunkingSettingsPanel from '../components/knowledge-base/ChunkingSettingsPanel.vue'
import RetrievalSettingsPanel from '../components/knowledge-base/RetrievalSettingsPanel.vue'
import RetrievalConfigForm, {
  type RetrievalFormState,
} from '../components/knowledge-base/RetrievalConfigForm.vue'
import { retrievalFormFromKnowledgeBase } from '../components/knowledge-base/retrieval-form'
import EmptyState from '../components/EmptyState.vue'
import Layout from '../components/Layout.vue'

const route = useRoute()
const router = useRouter()

const statusLabelMap: Record<string, string> = {
  active: '运行中',
  inactive: '未激活',
  deleted: '已删除',
  uploaded: '待解析',
  parsing: '解析中',
  chunking: '分块中',
  indexing: '索引中',
  indexed: '已完成',
  failed: '失败',
}

const statusToneMap: Record<string, string> = {
  uploaded: 'info',
  parsing: 'info',
  chunking: 'info',
  indexing: 'warning',
  indexed: 'success',
  failed: 'error',
}

const retrievalModeLabelMap: Record<RetrievalMode, string> = {
  hybrid: '混合检索',
  vector: '向量检索',
  keyword: '关键词检索',
}

const tabs = [
  { key: 'documents', label: '文件列表', caption: '文档与上传', icon: 'folder' },
  { key: 'retrieval', label: '检索测试', caption: '召回验证', icon: 'retrieval' },
  { key: 'logs', label: '处理日志', caption: '状态追踪', icon: 'clock' },
  { key: 'settings', label: '配置', caption: '默认参数', icon: 'settings' },
] as const

type DetailTab = (typeof tabs)[number]['key']

const knowledgeBase = ref<KnowledgeBase | null>(null)
const documents = ref<KnowledgeDocument[]>([])
const loading = ref(true)
const documentsLoading = ref(false)
const error = ref('')
const activeTab = ref<DetailTab>('documents')
const documentKeyword = ref('')
const documentStatusFilter = ref('all')
const sortOrder = ref<'newest' | 'oldest' | 'name'>('newest')
/** 正在解析/重建中的文档 id（上传本身已很快返回） */
const processingDocumentIds = ref<number[]>([])
const showParseLogModal = ref(false)
const parseLogTitle = ref('')
const parseLogLines = ref<{ t: string; text: string }[]>([])
const parseLogPhase = ref<'running' | 'success' | 'error'>('running')
const parseLogKind = ref<'parse' | 'reindex'>('parse')
const parseLogDocumentId = ref<number | null>(null)
/** 当前弹窗对应的文档 id，用于忽略过期的解析日志请求结果 */
const parseLogModalOpenedFor = ref<number | null>(null)
const parseLogLoading = ref(false)
const parseLogScrollRef = ref<HTMLDivElement | null>(null)
const deletingDocumentIds = ref<number[]>([])
const notice = ref<{ type: 'success' | 'error' | 'info'; text: string }>({ type: 'success', text: '' })

const embeddingModels = ref<ModelItem[]>([])
const embeddingModelsLoading = ref(false)
const savingEmbeddingModel = ref(false)
const defaultEmbeddingModel = ref<DefaultModelOption | null>(null)

type PdfParser = 'mineru' | 'docling'

const savingPdfParser = ref(false)

const pdfParser = computed<PdfParser>(() => {
  const raw = (knowledgeBase.value?.config as Record<string, unknown> | null)?.pdf_parser
  return raw === 'docling' ? 'docling' : 'mineru'
})

async function onPdfParserChange(evt: Event) {
  const target = evt.target as HTMLSelectElement
  const next = (target.value === 'docling' ? 'docling' : 'mineru') as PdfParser
  if (!kbId.value || Number.isNaN(kbId.value) || next === pdfParser.value) {
    return
  }
  savingPdfParser.value = true
  try {
    const prevConfig = (knowledgeBase.value?.config || {}) as Record<string, unknown>
    const nextConfig = { ...prevConfig, pdf_parser: next }
    const updated = await knowledgeBaseApi.update(kbId.value, { config: nextConfig })
    knowledgeBase.value = updated
    if (next === 'docling') {
      showNotice('已记录偏好为 Docling；引擎上线前仍使用 MinerU 解析。', 'info', 4000)
    } else {
      showNotice('PDF 解析器已切换为 MinerU。', 'success', 3000)
    }
  } catch (value) {
    showNotice(getKnowledgeBaseErrorMessage(value, '更新 PDF 解析器失败'), 'error')
    target.value = pdfParser.value
  } finally {
    savingPdfParser.value = false
  }
}

/** 底部单行 Toast（如上传成功），不占顶部 notice 条 */
const toastText = ref('')
let toastClearTimer: number | null = null

function showToast(text: string, durationMs = 3500) {
  if (toastClearTimer != null) {
    window.clearTimeout(toastClearTimer)
    toastClearTimer = null
  }
  toastText.value = text
  toastClearTimer = window.setTimeout(() => {
    if (toastText.value === text) {
      toastText.value = ''
    }
    toastClearTimer = null
  }, durationMs)
}

onUnmounted(() => {
  if (toastClearTimer != null) {
    window.clearTimeout(toastClearTimer)
  }
})

const showUploadModal = ref(false)
const uploadFile = ref<File | null>(null)
const uploadError = ref('')
const uploading = ref(false)
const isDragOver = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

const searchQuery = ref('')
const searchForm = ref<RetrievalFormState>({
  mode: 'hybrid',
  top_k: 3,
  score_threshold_enabled: false,
  score_threshold: 0.5,
  vector_weight: 0.5,
  hybrid_strategy: 'weight',
  rerank_enabled: false,
  rerank_model_id: null,
})

const searching = ref(false)
const searchError = ref('')
const searchResults = ref<KnowledgeSearchResponse | null>(null)

const kbId = computed(() => Number(route.params.id))
const filteredDocuments = computed(() => {
  const keyword = documentKeyword.value.trim().toLowerCase()
  const status = documentStatusFilter.value
  const sorted = [...documents.value]
    .filter((document) => {
      const matchKeyword = !keyword || document.document_name.toLowerCase().includes(keyword) || document.file_name.toLowerCase().includes(keyword)
      const matchStatus = status === 'all' || document.status === status
      return matchKeyword && matchStatus
    })
    .sort((left, right) => {
      if (sortOrder.value === 'name') {
        return left.document_name.localeCompare(right.document_name, 'zh-CN')
      }
      const leftTime = new Date(left.created_at).getTime()
      const rightTime = new Date(right.created_at).getTime()
      return sortOrder.value === 'newest' ? rightTime - leftTime : leftTime - rightTime
    })
  return sorted
})
const activityItems = computed(() => {
  return [...documents.value]
    .sort((left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime())
    .slice(0, 12)
    .map((document) => ({
      id: document.id,
      title: document.document_name,
      time: formatDate(document.updated_at),
      status: statusLabelMap[document.status] || document.status,
      tone: statusToneMap[document.status] || 'info',
      message:
        document.error_message ||
        (document.status === 'indexed'
          ? `文档已完成解析与索引，共生成 ${document.chunk_count} 个分块。`
          : `当前状态为 ${statusLabelMap[document.status] || document.status}。`),
    }))
})

const showNotice = (text: string, type: 'success' | 'error' | 'info' = 'success', durationMs = 3000) => {
  notice.value = { text, type }
  window.setTimeout(() => {
    if (notice.value.text === text) {
      notice.value = { text: '', type: 'success' }
    }
  }, durationMs)
}

function formatDate(value: string) {
  return new Date(value).toLocaleString('zh-CN')
}

function formatFileSize(value: number | null) {
  if (!value) {
    return '0 B'
  }
  if (value < 1024) {
    return `${value} B`
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function formatScore(value: number) {
  return value.toFixed(3)
}

type DocumentChunkingMode = 'inherit' | 'general' | 'parent_child'

function documentChunkingMode(document: KnowledgeDocument): DocumentChunkingMode {
  const cfg = document.chunking_config as Record<string, unknown> | null
  if (!cfg || typeof cfg !== 'object') {
    return 'inherit'
  }
  const mode = (cfg as Record<string, unknown>).mode
  if (mode === 'parent_child') {
    return 'parent_child'
  }
  if (mode === 'general') {
    return 'general'
  }
  return 'inherit'
}

function documentChunkingTitle(document: KnowledgeDocument): string {
  const mode = documentChunkingMode(document)
  if (mode === 'inherit') {
    return '分段策略：跟随知识库默认（切换后需手动重建索引生效）'
  }
  if (mode === 'general') {
    return '分段策略：通用分段（切换后需手动重建索引生效）'
  }
  return '分段策略：父子分段（切换后需手动重建索引生效）'
}

const openChunkingMenuForId = ref<number | null>(null)

function toggleChunkingMenu(documentId: number) {
  openChunkingMenuForId.value = openChunkingMenuForId.value === documentId ? null : documentId
}

function closeChunkingMenu() {
  openChunkingMenuForId.value = null
}

async function setDocumentChunkingMode(document: KnowledgeDocument, next: DocumentChunkingMode) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  try {
    if (next === 'inherit') {
      await knowledgeBaseApi.updateDocumentChunkingConfig(kbId.value, document.id, null)
    } else {
      const kbChunking = (knowledgeBase.value?.config as Record<string, unknown> | null)?.chunking
      const base = (kbChunking && typeof kbChunking === 'object' ? (kbChunking as Record<string, unknown>) : {}) as Record<string, unknown>
      const payload = { ...base, mode: next }
      await knowledgeBaseApi.updateDocumentChunkingConfig(kbId.value, document.id, payload)
    }
    await refreshDocuments()
    showNotice('分段策略已保存。请手动点击「重建索引」使其生效。', 'info')
  } catch (value) {
    showNotice(getKnowledgeBaseErrorMessage(value, '保存分段策略失败'), 'error')
  } finally {
    closeChunkingMenu()
  }
}

function formatSource(document: KnowledgeDocument) {
  if (document.file_ext) {
    return document.file_ext.replace('.', '').toUpperCase()
  }
  return document.source_type.toUpperCase()
}

function openNativeFilePicker() {
  fileInputRef.value?.click()
}

function clearSelectedFile() {
  uploadFile.value = null
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

function openUploadModal() {
  uploadError.value = ''
  showUploadModal.value = true
}

function closeUploadModal() {
  showUploadModal.value = false
  isDragOver.value = false
  uploadError.value = ''
  clearSelectedFile()
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  uploadFile.value = input.files?.[0] || null
}

function handleFileDrop(event: DragEvent) {
  isDragOver.value = false
  const file = event.dataTransfer?.files?.[0] || null
  uploadFile.value = file
}

async function refreshDocuments() {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    documents.value = []
    return
  }
  documentsLoading.value = true
  try {
    const data = await knowledgeBaseApi.listDocuments(kbId.value, { page: 1, page_size: 100 })
    documents.value = data.items
  } catch (value) {
    showNotice(getKnowledgeBaseErrorMessage(value, '加载文档列表失败'), 'error')
  } finally {
    documentsLoading.value = false
  }
}

function onChunkingSettingsSaved(updated: KnowledgeBase) {
  knowledgeBase.value = updated
}

function onRetrievalSettingsSaved(updated: KnowledgeBase) {
  knowledgeBase.value = updated
  searchForm.value = retrievalFormFromKnowledgeBase(updated)
}

function resetSearchForm() {
  if (!knowledgeBase.value) {
    return
  }
  searchForm.value = retrievalFormFromKnowledgeBase(knowledgeBase.value)
}

async function loadEmbeddingModels() {
  embeddingModelsLoading.value = true
  try {
    const [modelsData, defaultsData] = await Promise.all([
      modelApi.getModels({ model_type: 'embedding', is_enabled: true, view: 'flat' }),
      defaultModelApi.getDefaults(),
    ])
    embeddingModels.value = modelsData as ModelItem[]
    defaultEmbeddingModel.value = defaultsData.embedding
  } catch (value) {
    showNotice(getModelErrorMessage(value, '加载嵌入模型列表失败'), 'error')
  } finally {
    embeddingModelsLoading.value = false
  }
}

async function saveEmbeddingModel(modelId: number | null) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  savingEmbeddingModel.value = true
  try {
    const updated = await knowledgeBaseApi.update(kbId.value, { embedding_model_id: modelId })
    knowledgeBase.value = updated
    const hasIndexed = documents.value.some((d) => d.status === 'indexed')
    showNotice(
      hasIndexed
        ? 'Embedding 模型已更新。已有文档需点击「重建索引」才能在问答中正常使用。'
        : 'Embedding 模型已更新。',
      'success',
      5000,
    )
  } catch (value) {
    showNotice(getKnowledgeBaseErrorMessage(value, '更新 Embedding 模型失败'), 'error')
  } finally {
    savingEmbeddingModel.value = false
  }
}

async function loadPage() {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    error.value = '知识库 ID 无效'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    knowledgeBase.value = await knowledgeBaseApi.get(kbId.value)
    searchForm.value = retrievalFormFromKnowledgeBase(knowledgeBase.value)
    await refreshDocuments()
    await loadEmbeddingModels()
  } catch (value) {
    error.value = getKnowledgeBaseErrorMessage(value, '加载知识库详情失败')
  } finally {
    loading.value = false
  }
}

async function submitUpload() {
  if (!kbId.value || Number.isNaN(kbId.value) || !uploadFile.value) {
    uploadError.value = '请选择要上传的文件'
    return
  }
  uploading.value = true
  uploadError.value = ''
  const uploadedName = uploadFile.value.name
  try {
    await knowledgeBaseApi.uploadDocument(kbId.value, { file: uploadFile.value })
    await refreshDocuments()
    closeUploadModal()
    showToast(`「${uploadedName}」上传成功，已加入列表。请点击「开始解析」完成分块与索引。`, 4000)
  } catch (value) {
    uploadError.value = getKnowledgeBaseErrorMessage(value, '文档上传失败')
  } finally {
    uploading.value = false
  }
}

function goToDocumentDetail(document: KnowledgeDocument) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  router.push({
    name: 'knowledge-document-detail',
    params: { kbId: String(kbId.value), docId: String(document.id) },
  })
}

function closeParseLogModal() {
  showParseLogModal.value = false
}

type ParseLogSnapshot = {
  kind: 'parse' | 'reindex'
  phase: 'running' | 'success' | 'error'
  lines: { t: string; text: string }[]
}

function parseLogStorageKey(documentId: number) {
  return `zs-rag-parse-log:${kbId.value}:${documentId}`
}

function loadParseLogSnapshot(documentId: number): ParseLogSnapshot | null {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return null
  }
  try {
    const raw = sessionStorage.getItem(parseLogStorageKey(documentId))
    if (!raw) {
      return null
    }
    return JSON.parse(raw) as ParseLogSnapshot
  } catch {
    return null
  }
}

function persistParseLogSnapshot(documentId: number) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  if (parseLogDocumentId.value !== documentId) {
    return
  }
  try {
    const payload: ParseLogSnapshot = {
      kind: parseLogKind.value,
      phase: parseLogPhase.value,
      lines: [...parseLogLines.value],
    }
    sessionStorage.setItem(parseLogStorageKey(documentId), JSON.stringify(payload))
  } catch {
    /* 存储配额等 */
  }
}

function parseLogHasStoredSnapshot(documentId: number) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return false
  }
  return sessionStorage.getItem(parseLogStorageKey(documentId)) != null
}

function parseLogVisibleFor(document: KnowledgeDocument) {
  if (processingDocumentIds.value.includes(document.id)) {
    return true
  }
  if (parseLogDocumentId.value === document.id && parseLogLines.value.length > 0) {
    return true
  }
  if (document.status === 'indexed' || document.status === 'failed') {
    return true
  }
  return parseLogHasStoredSnapshot(document.id)
}

async function openParseLogModal(document: KnowledgeDocument) {
  const targetId = document.id
  parseLogModalOpenedFor.value = targetId
  parseLogTitle.value = document.file_name

  const memoryHit = parseLogDocumentId.value === document.id && parseLogLines.value.length > 0
  if (!memoryHit) {
    const stored = loadParseLogSnapshot(document.id)
    if (stored) {
      parseLogDocumentId.value = document.id
      parseLogKind.value = stored.kind
      parseLogPhase.value = stored.phase
      parseLogLines.value = [...stored.lines]
    } else {
      parseLogDocumentId.value = document.id
      parseLogLines.value = []
      parseLogKind.value = 'parse'
      if (document.status === 'indexed') {
        parseLogPhase.value = 'success'
      } else if (document.status === 'failed') {
        parseLogPhase.value = 'error'
      } else {
        parseLogPhase.value = 'running'
      }
    }
  }

  showParseLogModal.value = true

  const skipServerFetch = processingDocumentIds.value.includes(document.id)
  if (!skipServerFetch && kbId.value && !Number.isNaN(kbId.value)) {
    parseLogLoading.value = true
    try {
      const remote = await knowledgeBaseApi.getDocumentParseLog(kbId.value, document.id)
      if (parseLogModalOpenedFor.value !== targetId) {
        return
      }
      if (remote.lines && remote.lines.length > 0) {
        parseLogLines.value = remote.lines.map((line) => ({
          t: line.t || '',
          text: line.text || '',
        }))
        parseLogKind.value = remote.kind === 'reindex' ? 'reindex' : 'parse'
        parseLogPhase.value = remote.phase === 'error' ? 'error' : 'success'
        parseLogDocumentId.value = document.id
      }
    } catch (value) {
      showNotice(getKnowledgeBaseErrorMessage(value, '加载解析日志失败'), 'error')
    } finally {
      parseLogLoading.value = false
    }
  } else {
    parseLogLoading.value = false
  }

  nextTick(() => {
    const el = parseLogScrollRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

function parseLogDotClass(document: KnowledgeDocument): string {
  if (parseLogDocumentId.value === document.id) {
    if (processingDocumentIds.value.includes(document.id)) {
      return 'parse-log-dot--running'
    }
    if (parseLogPhase.value === 'success') {
      return 'parse-log-dot--success'
    }
    if (parseLogPhase.value === 'error') {
      return 'parse-log-dot--error'
    }
    return 'parse-log-dot--running'
  }
  if (document.status === 'failed') {
    return 'parse-log-dot--error'
  }
  if (document.status === 'indexed') {
    return 'parse-log-dot--success'
  }
  if (parseLogHasStoredSnapshot(document.id)) {
    const stored = loadParseLogSnapshot(document.id)
    if (stored?.phase === 'error') {
      return 'parse-log-dot--error'
    }
    return 'parse-log-dot--success'
  }
  return ''
}

function parseLogDotTitle(document: KnowledgeDocument): string {
  if (parseLogDocumentId.value === document.id) {
    if (processingDocumentIds.value.includes(document.id)) {
      return '解析进行中，点击查看日志'
    }
    if (parseLogPhase.value === 'success') {
      return '解析已完成，点击查看日志'
    }
    if (parseLogPhase.value === 'error') {
      return '解析失败，点击查看日志'
    }
    return '查看解析日志'
  }
  if (document.status === 'failed') {
    return '解析失败，点击查看解析日志'
  }
  if (document.status === 'indexed') {
    return '解析已完成，点击查看解析日志'
  }
  if (parseLogHasStoredSnapshot(document.id)) {
    return '点击查看解析日志'
  }
  return '查看解析日志'
}

function appendParseLog(text: string) {
  const t = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  parseLogLines.value.push({ t, text })
  nextTick(() => {
    const el = parseLogScrollRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

async function parseDocumentAction(documentId: number) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  const meta = documents.value.find((d) => d.id === documentId)
  parseLogDocumentId.value = documentId
  parseLogKind.value = 'parse'
  parseLogTitle.value = meta?.file_name || `文档 #${documentId}`
  parseLogLines.value = []
  parseLogPhase.value = 'running'
  appendParseLog('正在连接解析流…')
  processingDocumentIds.value = [...processingDocumentIds.value, documentId]
  try {
    await streamDocumentProcess(kbId.value, documentId, 'parse', {
      onLog: appendParseLog,
      onDone: () => {
        parseLogPhase.value = 'success'
      },
      onError: () => {
        parseLogPhase.value = 'error'
      },
    })
    await refreshDocuments()
    showNotice('解析与索引已完成。')
  } catch (value) {
    parseLogPhase.value = 'error'
    showNotice(getKnowledgeBaseErrorMessage(value, '解析失败'), 'error')
  } finally {
    processingDocumentIds.value = processingDocumentIds.value.filter((item) => item !== documentId)
    persistParseLogSnapshot(documentId)
  }
}

async function reindexDocumentAction(documentId: number) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  const meta = documents.value.find((d) => d.id === documentId)
  parseLogDocumentId.value = documentId
  parseLogKind.value = 'reindex'
  parseLogTitle.value = meta?.file_name || `文档 #${documentId}`
  parseLogLines.value = []
  parseLogPhase.value = 'running'
  appendParseLog('正在连接重建索引流…')
  processingDocumentIds.value = [...processingDocumentIds.value, documentId]
  try {
    await streamDocumentProcess(kbId.value, documentId, 'reindex', {
      onLog: appendParseLog,
      onDone: () => {
        parseLogPhase.value = 'success'
      },
      onError: () => {
        parseLogPhase.value = 'error'
      },
    })
    await refreshDocuments()
    showNotice('重建索引已完成。')
  } catch (value) {
    parseLogPhase.value = 'error'
    showNotice(getKnowledgeBaseErrorMessage(value, '重建索引失败'), 'error')
  } finally {
    processingDocumentIds.value = processingDocumentIds.value.filter((item) => item !== documentId)
    persistParseLogSnapshot(documentId)
  }
}

async function deleteDocumentAction(documentId: number) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  if (!window.confirm('确定要删除该文档吗？')) {
    return
  }
  deletingDocumentIds.value = [...deletingDocumentIds.value, documentId]
  try {
    await knowledgeBaseApi.deleteDocument(kbId.value, documentId)
    try {
      sessionStorage.removeItem(parseLogStorageKey(documentId))
    } catch {
      /* ignore */
    }
    await refreshDocuments()
    showNotice('文档已删除。')
  } catch (value) {
    showNotice(getKnowledgeBaseErrorMessage(value, '删除文档失败'), 'error')
  } finally {
    deletingDocumentIds.value = deletingDocumentIds.value.filter((item) => item !== documentId)
  }
}

async function submitSearch() {
  if (!kbId.value || Number.isNaN(kbId.value) || !searchQuery.value.trim()) {
    return
  }
  searching.value = true
  searchError.value = ''
  try {
    const f = searchForm.value
    const payload: Parameters<typeof knowledgeBaseApi.search>[1] = {
      query: searchQuery.value,
      mode: f.mode,
      top_k: f.top_k,
      score_threshold: f.score_threshold_enabled ? f.score_threshold : null,
    }
    if (f.mode === 'hybrid' && f.hybrid_strategy === 'weight') {
      payload.vector_weight = f.vector_weight
    }
    searchResults.value = await knowledgeBaseApi.search(kbId.value, payload)
  } catch (value) {
    searchError.value = getKnowledgeBaseErrorMessage(value, '检索失败')
    searchResults.value = null
  } finally {
    searching.value = false
  }
}

watch(
  () => route.params.id,
  async () => {
    await loadPage()
  },
  { immediate: true },
)

watch(openChunkingMenuForId, (value) => {
  if (value == null) {
    return
  }
  window.setTimeout(() => {
    const handler = () => closeChunkingMenu()
    const once = () => {
      window.removeEventListener('click', handler)
      window.removeEventListener('keydown', onKey)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        closeChunkingMenu()
        once()
      }
    }
    window.addEventListener('click', handler, { once: true })
    window.addEventListener('keydown', onKey, { once: true })
  }, 0)
})
</script>

<style scoped>
.kb-config-follow {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid var(--border-color);
}

.custom-select-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
}

.custom-select {
  width: 100%;
  height: 40px;
  padding: 0 36px 0 14px;
  appearance: none;
  -webkit-appearance: none;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-size: 0.9rem;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.custom-select:hover {
  border-color: var(--brand-primary);
  background: var(--bg-secondary);
}

.custom-select:focus {
  outline: none;
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 3px var(--brand-primary-light);
  background: var(--bg-secondary);
}

.custom-select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.custom-select-arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--text-tertiary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.custom-select:focus + .custom-select-arrow {
  color: var(--brand-primary);
}

.embedding-model-loading {
  display: flex;
  align-items: center;
  min-height: 40px;
  padding: 0 14px;
  color: var(--text-tertiary);
  font-size: 0.9rem;
  border: 1px dashed var(--border-color);
  border-radius: 12px;
  background: var(--bg-tertiary);
}

.embedding-model-saving {
  font-size: 0.82rem;
  color: var(--brand-primary);
  white-space: nowrap;
}

.embedding-model-warning {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 12px;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.25);
  color: #b45309;
  font-size: 0.85rem;
  line-height: 1.5;
}

.embedding-model-warning .app-icon {
  flex-shrink: 0;
  margin-top: 1px;
}

.pdf-parser-section {
  display: grid;
  gap: 10px;
  margin-bottom: 8px;
}

.pdf-parser-row {
  display: grid;
  grid-template-columns: minmax(120px, 160px) minmax(0, 1fr);
  align-items: center;
  gap: 16px;
}

.pdf-parser-label {
  margin: 0;
  font-size: 1.05rem;
  color: var(--text-primary);
  font-weight: 600;
}

.pdf-parser-field {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.pdf-parser-select-wrap {
  flex: 1;
  max-width: 420px;
}

.knowledge-detail-view {
  display: grid;
  gap: 16px;
}

.knowledge-detail-layout {
  display: grid;
  grid-template-columns: minmax(180px, 200px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.detail-sidebar,
.detail-main,
.content-card,
.section-nav-card,
.activity-list,
.search-result-list {
  display: grid;
  gap: 18px;
}

.panel-skeleton {
  min-height: 420px;
}

.error-panel,
.toolbar-actions,
.row-actions,
.action-row,
.search-result-header,
.search-result-meta-row,
.activity-header,
.modal-header,
.modal-footer,
.selected-file-card,
.helper-panel,
.title-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.document-main-cell strong,
.activity-card strong,
.search-result-card strong,
.error-panel h3 {
  color: var(--text-primary);
}

.document-main-cell p,
.search-result-card p,
.activity-card p,
.error-panel p,
.selected-file-card p,
.helper-panel span {
  color: var(--text-secondary);
}

.section-nav-copy small,
.document-meta-cell,
.document-table-head,
.table-actions-head,
.search-result-meta-row,
.activity-header p {
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.section-nav-card {
  padding: 10px;
}

.section-nav-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  padding: 12px;
  border: 1px solid transparent;
  border-radius: 16px;
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease, color 0.2s ease;
}

.section-nav-item:hover,
.section-nav-item.active {
  border-color: var(--border-color);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  transform: translateY(-1px);
}

.section-nav-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: var(--bg-secondary);
  color: var(--brand-primary);
  flex-shrink: 0;
}

.section-nav-copy {
  display: grid;
  gap: 4px;
}

.content-card {
  padding: 24px;
}

.documents-toolbar {
  gap: 14px;
}

.toolbar-field {
  min-width: 190px;
}

.toolbar-field-search {
  flex: 1;
  min-width: min(320px, 100%);
}

.document-table-head,
.document-row {
  display: grid;
  grid-template-columns: minmax(240px, 2.1fr) minmax(150px, 1.2fr) 0.8fr 0.9fr 0.8fr 0.8fr minmax(200px, 1.45fr);
  gap: 16px;
  align-items: center;
}

.document-table-head {
  padding: 0 18px 12px;
  font-weight: 700;
  border-bottom: 1px solid var(--border-color);
}

.document-table-body {
  display: grid;
  gap: 14px;
}

.document-row {
  position: relative;
  padding: 18px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: var(--bg-tertiary);
  box-shadow: var(--card-shadow-xs);
}

.document-main-cell {
  min-width: 0;
}

.document-main-cell strong,
.document-main-cell p {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-preview-trigger {
  cursor: pointer;
  border-radius: 10px;
  padding: 6px 8px;
  margin: -6px -8px;
  outline: none;
  transition: background 0.15s ease, opacity 0.15s ease;
}

.doc-preview-trigger:hover {
  background: var(--bg-secondary);
}

.doc-preview-trigger:focus-visible {
  box-shadow: 0 0 0 2px var(--brand-primary);
}

.doc-preview-loading {
  pointer-events: none;
  opacity: 0.65;
}

.document-main-cell p,
.selected-file-card p,
.search-result-card p,
.activity-message,
.error-panel p {
  margin: 6px 0 0;
  line-height: 1.6;
}

.btn-row {
  min-width: 92px;
  justify-content: center;
}

.document-row .row-actions.document-row-actions {
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  min-width: 0;
}

.document-row .row-actions.document-row-actions .btn-row-compact {
  min-width: 0;
  max-width: 100%;
  padding: 4px 8px;
  font-size: 0.72rem;
  line-height: 1.25;
  white-space: nowrap;
}

.parse-log-dot-btn {
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  vertical-align: middle;
}

.parse-log-dot-btn:hover {
  background: var(--bg-secondary);
}

.parse-log-dot-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--brand-primary-light);
}

.parse-log-dot {
  display: block;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--text-tertiary);
}

.parse-log-dot--running {
  background: var(--brand-primary);
}

.parse-log-dot--success {
  background: var(--success-color);
  box-shadow: 0 0 0 1px rgba(22, 163, 74, 0.35);
}

.parse-log-dot--error {
  background: var(--danger-color);
  box-shadow: 0 0 0 1px rgba(220, 38, 38, 0.35);
}

.row-actions-muted {
  font-size: 0.82rem;
  color: var(--text-tertiary);
  padding: 6px 8px;
}

.kebab-menu {
  position: relative;
  flex: 0 0 auto;
}

.kebab-trigger {
  min-width: 34px;
  padding: 4px 10px;
  font-size: 1.05rem;
  line-height: 1;
}

.kebab-popover {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  min-width: 180px;
  padding: 10px;
  border-radius: 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  box-shadow: var(--card-shadow-xs);
  z-index: 20;
  display: grid;
  gap: 6px;
}

.kebab-title {
  font-size: 0.78rem;
  color: var(--text-tertiary);
  padding: 0 6px 4px;
}

.kebab-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  width: 100%;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-primary);
  text-align: left;
  padding: 8px 10px;
  border-radius: 12px;
  cursor: pointer;
  font-size: 0.86rem;
}

.kebab-item:hover {
  background: var(--bg-tertiary);
  border-color: var(--border-color);
}

.kebab-item:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--brand-primary-light);
}

.kebab-check {
  color: var(--brand-primary);
  font-weight: 700;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.document-row-error {
  grid-column: 1 / -1;
}

.retrieval-card {
  display: grid;
  gap: 18px;
}

.retrieval-form {
  display: grid;
  gap: 18px;
}

.retrieval-search-field {
  width: 100%;
}

.retrieval-query-block {
  display: grid;
  gap: 12px;
}

.retrieval-query-label {
  font-size: 0.92rem;
  font-weight: 600;
}

.retrieval-query-actions {
  display: flex;
  justify-content: flex-end;
}

.retrieval-submit-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.retrieval-layout {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 6fr);
  gap: 20px;
  align-items: start;
}

.retrieval-panel {
  display: grid;
  gap: 18px;
  min-width: 0;
}

.retrieval-panel--left {
  padding: 18px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-elevated);
}

.retrieval-panel--right {
  position: sticky;
  top: 12px;
  padding: 18px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-elevated);
  max-height: calc(100vh - 140px);
  overflow: hidden;
  grid-template-rows: auto minmax(0, 1fr);
}

.retrieval-result-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.retrieval-result-head-title {
  display: grid;
  gap: 4px;
}

.retrieval-result-head-title h4 {
  margin: 0;
  font-size: 1rem;
  color: var(--text-primary);
}

.retrieval-result-head-title p {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-tertiary);
}

.retrieval-result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.retrieval-result-body {
  min-height: 0;
  overflow: auto;
  padding-right: 4px;
}

@media (max-width: 1100px) {
  .retrieval-layout {
    grid-template-columns: 1fr;
  }

  .retrieval-panel--right {
    position: static;
    max-height: none;
    overflow: visible;
  }

  .retrieval-result-body {
    overflow: visible;
  }
}

.search-result-list {
  display: grid;
  gap: 14px;
}

.search-result-card,
.activity-card {
  padding: 18px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: var(--bg-tertiary);
}

.search-result-card p {
  white-space: pre-wrap;
}

.search-result-header,
.search-result-meta-row,
.activity-header {
  align-items: center;
}

.activity-list {
  gap: 14px;
}

.activity-card {
  display: grid;
  gap: 12px;
}

.activity-message {
  color: var(--text-secondary);
}

.upload-modal {
  width: min(760px, 100%);
}

.upload-modal-body {
  display: grid;
  gap: 18px;
}

.parse-log-modal {
  width: min(720px, 100%);
  max-height: min(90vh, 800px);
  display: flex;
  flex-direction: column;
}

.parse-log-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.parse-log-body {
  overflow: auto;
  min-height: 220px;
  max-height: min(58vh, 520px);
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 0.8rem;
  line-height: 1.55;
  text-align: left;
}

.parse-log-line {
  display: grid;
  grid-template-columns: 84px 1fr;
  gap: 10px;
  padding: 0.2rem 0;
  border-bottom: 1px solid var(--border-color);
}

.parse-log-line:last-child {
  border-bottom: none;
}

.parse-log-time {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.parse-log-text {
  color: var(--text-primary);
  word-break: break-word;
  white-space: pre-wrap;
}

.parse-log-empty {
  margin: 0;
  padding: 20px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.parse-log-empty-hint {
  line-height: 1.6;
  max-width: 520px;
  margin-left: auto;
  margin-right: auto;
}

.hidden-file-input {
  display: none;
}

.upload-dropzone {
  display: grid;
  gap: 12px;
  justify-items: center;
  width: 100%;
  padding: 36px 24px;
  border: 1px dashed var(--border-strong);
  border-radius: 22px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}

.upload-dropzone:hover,
.upload-dropzone.dragging {
  border-color: var(--brand-primary);
  background: var(--brand-primary-light);
  transform: translateY(-1px);
}

.upload-dropzone strong {
  color: var(--text-primary);
}

.upload-dropzone p {
  max-width: 560px;
  margin: 0;
  line-height: 1.65;
}

.upload-dropzone-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 58px;
  height: 58px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--brand-primary);
}

.selected-file-card,
.helper-panel {
  align-items: center;
  padding: 14px 16px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-tertiary);
}

.selected-file-card strong {
  color: var(--text-primary);
}

.helper-panel {
  flex-wrap: wrap;
}

.document-skeleton {
  min-height: 220px;
}

.status-box {
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 0.9rem;
}

.status-box.error {
  background: var(--danger-soft);
  color: var(--danger-color);
}

@media (max-width: 1280px) {
  .knowledge-detail-layout {
    grid-template-columns: 1fr;
  }

  .detail-sidebar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }

  .document-table-head {
    display: none;
  }

  .document-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }

  .document-row .row-actions.document-row-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .row-actions,
  .document-row-error {
    grid-column: 1 / -1;
  }
}

@media (max-width: 900px) {
  .detail-sidebar,
  .document-row {
    grid-template-columns: 1fr;
  }

  .document-row .row-actions.document-row-actions {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-start;
  }

  .error-panel,
  .toolbar-actions,
  .row-actions,
  .action-row,
  .search-result-header,
  .search-result-meta-row,
  .activity-header,
  .modal-header,
  .modal-footer,
  .selected-file-card,
  .helper-panel,
  .title-row {
    flex-direction: column;
    align-items: stretch;
  }

  .content-card {
    padding: 20px;
  }
}

/* 底部单行 Toast（Teleport 到 body） */
.kb-detail-toast {
  position: fixed;
  left: 50%;
  bottom: 28px;
  transform: translateX(-50%);
  z-index: 10000;
  max-width: min(92vw, 560px);
  padding: 12px 20px;
  border-radius: 12px;
  background: var(--text-primary);
  color: var(--bg-primary);
  font-size: 0.9rem;
  font-weight: 600;
  text-align: center;
  line-height: 1.45;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  border: 1px solid var(--border-color);
  pointer-events: none;
}

.kb-detail-toast-enter-active,
.kb-detail-toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.kb-detail-toast-enter-from,
.kb-detail-toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 12px);
}
</style>
