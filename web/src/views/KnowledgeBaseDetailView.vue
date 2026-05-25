<template>
  <Layout>
    <div class="page-shell knowledge-detail-view" :class="{ 'knowledge-detail-view--graph-tab': activeTab === 'graph' }">
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
            <nav class="detail-sidebar-nav surface-card" aria-label="知识库功能导航">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                type="button"
                :class="['detail-nav-item', { active: activeTab === tab.key }]"
                :title="tab.caption"
                @click="activeTab = tab.key"
              >
                <AppIcon :name="tab.icon" :size="16" class="detail-nav-icon" />
                <span class="detail-nav-label">{{ tab.label }}</span>
              </button>
            </nav>
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
                    <option v-if="isLightragKb" value="graph_indexing">图谱入库中</option>
                    <option v-if="isLightragKb" value="graph_indexed">图谱就绪</option>
                    <option value="failed">失败</option>
                    <option v-if="isLightragKb" value="graph_failed">解析失败</option>
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

                <div v-if="selectedDocumentIds.length > 0" class="documents-batch-actions">
                  <span class="documents-batch-count">已选 {{ selectedDocumentIds.length }} 项</span>
                  <button
                    class="btn btn-primary"
                    type="button"
                    :disabled="batchParsing || batchDeleting || documentsLoading || !canBatchParseSelection"
                    @click="batchParseSelectedDocuments"
                  >
                    {{ batchParsing ? '批量解析中…' : '批量解析' }}
                  </button>
                  <button
                    class="btn btn-danger"
                    type="button"
                    :disabled="batchParsing || batchDeleting || documentsLoading"
                    @click="batchDeleteSelectedDocuments"
                  >
                    {{ batchDeleting ? '批量删除中…' : '批量删除' }}
                  </button>
                  <button
                    class="btn btn-ghost"
                    type="button"
                    :disabled="batchParsing || batchDeleting"
                    @click="clearDocumentSelection"
                  >
                    清除选择
                  </button>
                </div>
              </div>

              <div v-if="documentsLoading" class="loading-skeleton document-skeleton"></div>

              <EmptyState
                v-else-if="documents.length === 0"
                :title="documentListEmptyTitle"
                :description="documentListEmptyDescription"
              >
                <template #icon>
                  <AppIcon name="folder" :size="20" />
                </template>
                <template #actions>
                  <button
                    v-if="!documentListFilterActive"
                    class="btn btn-primary"
                    type="button"
                    @click="openUploadModal"
                  >
                    <AppIcon name="plus" :size="16" />
                    添加文件
                  </button>
                </template>
              </EmptyState>

              <template v-else>
                <div class="document-table document-table-head">
                  <span class="document-col-check">
                    <input
                      ref="headerSelectAllRef"
                      class="doc-checkbox"
                      type="checkbox"
                      :checked="allDocumentsOnPageSelected"
                      :disabled="documents.length === 0 || documentsLoading || batchParsing || batchDeleting"
                      aria-label="全选本页"
                      @change="toggleSelectAllOnPage"
                    />
                  </span>
                  <span>名称</span>
                  <span>上传时间</span>
                  <span>来源</span>
                  <span>状态</span>
                  <span>分块数</span>
                  <span>解析器</span>
                  <span class="table-actions-head">动作</span>
                </div>

                <div class="document-table-body">
                  <article v-for="document in documents" :key="document.id" class="document-row">
                    <label class="document-row-check" @click.stop>
                      <input
                        class="doc-checkbox"
                        type="checkbox"
                        :checked="selectedDocumentIds.includes(document.id)"
                        :disabled="documentsLoading || batchParsing || batchDeleting"
                        :aria-label="`选择 ${document.document_name}`"
                        @change="onDocumentRowCheckboxChange(document, $event)"
                      />
                    </label>
                    <div
                      class="document-main-cell doc-preview-trigger"
                      :title="`${document.file_name || document.document_name} — 点击查看原文与切片`"
                      role="button"
                      tabindex="0"
                      @click="goToDocumentDetail(document)"
                      @keydown.enter.prevent="goToDocumentDetail(document)"
                      @keydown.space.prevent="goToDocumentDetail(document)"
                    >
                      <strong>{{ document.document_name }}</strong>
                      <p v-if="shouldShowDocumentFileSubtitle(document)">{{ document.file_name }}</p>
                    </div>
                    <span class="document-meta-cell">{{ formatDate(document.created_at) }}</span>
                    <span class="document-meta-cell">{{ formatSource(document) }}</span>
                    <span>
                      <span :class="['status-pill', statusToneMap[getDocumentDisplayStatus(document)] || 'info']">
                        {{ statusLabelMap[getDocumentDisplayStatus(document)] || getDocumentDisplayStatus(document) }}
                      </span>
                    </span>
                    <span class="document-meta-cell">{{ document.chunk_count }}</span>
                    <span class="document-meta-cell">{{ document.parser_type.toUpperCase() }}</span>
                    <div class="row-actions document-row-actions">
                      <DocumentParseProgress
                        v-if="parseTasks.isRunning(document.id)"
                        :percent="parseTasks.getTask(document.id)?.percent ?? 0"
                        :title="parseLogDotTitle(document)"
                        @open-log="openParseLogModal(document)"
                        @cancel="cancelDocumentParseAction(document.id)"
                      />
                      <template v-else>
                        <button
                          v-if="documentCanStartParse(document)"
                          class="btn btn-primary btn-row btn-row-compact"
                          type="button"
                          :disabled="batchParsing || batchDeleting"
                          @click="parseDocumentAction(document.id)"
                        >
                          {{
                            documentIsParseFailed(document) || documentIsStuckProcessing(document)
                              ? '重新解析'
                              : '开始解析'
                          }}
                        </button>
                        <button
                          v-if="documentCanReindex(document)"
                          class="btn btn-ghost btn-row btn-row-compact"
                          type="button"
                          :disabled="batchParsing || batchDeleting"
                          @click="reindexDocumentAction(document.id)"
                        >
                          {{ isLightragKb ? '重建图谱' : '重建索引' }}
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
                          :disabled="parseTasks.isRunning(document.id)"
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
                            v-if="parseTasks.isRunning(document.id)"
                            class="kebab-item"
                            type="button"
                            role="menuitem"
                            @click="forceRestartParseAction(document); openChunkingMenuForId = null"
                          >
                            <span>强制重跑</span>
                          </button>
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
                      <p class="document-row-error-text">{{ document.error_message }}</p>
                      <button
                        v-if="documentCanStartParse(document) && !isDocumentRowBusy(document)"
                        class="btn btn-primary btn-row btn-row-compact document-row-error-action"
                        type="button"
                        :disabled="isDocumentProcessingLocally(document) || batchParsing || batchDeleting"
                        @click="parseDocumentAction(document.id)"
                      >
                        {{ isDocumentProcessingLocally(document) ? '解析中…' : '重新解析' }}
                      </button>
                    </div>
                  </article>
                </div>

                <div v-if="documentsTotal > 0" class="documents-pagination">
                  <span class="documents-pagination-meta">共 {{ documentsTotal }} 条</span>
                  <label class="field documents-pagination-size">
                    <span class="field-label">每页</span>
                    <select v-model.number="documentsPageSize" class="select">
                      <option :value="10">10</option>
                      <option :value="20">20</option>
                      <option :value="50">50</option>
                      <option :value="100">100</option>
                    </select>
                  </label>
                  <div class="documents-pagination-nav">
                    <button
                      class="btn btn-ghost"
                      type="button"
                      :disabled="documentsPage <= 1 || documentsLoading"
                      @click="goDocumentsPagePrev"
                    >
                      上一页
                    </button>
                    <span class="documents-pagination-page">{{ documentsPage }} / {{ documentsTotalPages }}</span>
                    <button
                      class="btn btn-ghost"
                      type="button"
                      :disabled="documentsPage >= documentsTotalPages || documentsLoading"
                      @click="goDocumentsPageNext"
                    >
                      下一页
                    </button>
                  </div>
                </div>
              </template>
            </section>

            <section v-else-if="activeTab === 'retrieval'" class="surface-card content-card retrieval-card">
              <div class="section-heading">
                <div>
                  <h3>检索测试</h3>
                  <p>快速验证当前知识库的召回效果；修改检索参数将自动保存为知识库默认，对问答与后续检索生效。</p>
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
                    <button
                      class="btn btn-ghost"
                      type="button"
                      :disabled="searching || retrievalConfigSaving"
                      @click="resetSearchForm"
                    >
                      还原为知识库默认
                    </button>
                    <span v-if="retrievalConfigSaving" class="retrieval-config-save-hint">保存中…</span>
                    <span v-else-if="retrievalConfigSaved" class="retrieval-config-save-hint ok">已保存</span>
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

            <section v-else-if="activeTab === 'graph-search'" class="surface-card content-card retrieval-card">
              <div class="section-heading">
                <div>
                  <h3>图检索测试</h3>
                  <p>使用 LightRAG 五模式检索；默认 mix，可调整 Top K。</p>
                </div>
              </div>
              <form class="retrieval-form" @submit.prevent="submitGraphSearch">
                <label class="field">
                  <span class="field-label">检索问题</span>
                  <textarea v-model.trim="graphSearchQuery" class="textarea" rows="3" placeholder="输入问题…" />
                </label>
                <div class="form-grid two">
                  <label class="field">
                    <span class="field-label">查询模式</span>
                    <select v-model="graphSearchMode" class="select">
                      <option value="mix">mix（推荐）</option>
                      <option value="naive">naive</option>
                      <option value="local">local</option>
                      <option value="global">global</option>
                      <option value="hybrid">hybrid</option>
                    </select>
                  </label>
                  <label class="field">
                    <span class="field-label">Top K</span>
                    <input v-model.number="graphSearchTopK" class="input" type="number" min="1" max="50" />
                  </label>
                </div>
                <button class="btn btn-primary" type="submit" :disabled="graphSearching || !graphSearchQuery">
                  {{ graphSearching ? '检索中…' : '开始图检索' }}
                </button>
              </form>
              <div v-if="graphSearchError" class="status-box error">{{ graphSearchError }}</div>
              <div v-else-if="graphSearchResult" class="graph-search-results">
                <p v-if="graphSearchResult.answer_context" class="graph-search-context">{{ graphSearchResult.answer_context }}</p>
                <div v-if="graphSearchResult.entities?.length" class="graph-search-entities">
                  <h4>实体</h4>
                  <ul>
                    <li v-for="(ent, idx) in graphSearchResult.entities.slice(0, 10)" :key="idx">
                      {{ (ent as Record<string, string>).entity_name || (ent as Record<string, string>).entity_id || idx }}
                      <ViewInGraphLink
                        v-if="(ent as Record<string, string>).entity_name"
                        :kb-id="kbId"
                        :entity-id="(ent as Record<string, string>).entity_name"
                      />
                    </li>
                  </ul>
                </div>
              </div>
            </section>

            <section v-else-if="activeTab === 'graph'" class="surface-card content-card graph-viz-card">
              <div class="section-heading">
                <div>
                  <h3>知识图谱可视化</h3>
                  <p>浏览实体关系网络，按类型着色；点击节点查看详情并跳转原文。</p>
                </div>
              </div>
              <GraphVisualizationPanel
                ref="graphPanelRef"
                :kb-id="kbId"
                :focus-entity-id="graphEntityFromRoute"
              />
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

              <div v-if="isLightragKb" class="pdf-parser-section extract-llm-section">
                <div class="pdf-parser-row">
                  <h4 class="pdf-parser-label">实体抽取 LLM</h4>
                  <div class="pdf-parser-field">
                    <div class="custom-select-wrap pdf-parser-select-wrap">
                      <select
                        v-if="!llmModelsLoading"
                        class="custom-select"
                        :value="extractLlmModelId ?? ''"
                        :disabled="savingExtractLlm"
                        @change="(e) => saveExtractLlmModel((e.target as HTMLSelectElement).value ? Number((e.target as HTMLSelectElement).value) : null)"
                      >
                        <option value="">
                          默认{{ defaultLlmModel ? `（${defaultLlmModel.model_name}）` : '' }}
                        </option>
                        <option
                          v-for="model in llmModels"
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
                    <span v-if="savingExtractLlm" class="embedding-model-saving">保存中…</span>
                  </div>
                </div>
                <p class="pdf-parser-hint">用于 LightRAG 图谱入库时的实体与关系抽取；未指定时使用企业空间默认 LLM。</p>
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
                        <option value="opendataloader">OpenDataLoader（推荐，本地 CPU）</option>
                        <option value="mineru">MinerU（图片 / 兼容模式）</option>
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
                  <span>Docling 引擎尚未上线，当前仍使用 OpenDataLoader 完成 PDF 解析；功能就绪后会自动切换。</span>
                </div>
                <div v-if="pdfParser === 'opendataloader'" class="pdf-parser-section extract-llm-section">
                  <div class="pdf-parser-row">
                    <h4 class="pdf-parser-label">Hybrid 模式</h4>
                    <div class="pdf-parser-field">
                      <label class="pdf-parser-hybrid-toggle">
                        <input
                          type="checkbox"
                          :checked="pdfParserHybrid"
                          :disabled="savingPdfParserHybrid"
                          @change="onPdfParserHybridChange($event)"
                        />
                        <span>扫描件 / 复杂表格（需 odl-hybrid sidecar）</span>
                      </label>
                      <span v-if="savingPdfParserHybrid" class="embedding-model-saving">保存中…</span>
                    </div>
                  </div>
                  <p class="pdf-parser-hint">默认本地 CPU 解析；开启 Hybrid 后复杂页走 docling 后端，适合扫描 PDF。</p>
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
              <p>
                {{ knowledgeBase?.name || '当前知识库' }} · 支持 txt / md / pdf / docx / csv / Excel（xls、xlsx），可多选文件或整个文件夹。
              </p>
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
              multiple
              accept=".txt,.md,.pdf,.docx,.csv,.xls,.xlsx,.xlsm"
              @change="handleMultiFileInputChange"
            />
            <input
              ref="folderInputRef"
              class="hidden-file-input"
              type="file"
              multiple
              webkitdirectory
              @change="handleMultiFileInputChange"
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
              <p>
                支持一次选择多个文件，或拖入多个文件；格式包括 txt、md、pdf、docx、csv、Excel（xls / xlsx / xlsm）。旧版 Word（.doc）请另存为 docx。
              </p>
            </button>

            <div class="upload-folder-row">
              <button type="button" class="btn btn-ghost" @click="openFolderPicker">选择文件夹…</button>
              <span class="upload-folder-hint">将连同子目录一并加入队列，相对路径会作为上传文件名（便于区分同名文件）。</span>
            </div>

            <div v-if="uploadFiles.length > 0" class="upload-selected-panel">
              <div class="upload-selected-header">
                <span>已选 {{ uploadFiles.length }} 个文件（共 {{ formatFileSize(uploadQueueTotalBytes) }}）</span>
                <button class="btn btn-ghost" type="button" @click="clearSelectedFiles">清空</button>
              </div>
              <ul class="upload-selected-list">
                <li v-for="(f, idx) in uploadFiles" :key="`${f.name}-${idx}-${f.size}`" class="upload-selected-row">
                  <div class="upload-selected-meta">
                    <strong class="upload-selected-name">{{ f.name }}</strong>
                    <span class="upload-selected-size">{{ formatFileSize(f.size) }}</span>
                  </div>
                  <button class="btn btn-ghost" type="button" @click="removeQueuedFile(idx)">移除</button>
                </li>
              </ul>
            </div>

            <div class="helper-panel">
              <span>当前默认分块：{{ knowledgeBase?.default_chunk_size }} / {{ knowledgeBase?.default_chunk_overlap }}</span>
              <span>默认检索模式：{{ knowledgeBase ? retrievalModeLabelMap[knowledgeBase.default_retrieval_mode] : '-' }}</span>
            </div>

            <div v-if="uploadError" class="status-box error">{{ uploadError }}</div>
          </div>

          <div class="modal-footer">
            <button class="btn btn-ghost" type="button" @click="closeUploadModal">取消</button>
            <button
              class="btn btn-primary"
              type="button"
              :disabled="uploading || uploadFiles.length === 0"
              @click="submitUpload"
            >
              {{
                uploading ? `上传中 (${uploadProgress}/${uploadFiles.length})…` : '保存并上传'
              }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="showParseLogModal" class="modal-overlay" @click.self="closeParseLogModal">
        <div class="modal-card parse-log-modal">
          <div class="modal-header">
            <div>
              <h3>{{ activeParseLogTask?.mode === 'reindex' ? '重建索引进度' : '解析进度' }}</h3>
              <p>{{ parseLogTitle }}</p>
              <p v-if="activeParseLogTask?.status === 'running'" class="parse-log-progress-summary">
                {{ activeParseLogTask.percent.toFixed(2) }}%
                <span v-if="activeParseLogTask.progressMessage"> · {{ activeParseLogTask.progressMessage }}</span>
              </p>
            </div>
            <div class="parse-log-header-actions">
              <span
                v-if="activeParseLogPhase === 'running'"
                class="status-pill info"
              >进行中</span>
              <span
                v-else-if="activeParseLogPhase === 'success'"
                class="status-pill success"
              >成功</span>
              <span
                v-else-if="activeParseLogPhase === 'cancelled'"
                class="status-pill info"
              >已取消</span>
              <span
                v-else-if="activeParseLogPhase === 'error'"
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
              <div v-for="(line, idx) in activeParseLogLines" :key="idx" class="parse-log-line">
                <span class="parse-log-time">{{ line.t }}</span>
                <span class="parse-log-text">{{ line.text }}</span>
              </div>
              <p
                v-if="activeParseLogLines.length === 0 && activeParseLogPhase !== 'success' && activeParseLogPhase !== 'error' && activeParseLogPhase !== 'cancelled'"
                class="parse-log-empty"
              >
                等待日志…
              </p>
              <p
                v-else-if="activeParseLogLines.length === 0 && activeParseLogPhase === 'success'"
                class="parse-log-empty parse-log-empty-hint"
              >
                暂无解析过程日志。完成解析或重建索引后，日志会保存在服务器，之后可随时在此查看。
              </p>
              <p
                v-else-if="activeParseLogLines.length === 0 && activeParseLogPhase === 'error'"
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
  type KnowledgeBase,
  type KnowledgeDocument,
  type KnowledgeSearchResponse,
  type RetrievalMode,
} from '../api/knowledge-base'
import { modelApi, defaultModelApi, getErrorMessage as getModelErrorMessage, type ModelItem, type DefaultModelOption } from '../api/model-management'
import AppIcon from '../components/AppIcon.vue'
import ChunkingSettingsPanel from '../components/knowledge-base/ChunkingSettingsPanel.vue'
import DocumentParseProgress from '../components/knowledge-base/DocumentParseProgress.vue'
import RetrievalSettingsPanel from '../components/knowledge-base/RetrievalSettingsPanel.vue'
import RetrievalConfigForm, {
  type RetrievalFormState,
} from '../components/knowledge-base/RetrievalConfigForm.vue'
import {
  buildRetrievalUpdatePayload,
  defaultRetrievalFormState,
  retrievalFormFromKnowledgeBase,
  validateRetrievalForm,
} from '../components/knowledge-base/retrieval-form'
import EmptyState from '../components/EmptyState.vue'
import GraphVisualizationPanel from '../components/graph/GraphVisualizationPanel.vue'
import { useDocumentParseTasks } from '../composables/useDocumentParseTasks'
import ViewInGraphLink from '../components/graph/ViewInGraphLink.vue'
import Layout from '../components/Layout.vue'
import { graphSearch, getGraphErrorMessage, type GraphSearchResponse, type LightRagQueryMode } from '../api/graph-knowledge-base'
import { GRAPH_ENTITY_QUERY_KEY, GRAPH_TAB_QUERY_KEY } from '../lib/graphNavigation'

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
  graph_indexing: '图谱入库中',
  graph_indexed: '图谱就绪',
  graph_failed: '解析失败',
  failed: '失败',
}

const statusToneMap: Record<string, string> = {
  uploaded: 'info',
  parsing: 'info',
  chunking: 'info',
  indexing: 'warning',
  indexed: 'success',
  graph_indexing: 'warning',
  graph_indexed: 'success',
  graph_failed: 'error',
  failed: 'error',
}

const retrievalModeLabelMap: Record<RetrievalMode, string> = {
  hybrid: '混合检索',
  vector: '向量检索',
  keyword: '关键词检索',
}

type DetailTab = 'documents' | 'retrieval' | 'graph-search' | 'graph' | 'logs' | 'settings'

const baseTabs: { key: DetailTab; label: string; caption: string; icon: string }[] = [
  { key: 'documents', label: '文件列表', caption: '文档与上传', icon: 'folder' },
  { key: 'retrieval', label: '检索测试', caption: '召回验证', icon: 'retrieval' },
  { key: 'logs', label: '处理日志', caption: '状态追踪', icon: 'clock' },
  { key: 'settings', label: '配置', caption: '默认参数', icon: 'settings' },
]

const isLightragKb = computed(() => knowledgeBase.value?.kb_type === 'lightrag')

function getLightragConfigRecord(kb: KnowledgeBase | null | undefined): Record<string, unknown> {
  const cfg = kb?.config
  if (!cfg || typeof cfg !== 'object') {
    return {}
  }
  const lightrag = (cfg as Record<string, unknown>).lightrag
  return lightrag && typeof lightrag === 'object' ? (lightrag as Record<string, unknown>) : {}
}

const extractLlmModelId = computed(() => {
  const raw = getLightragConfigRecord(knowledgeBase.value).extract_llm_id
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : null
})

const showGraphTab = computed(() => isLightragKb.value)

const tabs = computed(() => {
  const items: { key: DetailTab; label: string; caption: string; icon: string }[] = [
    baseTabs[0],
  ]
  if (isLightragKb.value) {
    items.push({ key: 'graph-search', label: '图检索测试', caption: 'LightRAG 五模式', icon: 'retrieval' })
  } else {
    items.push(baseTabs[1])
  }
  if (showGraphTab.value) {
    items.push({
      key: 'graph',
      label: '知识图谱',
      caption: '实体关系浏览',
      icon: 'graph',
    })
  }
  items.push(baseTabs[2], baseTabs[3])
  return items
})

const knowledgeBase = ref<KnowledgeBase | null>(null)
const documents = ref<KnowledgeDocument[]>([])
const loading = ref(true)
const documentsLoading = ref(false)
const error = ref('')
const activeTab = ref<DetailTab>('documents')
const graphPanelRef = ref<InstanceType<typeof GraphVisualizationPanel> | null>(null)
const graphSearchQuery = ref('')
const graphSearchMode = ref<LightRagQueryMode>('mix')
const graphSearchTopK = ref(5)
const graphSearching = ref(false)
const graphSearchError = ref('')
const graphSearchResult = ref<GraphSearchResponse | null>(null)

async function submitGraphSearch() {
  if (!kbId.value || Number.isNaN(kbId.value) || !graphSearchQuery.value.trim()) {
    return
  }
  graphSearching.value = true
  graphSearchError.value = ''
  try {
    graphSearchResult.value = await graphSearch(kbId.value, {
      query: graphSearchQuery.value.trim(),
      mode: graphSearchMode.value,
      top_k: graphSearchTopK.value,
      include_references: true,
    })
  } catch (err) {
    graphSearchError.value = getGraphErrorMessage(err, '图检索失败')
    graphSearchResult.value = null
  } finally {
    graphSearching.value = false
  }
}

const graphEntityFromRoute = computed(() => {
  const raw = route.query[GRAPH_ENTITY_QUERY_KEY] ?? route.query.focus
  if (typeof raw === 'string' && raw.trim()) {
    return raw.trim()
  }
  return null
})

function syncDetailTabFromRoute() {
  const tab = route.query[GRAPH_TAB_QUERY_KEY] ?? route.query.tab
  if ((tab === 'graph' || tab === 'graph-viz') && showGraphTab.value) {
    activeTab.value = 'graph'
  }
}
const documentKeyword = ref('')
const documentStatusFilter = ref('all')
const sortOrder = ref<'newest' | 'oldest' | 'name'>('newest')
const documentsTotal = ref(0)
const documentsPage = ref(1)
const documentsPageSize = ref(10)
const recentActivityDocuments = ref<KnowledgeDocument[]>([])
let documentKeywordDebounceTimer: number | null = null
const selectedDocumentIds = ref<number[]>([])
const batchParsing = ref(false)
const batchDeleting = ref(false)
const headerSelectAllRef = ref<HTMLInputElement | null>(null)
const showParseLogModal = ref(false)
const parseLogTitle = ref('')
const parseLogLines = ref<{ t: string; text: string }[]>([])
const parseLogPhase = ref<'running' | 'success' | 'error' | 'cancelled'>('running')
const parseLogKind = ref<'parse' | 'reindex'>('parse')
const parseLogDocumentId = ref<number | null>(null)
/** 当前弹窗对应的文档 id，用于忽略过期的解析日志请求结果 */
const parseLogModalOpenedFor = ref<number | null>(null)
const parseLogLoading = ref(false)
const parseLogScrollRef = ref<HTMLDivElement | null>(null)
const deletingDocumentIds = ref<number[]>([])
const notice = ref<{ type: 'success' | 'error' | 'info'; text: string }>({ type: 'success', text: '' })

const activeParseLogTask = computed(() => {
  if (parseLogDocumentId.value == null) {
    return undefined
  }
  return parseTasks.getTask(parseLogDocumentId.value)
})

const activeParseLogLines = computed(() => {
  const task = activeParseLogTask.value
  if (task && task.logs.length > 0) {
    return task.logs
  }
  return parseLogLines.value
})

const activeParseLogPhase = computed(() => {
  const task = activeParseLogTask.value
  if (task) {
    return task.status
  }
  return parseLogPhase.value
})

const embeddingModels = ref<ModelItem[]>([])
const embeddingModelsLoading = ref(false)
const savingEmbeddingModel = ref(false)
const defaultEmbeddingModel = ref<DefaultModelOption | null>(null)
const llmModels = ref<ModelItem[]>([])
const llmModelsLoading = ref(false)
const savingExtractLlm = ref(false)
const defaultLlmModel = ref<DefaultModelOption | null>(null)

type PdfParser = 'opendataloader' | 'mineru' | 'docling'

const savingPdfParser = ref(false)
const savingPdfParserHybrid = ref(false)

const pdfParser = computed<PdfParser>(() => {
  const raw = (knowledgeBase.value?.config as Record<string, unknown> | null)?.pdf_parser
  if (raw === 'mineru' || raw === 'docling') {
    return raw
  }
  return 'opendataloader'
})

const pdfParserHybrid = computed(() => {
  const cfg = (knowledgeBase.value?.config as Record<string, unknown> | null) ?? {}
  return cfg.pdf_parser_hybrid === true
})

async function saveKbPdfConfig(patch: Record<string, unknown>) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  const prevConfig = (knowledgeBase.value?.config || {}) as Record<string, unknown>
  const nextConfig = { ...prevConfig, ...patch }
  const updated = await knowledgeBaseApi.update(kbId.value, { config: nextConfig })
  knowledgeBase.value = updated
}

async function onPdfParserChange(evt: Event) {
  const target = evt.target as HTMLSelectElement
  const next = (target.value === 'mineru'
    ? 'mineru'
    : target.value === 'docling'
      ? 'docling'
      : 'opendataloader') as PdfParser
  if (!kbId.value || Number.isNaN(kbId.value) || next === pdfParser.value) {
    return
  }
  savingPdfParser.value = true
  try {
    await saveKbPdfConfig({ pdf_parser: next })
    if (next === 'docling') {
      showNotice('已记录偏好为 Docling；引擎上线前仍使用 OpenDataLoader 解析 PDF。', 'info', 4000)
    } else if (next === 'mineru') {
      showNotice('PDF 解析器已切换为 MinerU（HTTP sidecar）。', 'success', 3000)
    } else {
      showNotice('PDF 解析器已切换为 OpenDataLoader（本地 CPU）。', 'success', 3000)
    }
  } catch (value) {
    showNotice(getKnowledgeBaseErrorMessage(value, '更新 PDF 解析器失败'), 'error')
    target.value = pdfParser.value
  } finally {
    savingPdfParser.value = false
  }
}

async function onPdfParserHybridChange(evt: Event) {
  const target = evt.target as HTMLInputElement
  const next = target.checked
  if (!kbId.value || Number.isNaN(kbId.value) || next === pdfParserHybrid.value) {
    return
  }
  savingPdfParserHybrid.value = true
  try {
    await saveKbPdfConfig({ pdf_parser_hybrid: next })
    showNotice(next ? '已开启 OpenDataLoader Hybrid 模式。' : '已关闭 Hybrid，使用纯本地解析。', 'success', 3000)
  } catch (value) {
    showNotice(getKnowledgeBaseErrorMessage(value, '更新 Hybrid 配置失败'), 'error')
    target.checked = pdfParserHybrid.value
  } finally {
    savingPdfParserHybrid.value = false
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

watch(activeParseLogLines, () => {
  nextTick(() => {
    const el = parseLogScrollRef.value
    if (el && showParseLogModal.value) {
      el.scrollTop = el.scrollHeight
    }
  })
})

onUnmounted(() => {
  if (toastClearTimer != null) {
    window.clearTimeout(toastClearTimer)
  }
  if (documentKeywordDebounceTimer != null) {
    window.clearTimeout(documentKeywordDebounceTimer)
  }
  for (const documentId of [...documentStatusPollTimers.keys()]) {
    stopDocumentStatusPoll(documentId)
  }
})

const showUploadModal = ref(false)
const uploadFiles = ref<File[]>([])
const uploadError = ref('')
const uploading = ref(false)
const uploadProgress = ref(0)
const isDragOver = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const folderInputRef = ref<HTMLInputElement | null>(null)

const UPLOAD_ACCEPT_EXT = new Set(['.txt', '.md', '.pdf', '.docx', '.csv', '.xls', '.xlsx', '.xlsm'])

const uploadQueueTotalBytes = computed(() => uploadFiles.value.reduce((sum, file) => sum + file.size, 0))

function fileQueueDedupeKey(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}`
}

function isAcceptedUploadFile(file: File) {
  const anyFile = file as File & { webkitRelativePath?: string }
  const pathOrName = (anyFile.webkitRelativePath && anyFile.webkitRelativePath.trim()) || file.name
  const lower = pathOrName.toLowerCase()
  const dot = lower.lastIndexOf('.')
  if (dot < 0) {
    return false
  }
  return UPLOAD_ACCEPT_EXT.has(lower.slice(dot))
}

/** 文件夹选择时携带相对路径，multipart 里的文件名供后端存入 file_name */
function toUploadFileWithRelativePath(file: File) {
  const anyFile = file as File & { webkitRelativePath?: string }
  const rel = anyFile.webkitRelativePath?.trim()
  if (!rel) {
    return file
  }
  const normalized = rel.replace(/\\/g, '/')
  if (normalized === file.name) {
    return file
  }
  return new File([file], normalized, {
    type: file.type || 'application/octet-stream',
    lastModified: file.lastModified,
  })
}

function addFilesToQueue(rawList: File[]) {
  const seen = new Set(uploadFiles.value.map(fileQueueDedupeKey))
  const next = [...uploadFiles.value]
  for (const raw of rawList) {
    if (!isAcceptedUploadFile(raw)) {
      continue
    }
    const prepared = toUploadFileWithRelativePath(raw)
    const key = fileQueueDedupeKey(prepared)
    if (seen.has(key)) {
      continue
    }
    seen.add(key)
    next.push(prepared)
  }
  uploadFiles.value = next
}

const searchQuery = ref('')
const searchForm = ref<RetrievalFormState>(defaultRetrievalFormState())

const searching = ref(false)
const searchError = ref('')
const searchResults = ref<KnowledgeSearchResponse | null>(null)
const retrievalConfigSaving = ref(false)
const retrievalConfigSaved = ref(false)
const skipRetrievalFormAutoSave = ref(false)
let retrievalFormSaveTimer: ReturnType<typeof window.setTimeout> | null = null
let retrievalConfigSavedTimer: ReturnType<typeof window.setTimeout> | null = null

const kbId = computed(() => Number(route.params.id))

const parseTasks = useDocumentParseTasks(() => kbId.value)
const processingDocumentIds = computed(() => parseTasks.runningDocumentIds())

const documentListSort = computed(() => {
  if (sortOrder.value === 'oldest') {
    return 'created_asc'
  }
  if (sortOrder.value === 'name') {
    return 'name_asc'
  }
  return 'created_desc'
})

const documentsTotalPages = computed(() => Math.max(1, Math.ceil(documentsTotal.value / documentsPageSize.value)))

const documentListFilterActive = computed(
  () => documentKeyword.value.trim() !== '' || documentStatusFilter.value !== 'all',
)

const documentListEmptyTitle = computed(() =>
  documentListFilterActive.value ? '没有匹配的文档' : '还没有文档',
)

const documentListEmptyDescription = computed(() =>
  documentListFilterActive.value
    ? '请调整搜索关键词或筛选条件。'
    : '上传文件后，点击「开始解析」完成分块与向量索引。',
)

const activityItems = computed(() => {
  return recentActivityDocuments.value.map((document) => ({
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

function documentIsParseFailed(document: KnowledgeDocument) {
  return document.status === 'failed' || document.status === 'graph_failed'
}

function documentIsIndexed(document: KnowledgeDocument) {
  return document.status === 'indexed' || document.status === 'graph_indexed'
}

function documentIsStuckProcessing(document: KnowledgeDocument) {
  return isDocumentProcessingOnServer(document) && !parseTasks.isRunning(document.id)
}

function documentCanStartParse(document: KnowledgeDocument) {
  return (
    document.status === 'uploaded' ||
    documentIsParseFailed(document) ||
    documentIsStuckProcessing(document)
  )
}

function documentCanReindex(document: KnowledgeDocument) {
  return documentIsIndexed(document)
}

function documentCanBatchParse(document: KnowledgeDocument) {
  return (
    documentCanStartParse(document) ||
    isDocumentProcessingOnServer(document)
  )
}

const DOCUMENT_PROCESSING_STATUSES = ['parsing', 'chunking', 'indexing', 'graph_indexing'] as const

function isDocumentProcessingOnServer(document: KnowledgeDocument) {
  return DOCUMENT_PROCESSING_STATUSES.includes(document.status as (typeof DOCUMENT_PROCESSING_STATUSES)[number])
}

/** 本页已发起解析/重建流式任务（含刚点击「开始解析」、服务端尚未刷新时）。 */
function isDocumentProcessingLocally(document: KnowledgeDocument) {
  if (!parseTasks.isRunning(document.id)) {
    return false
  }
  if (document.status === 'failed' || document.status === 'graph_failed') {
    return batchParsing.value
  }
  return true
}

function isDocumentRowBusy(document: KnowledgeDocument) {
  if (documentIsStuckProcessing(document)) {
    return false
  }
  return isDocumentProcessingOnServer(document) || isDocumentProcessingLocally(document)
}

/** 本页流式任务进行中：覆盖服务端尚未刷新的旧状态（避免列表闪回「图谱就绪」）。 */
function applyLocalProcessingOverlay(document: KnowledgeDocument): KnowledgeDocument {
  if (!parseTasks.isRunning(document.id)) {
    return document
  }
  if (document.status === 'graph_indexed' || document.status === 'indexed') {
    return document
  }
  if (document.status === 'graph_indexing' || document.status === 'parsing' || document.status === 'indexing') {
    return document
  }
  const task = parseTasks.getTask(document.id)
  if (task?.mode === 'reindex') {
    return {
      ...document,
      status: isLightragKb.value ? 'graph_indexing' : 'indexing',
    }
  }
  if (document.status === 'uploaded' || document.status === 'failed' || document.status === 'graph_failed') {
    return { ...document, status: 'parsing' }
  }
  return document
}

function endDocumentStreamProcessing(documentId: number, snapshot?: KnowledgeDocument) {
  stopDocumentStatusPoll(documentId)
  if (snapshot) {
    patchDocumentInList(documentId, snapshot)
  }
}

/** 列表状态列：本地任务进行中时对 uploaded / 图谱就绪 等态做乐观展示。 */
function getDocumentDisplayStatus(document: KnowledgeDocument): string {
  const overlaid = applyLocalProcessingOverlay(document)
  if (documentIsStuckProcessing(document)) {
    return 'uploaded'
  }
  return overlaid.status
}

function patchDocumentInList(documentId: number, patch: Partial<KnowledgeDocument>) {
  documents.value = documents.value.map((item) =>
    item.id === documentId ? { ...item, ...patch } : item,
  )
}

const documentStatusPollTimers = new Map<number, number>()

function startDocumentStatusPoll(documentId: number) {
  stopDocumentStatusPoll(documentId)
  const timer = window.setInterval(() => {
    if (!parseTasks.isRunning(documentId)) {
      stopDocumentStatusPoll(documentId)
      return
    }
    void fetchDocumentPage({ withLoading: false })
  }, 5000)
  documentStatusPollTimers.set(documentId, timer)
}

function stopDocumentStatusPoll(documentId: number) {
  const timer = documentStatusPollTimers.get(documentId)
  if (timer != null) {
    window.clearInterval(timer)
    documentStatusPollTimers.delete(documentId)
  }
}

function pruneProcessingDocumentIds() {
  for (const [documentId, task] of parseTasks.tasks.entries()) {
    if (!documents.value.some((d) => d.id === documentId) && task.status !== 'running') {
      parseTasks.tasks.delete(documentId)
    }
  }
}

const allDocumentsOnPageSelected = computed(() => {
  const pageDocs = documents.value
  if (pageDocs.length === 0) {
    return false
  }
  return pageDocs.every((d) => selectedDocumentIds.value.includes(d.id))
})

const someDocumentsOnPageSelected = computed(() => {
  const pageDocs = documents.value
  if (pageDocs.length === 0) {
    return false
  }
  const some = pageDocs.some((d) => selectedDocumentIds.value.includes(d.id))
  return some && !allDocumentsOnPageSelected.value
})

/** 仅当「当前所选全部在列表中可见」且其中无可解析项时禁用批量解析；跨页所选仍允许尝试。 */
const canBatchParseSelection = computed(() => {
  const sel = new Set(selectedDocumentIds.value)
  if (sel.size === 0) {
    return false
  }
  const onPage = documents.value.filter((d) => sel.has(d.id))
  const everySelectedOnThisPage = onPage.length === sel.size
  if (everySelectedOnThisPage) {
    return onPage.some(documentCanBatchParse)
  }
  return true
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

/** file_name 相对路径的最后一段去掉扩展名，与 document_name 对比 */
function fileStemFromUploadName(fileName: string) {
  const normalized = fileName.replace(/\\/g, '/').trim()
  const base = normalized.split('/').pop() ?? normalized
  const dot = base.lastIndexOf('.')
  return dot > 0 ? base.slice(0, dot) : base
}

/**
 * 第二行展示完整 file_name：仅在相对路径、或与标题明显不同时显示，避免与 document_name 重复占高。
 */
function shouldShowDocumentFileSubtitle(document: KnowledgeDocument) {
  const fn = document.file_name?.trim() ?? ''
  if (!fn) {
    return false
  }
  const dn = document.document_name?.trim() ?? ''
  if (fn.includes('/') || fn.includes('\\')) {
    return true
  }
  const stem = fileStemFromUploadName(fn)
  return stem !== dn
}

function openNativeFilePicker() {
  fileInputRef.value?.click()
}

function openFolderPicker() {
  folderInputRef.value?.click()
}

function clearSelectedFiles() {
  uploadFiles.value = []
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
  if (folderInputRef.value) {
    folderInputRef.value.value = ''
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
  clearSelectedFiles()
}

function handleMultiFileInputChange(event: Event) {
  const input = event.target as HTMLInputElement
  const list = input.files ? Array.from(input.files) : []
  addFilesToQueue(list)
  input.value = ''
}

function handleFileDrop(event: DragEvent) {
  isDragOver.value = false
  const list = event.dataTransfer?.files ? Array.from(event.dataTransfer.files) : []
  addFilesToQueue(list)
}

function removeQueuedFile(index: number) {
  uploadFiles.value = uploadFiles.value.filter((_, itemIndex) => itemIndex !== index)
}

async function fetchDocumentPage(options?: { withLoading?: boolean }) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    documents.value = []
    documentsTotal.value = 0
    return
  }
  const withLoading = options?.withLoading !== false
  if (withLoading) {
    documentsLoading.value = true
  }
  try {
    const kw = documentKeyword.value.trim()
    const params = {
      page: documentsPage.value,
      page_size: documentsPageSize.value,
      keyword: kw || undefined,
      status: documentStatusFilter.value === 'all' ? undefined : documentStatusFilter.value,
      sort: documentListSort.value,
    }
    let data = await knowledgeBaseApi.listDocuments(kbId.value, params)
    const lastPage = Math.max(1, Math.ceil(data.total / documentsPageSize.value) || 1)
    if (data.total > 0 && documentsPage.value > lastPage) {
      documentsPage.value = lastPage
      data = await knowledgeBaseApi.listDocuments(kbId.value, { ...params, page: lastPage })
    }
    documentsTotal.value = data.total
    documents.value = data.items.map(applyLocalProcessingOverlay)
    pruneProcessingDocumentIds()
  } catch (value) {
    const hasActiveParse = parseTasks.runningDocumentIds().length > 0
    if (withLoading || !hasActiveParse) {
      showNotice(getKnowledgeBaseErrorMessage(value, '加载文档列表失败'), 'error')
    }
  } finally {
    if (withLoading) {
      documentsLoading.value = false
    }
  }
}

async function fetchRecentActivity() {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    recentActivityDocuments.value = []
    return
  }
  try {
    const data = await knowledgeBaseApi.listDocuments(kbId.value, {
      page: 1,
      page_size: 12,
      sort: 'updated_desc',
    })
    recentActivityDocuments.value = data.items
  } catch {
    recentActivityDocuments.value = []
  }
}

async function refreshDocuments() {
  await fetchDocumentPage()
  await fetchRecentActivity()
}

function goDocumentsPagePrev() {
  if (documentsPage.value <= 1 || documentsLoading.value) {
    return
  }
  documentsPage.value -= 1
  void fetchDocumentPage()
}

function goDocumentsPageNext() {
  if (documentsPage.value >= documentsTotalPages.value || documentsLoading.value) {
    return
  }
  documentsPage.value += 1
  void fetchDocumentPage()
}

function onChunkingSettingsSaved(updated: KnowledgeBase) {
  knowledgeBase.value = updated
}

function onRetrievalSettingsSaved(updated: KnowledgeBase) {
  skipRetrievalFormAutoSave.value = true
  knowledgeBase.value = updated
  searchForm.value = retrievalFormFromKnowledgeBase(updated)
  nextTick(() => {
    skipRetrievalFormAutoSave.value = false
  })
}

function markRetrievalConfigSaved() {
  retrievalConfigSaved.value = true
  if (retrievalConfigSavedTimer != null) {
    window.clearTimeout(retrievalConfigSavedTimer)
  }
  retrievalConfigSavedTimer = window.setTimeout(() => {
    retrievalConfigSaved.value = false
    retrievalConfigSavedTimer = null
  }, 2000)
}

async function saveRetrievalConfigFromForm() {
  if (!knowledgeBase.value || !kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  const err = validateRetrievalForm(searchForm.value)
  if (err) {
    return
  }
  retrievalConfigSaving.value = true
  try {
    const payload = buildRetrievalUpdatePayload(searchForm.value, knowledgeBase.value.config)
    const updated = await knowledgeBaseApi.update(kbId.value, payload)
    knowledgeBase.value = updated
    markRetrievalConfigSaved()
  } catch (value) {
    searchError.value = getKnowledgeBaseErrorMessage(value, '保存检索配置失败')
  } finally {
    retrievalConfigSaving.value = false
  }
}

function scheduleRetrievalConfigSave() {
  if (skipRetrievalFormAutoSave.value) {
    return
  }
  if (retrievalFormSaveTimer != null) {
    window.clearTimeout(retrievalFormSaveTimer)
  }
  retrievalFormSaveTimer = window.setTimeout(() => {
    retrievalFormSaveTimer = null
    void saveRetrievalConfigFromForm()
  }, 500)
}

async function resetSearchForm() {
  skipRetrievalFormAutoSave.value = true
  searchForm.value = defaultRetrievalFormState()
  skipRetrievalFormAutoSave.value = false
  await saveRetrievalConfigFromForm()
}

async function loadLlmModels() {
  llmModelsLoading.value = true
  try {
    const [modelsData, defaultsData] = await Promise.all([
      modelApi.getModels({ model_type: 'llm', is_enabled: true, view: 'flat' }),
      defaultModelApi.getDefaults(),
    ])
    llmModels.value = modelsData as ModelItem[]
    defaultLlmModel.value = defaultsData.llm
  } catch (value) {
    showNotice(getModelErrorMessage(value, '加载 LLM 模型列表失败'), 'error')
  } finally {
    llmModelsLoading.value = false
  }
}

async function saveExtractLlmModel(modelId: number | null) {
  if (!kbId.value || Number.isNaN(kbId.value) || !knowledgeBase.value) {
    return
  }
  savingExtractLlm.value = true
  try {
    const currentConfig =
      knowledgeBase.value.config && typeof knowledgeBase.value.config === 'object'
        ? { ...(knowledgeBase.value.config as Record<string, unknown>) }
        : {}
    const nextLightrag = { ...getLightragConfigRecord(knowledgeBase.value) }
    if (modelId == null) {
      delete nextLightrag.extract_llm_id
    } else {
      nextLightrag.extract_llm_id = modelId
    }
    const updated = await knowledgeBaseApi.update(kbId.value, {
      config: { ...currentConfig, lightrag: nextLightrag },
    })
    knowledgeBase.value = updated
    showNotice(
      '实体抽取 LLM 已更新。新配置将在后续解析或重建图谱时生效；已入库文档如需切换模型请重建图谱。',
      'success',
      6000,
    )
  } catch (value) {
    showNotice(getKnowledgeBaseErrorMessage(value, '更新实体抽取 LLM 失败'), 'error')
  } finally {
    savingExtractLlm.value = false
  }
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
    let hasIndexed = false
    try {
      const indexedPage = await knowledgeBaseApi.listDocuments(kbId.value, {
        status: 'indexed',
        page: 1,
        page_size: 1,
      })
      hasIndexed = indexedPage.total > 0
    } catch {
      hasIndexed = false
    }
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
  selectedDocumentIds.value = []
  try {
    documentsPage.value = 1
    knowledgeBase.value = await knowledgeBaseApi.get(kbId.value)
    skipRetrievalFormAutoSave.value = true
    searchForm.value = retrievalFormFromKnowledgeBase(knowledgeBase.value)
    nextTick(() => {
      skipRetrievalFormAutoSave.value = false
    })
    await Promise.all([
      refreshDocuments(),
      loadEmbeddingModels(),
      ...(knowledgeBase.value?.kb_type === 'lightrag' ? [loadLlmModels()] : []),
    ])
  } catch (value) {
    error.value = getKnowledgeBaseErrorMessage(value, '加载知识库详情失败')
  } finally {
    loading.value = false
  }
}

async function submitUpload() {
  if (!kbId.value || Number.isNaN(kbId.value) || uploadFiles.value.length === 0) {
    uploadError.value = '请选择要上传的文件'
    return
  }
  uploading.value = true
  uploadError.value = ''
  uploadProgress.value = 0
  const okNames: string[] = []
  const failures: string[] = []
  const queue = [...uploadFiles.value]
  const total = queue.length
  try {
    for (let index = 0; index < total; index += 1) {
      const file = queue[index]
      uploadProgress.value = index + 1
      try {
        await knowledgeBaseApi.uploadDocument(kbId.value, { file })
        okNames.push(file.name)
      } catch (value) {
        failures.push(`${file.name}：${getKnowledgeBaseErrorMessage(value, '上传失败')}`)
      }
    }
    await refreshDocuments()
    if (failures.length === 0) {
      closeUploadModal()
      showToast(
        okNames.length === 1
          ? `「${okNames[0]}」上传成功，已加入列表。请点击「开始解析」完成分块与索引。`
          : `已成功上传 ${okNames.length} 个文件，已加入列表。请点击「开始解析」完成分块与索引。`,
        okNames.length === 1 ? 4000 : 5000,
      )
    } else {
      uploadError.value =
        failures.length === total
          ? `全部上传失败：${failures.join('；')}`
          : `部分失败（${failures.length}/${total}）：${failures.join('；')}`
      if (okNames.length > 0) {
        showToast(`已上传 ${okNames.length} 个文件，另有 ${failures.length} 个失败，请查看下方错误信息。`, 5000)
      }
    }
  } finally {
    uploading.value = false
    uploadProgress.value = 0
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
  phase: 'running' | 'success' | 'error' | 'cancelled'
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
  const task = parseTasks.getTask(documentId)
  const lines = task && task.logs.length > 0 ? task.logs : parseLogLines.value
  if (lines.length === 0) {
    return
  }
  try {
    const phase =
      task?.status === 'success'
        ? 'success'
        : task?.status === 'error'
          ? 'error'
          : task?.status === 'cancelled'
            ? 'cancelled'
            : parseLogPhase.value
    const payload: ParseLogSnapshot = {
      kind: task?.mode ?? parseLogKind.value,
      phase,
      lines: [...lines],
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
  if (parseTasks.isRunning(document.id)) {
    return false
  }
  const task = parseTasks.getTask(document.id)
  if (task && task.logs.length > 0) {
    return true
  }
  if (parseLogDocumentId.value === document.id && parseLogLines.value.length > 0) {
    return true
  }
  if (document.status === 'indexed' || document.status === 'failed' || document.status === 'graph_indexed' || document.status === 'graph_failed') {
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
      if (document.status === 'indexed' || document.status === 'graph_indexed') {
        parseLogPhase.value = 'success'
      } else if (document.status === 'failed' || document.status === 'graph_failed') {
        parseLogPhase.value = 'error'
      } else {
        parseLogPhase.value = 'running'
      }
    }
  }

  showParseLogModal.value = true

  const skipServerFetch = parseTasks.isRunning(document.id)
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
  const task = parseTasks.getTask(document.id)
  if (parseTasks.isRunning(document.id)) {
    return 'parse-log-dot--running'
  }
  if (task) {
    if (task.status === 'success') {
      return 'parse-log-dot--success'
    }
    if (task.status === 'error' || task.status === 'cancelled') {
      return 'parse-log-dot--error'
    }
  }
  if (document.status === 'failed' || document.status === 'graph_failed') {
    return 'parse-log-dot--error'
  }
  if (document.status === 'indexed' || document.status === 'graph_indexed') {
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
  const task = parseTasks.getTask(document.id)
  if (parseTasks.isRunning(document.id)) {
    const verb = task?.mode === 'reindex' ? '重建' : '解析'
    return `${verb}进行中 ${task?.percent.toFixed(2) ?? '0.00'}%，点击查看日志`
  }
  if (task) {
    if (task.status === 'success') {
      return '解析已完成，点击查看日志'
    }
    if (task.status === 'error') {
      return '解析失败，点击查看日志'
    }
    if (task.status === 'cancelled') {
      return '解析已取消，点击查看日志'
    }
  }
  if (parseLogDocumentId.value === document.id) {
    if (parseLogPhase.value === 'success') {
      return '解析已完成，点击查看日志'
    }
    if (parseLogPhase.value === 'error') {
      return '解析失败，点击查看日志'
    }
    return '查看解析日志'
  }
  if (document.status === 'failed' || document.status === 'graph_failed') {
    return '解析失败，点击查看解析日志'
  }
  if (document.status === 'indexed' || document.status === 'graph_indexed') {
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

async function resolveDocumentForBatchParse(documentId: number): Promise<KnowledgeDocument | null> {
  const cached = documents.value.find((d) => d.id === documentId)
  if (cached) {
    return cached
  }
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return null
  }
  try {
    return await knowledgeBaseApi.getDocument(kbId.value, documentId)
  } catch {
    return null
  }
}

async function runDocumentParseSilent(documentId: number): Promise<{ ok: boolean; message?: string }> {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return { ok: false, message: '知识库无效' }
  }

  const meta = await resolveDocumentForBatchParse(documentId)
  if (!meta) {
    return { ok: false, message: '无法获取文档状态' }
  }

  const needsForce = documentIsStuckProcessing(meta)
  if (parseTasks.isRunning(documentId)) {
    if (!needsForce) {
      return { ok: false, message: '文档正在解析中' }
    }
    await parseTasks.cancelTask(documentId)
  }

  const mode: 'parse' | 'reindex' =
    documentIsIndexed(meta) ||
    (isLightragKb.value && needsForce && meta.status === 'graph_indexing')
      ? 'reindex'
      : 'parse'
  const optimisticStatus =
    mode === 'reindex' ? (isLightragKb.value ? 'graph_indexing' : 'indexing') : 'parsing'

  parseLogDocumentId.value = documentId
  patchDocumentInList(documentId, { status: optimisticStatus })
  startDocumentStatusPoll(documentId)
  void fetchDocumentPage({ withLoading: false })
  try {
    const result = await parseTasks.startTask(documentId, mode, { force: needsForce })
    if (result) {
      endDocumentStreamProcessing(documentId, result)
      return { ok: true }
    }
    return { ok: false, message: '已取消' }
  } catch (value) {
    return { ok: false, message: getKnowledgeBaseErrorMessage(value, '解析失败') }
  } finally {
    stopDocumentStatusPoll(documentId)
    persistParseLogSnapshot(documentId)
  }
}

async function runWithConcurrencyLimit<T>(
  items: number[],
  limit: number,
  fn: (documentId: number) => Promise<T>,
): Promise<T[]> {
  const results = new Array<T>(items.length)
  let cursor = 0
  async function worker() {
    while (cursor < items.length) {
      const index = cursor
      cursor += 1
      results[index] = await fn(items[index])
    }
  }
  const workers = Math.min(Math.max(limit, 1), items.length)
  await Promise.all(Array.from({ length: workers }, () => worker()))
  return results
}

function onDocumentRowCheckboxChange(document: KnowledgeDocument, event: Event) {
  if (documentsLoading.value || batchParsing.value || batchDeleting.value) {
    return
  }
  const checked = (event.target as HTMLInputElement).checked
  if (checked) {
    if (!selectedDocumentIds.value.includes(document.id)) {
      selectedDocumentIds.value = [...selectedDocumentIds.value, document.id]
    }
  } else {
    selectedDocumentIds.value = selectedDocumentIds.value.filter((id) => id !== document.id)
  }
}

function toggleSelectAllOnPage(event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  const pageIds = documents.value.map((d) => d.id)
  if (checked) {
    selectedDocumentIds.value = [...new Set([...selectedDocumentIds.value, ...pageIds])]
  } else {
    const remove = new Set(pageIds)
    selectedDocumentIds.value = selectedDocumentIds.value.filter((id) => !remove.has(id))
  }
}

function clearDocumentSelection() {
  selectedDocumentIds.value = []
}

async function batchParseSelectedDocuments() {
  const ids = [...new Set(selectedDocumentIds.value)]
  if (!kbId.value || Number.isNaN(kbId.value) || ids.length === 0) {
    return
  }
  batchParsing.value = true
  let ok = 0
  let fail = 0
  const concurrency = isLightragKb.value ? 2 : 4
  try {
    const results = await runWithConcurrencyLimit(ids, concurrency, async (documentId) => {
      const result = await runDocumentParseSilent(documentId)
      await fetchDocumentPage({ withLoading: false })
      return result
    })
    for (const result of results) {
      if (result.ok) {
        ok += 1
      } else {
        fail += 1
      }
    }
    await fetchRecentActivity()
    clearDocumentSelection()
    if (fail === 0) {
      showNotice(`已批量解析完成，共 ${ok} 个文件。`, 'success', 4000)
    } else {
      showNotice(
        `批量解析结束：成功 ${ok} 个，失败 ${fail} 个。`,
        fail === ids.length ? 'error' : 'info',
        6000,
      )
    }
  } finally {
    batchParsing.value = false
  }
}

async function cancelDocumentParseAction(documentId: number) {
  if (!window.confirm('确定停止该文档的解析吗？已写入的部分将被清理。')) {
    return
  }
  const snapshot = await parseTasks.cancelTask(documentId)
  stopDocumentStatusPoll(documentId)
  parseLogDocumentId.value = documentId
  parseLogPhase.value = 'cancelled'
  if (snapshot) {
    patchDocumentInList(documentId, snapshot)
  } else {
    patchDocumentInList(documentId, {
      status: 'uploaded',
      error_message: '用户已取消解析',
      chunk_count: 0,
    })
  }
  await refreshDocuments()
  showNotice('已停止解析', 'info', 3000)
}

async function forceRestartParseAction(document: KnowledgeDocument) {
  if (parseTasks.isRunning(document.id)) {
    await parseTasks.cancelTask(document.id)
  }
  endDocumentStreamProcessing(document.id)
  const status = document.status
  if (isLightragKb.value && (status === 'graph_indexing' || status === 'graph_failed')) {
    await reindexDocumentAction(document.id, { force: true })
  } else {
    await parseDocumentAction(document.id, { force: true })
  }
}

async function parseDocumentAction(documentId: number, options?: { force?: boolean }) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  const meta = documents.value.find((d) => d.id === documentId)
  const needsForce = Boolean(options?.force || (meta && documentIsStuckProcessing(meta)))
  if (parseTasks.isRunning(documentId) && !needsForce) {
    return
  }
  if (needsForce && parseTasks.isRunning(documentId)) {
    await parseTasks.cancelTask(documentId)
  }
  parseLogDocumentId.value = documentId
  parseLogKind.value = 'parse'
  parseLogTitle.value = meta?.file_name || `文档 #${documentId}`
  parseLogLines.value = []
  parseLogPhase.value = 'running'
  patchDocumentInList(documentId, { status: 'parsing' })
  startDocumentStatusPoll(documentId)
  void fetchDocumentPage({ withLoading: false })
  try {
    const result = await parseTasks.startTask(documentId, 'parse', { force: needsForce })
    if (result) {
      endDocumentStreamProcessing(documentId, result)
      parseLogPhase.value = 'success'
      await refreshDocuments()
      showNotice(
        needsForce
          ? isLightragKb.value
            ? '强制重跑：解析与图谱入库已完成。'
            : '强制重跑：解析与索引已完成。'
          : isLightragKb.value
            ? '解析与图谱入库已完成。'
            : '解析与索引已完成。',
      )
    } else {
      parseLogPhase.value = 'cancelled'
    }
  } catch (value) {
    parseLogPhase.value = 'error'
    showNotice(getKnowledgeBaseErrorMessage(value, '解析失败'), 'error')
  } finally {
    endDocumentStreamProcessing(documentId)
    persistParseLogSnapshot(documentId)
  }
}

async function reindexDocumentAction(documentId: number, options?: { force?: boolean }) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  if (parseTasks.isRunning(documentId) && !options?.force) {
    return
  }
  if (options?.force && parseTasks.isRunning(documentId)) {
    await parseTasks.cancelTask(documentId)
  }
  const meta = documents.value.find((d) => d.id === documentId)
  parseLogDocumentId.value = documentId
  parseLogKind.value = 'reindex'
  parseLogTitle.value = meta?.file_name || `文档 #${documentId}`
  parseLogLines.value = []
  parseLogPhase.value = 'running'
  patchDocumentInList(documentId, {
    status: isLightragKb.value ? 'graph_indexing' : 'indexing',
  })
  startDocumentStatusPoll(documentId)
  void fetchDocumentPage({ withLoading: false })
  try {
    const result = await parseTasks.startTask(documentId, 'reindex', { force: options?.force })
    if (result) {
      endDocumentStreamProcessing(documentId, result)
      parseLogPhase.value = 'success'
      await refreshDocuments()
      showNotice(
        options?.force
          ? isLightragKb.value
            ? '强制重跑：重建图谱已完成。'
            : '强制重跑：重建索引已完成。'
          : isLightragKb.value
            ? '重建图谱已完成。'
            : '重建索引已完成。',
      )
    } else {
      parseLogPhase.value = 'cancelled'
    }
  } catch (value) {
    parseLogPhase.value = 'error'
    showNotice(getKnowledgeBaseErrorMessage(value, '重建索引失败'), 'error')
  } finally {
    endDocumentStreamProcessing(documentId)
    persistParseLogSnapshot(documentId)
  }
}

async function batchDeleteSelectedDocuments() {
  const ids = [...new Set(selectedDocumentIds.value)]
  if (!kbId.value || Number.isNaN(kbId.value) || ids.length === 0) {
    return
  }
  if (!window.confirm(`确定删除已选的 ${ids.length} 个文档吗？此操作不可恢复。`)) {
    return
  }
  batchDeleting.value = true
  let ok = 0
  let fail = 0
  try {
    for (const documentId of ids) {
      deletingDocumentIds.value = [...deletingDocumentIds.value, documentId]
      try {
        await knowledgeBaseApi.deleteDocument(kbId.value, documentId)
        try {
          sessionStorage.removeItem(parseLogStorageKey(documentId))
        } catch {
          /* ignore */
        }
        ok += 1
      } catch {
        fail += 1
      } finally {
        deletingDocumentIds.value = deletingDocumentIds.value.filter((item) => item !== documentId)
      }
    }
    clearDocumentSelection()
    await refreshDocuments()
    if (fail === 0) {
      showNotice(`已删除 ${ok} 个文档。`, 'success', 4000)
    } else {
      showNotice(`删除结束：成功 ${ok} 个，失败 ${fail} 个。`, fail === ids.length ? 'error' : 'info', 6000)
    }
  } finally {
    batchDeleting.value = false
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

watch(showGraphTab, () => {
  syncDetailTabFromRoute()
})

watch(
  () => [route.query[GRAPH_TAB_QUERY_KEY], route.query[GRAPH_ENTITY_QUERY_KEY], showGraphTab.value] as const,
  () => {
    syncDetailTabFromRoute()
    const entity = graphEntityFromRoute.value
    if (entity && activeTab.value === 'graph') {
      graphPanelRef.value?.focusEntity(entity)
    }
  },
  { immediate: true },
)


watch(documentsPageSize, () => {
  documentsPage.value = 1
  void fetchDocumentPage()
})

watch(documentKeyword, () => {
  documentsPage.value = 1
  if (documentKeywordDebounceTimer != null) {
    window.clearTimeout(documentKeywordDebounceTimer)
  }
  documentKeywordDebounceTimer = window.setTimeout(() => {
    documentKeywordDebounceTimer = null
    void fetchDocumentPage()
  }, 350)
})

watch(documentStatusFilter, () => {
  documentsPage.value = 1
  void fetchDocumentPage()
})

watch(sortOrder, () => {
  documentsPage.value = 1
  void fetchDocumentPage()
})

watch(
  searchForm,
  () => {
    scheduleRetrievalConfigSave()
  },
  { deep: true },
)

watch(
  [allDocumentsOnPageSelected, someDocumentsOnPageSelected, documents],
  () => {
    nextTick(() => {
      const el = headerSelectAllRef.value
      if (el) {
        el.indeterminate = someDocumentsOnPageSelected.value
      }
    })
  },
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

.pdf-parser-hint {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 0.82rem;
  line-height: 1.5;
}

.extract-llm-section .pdf-parser-hint {
  display: none;
}

.extract-llm-section:focus-within .pdf-parser-hint,
.extract-llm-section:hover .pdf-parser-hint {
  display: block;
}

.knowledge-detail-view {
  display: grid;
  gap: 16px;
}

.knowledge-detail-layout {
  --detail-sidebar-width: 168px;
  display: grid;
  grid-template-columns: var(--detail-sidebar-width) minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
}

.detail-sidebar {
  display: flex;
  flex-direction: column;
  align-self: stretch;
  min-height: 100%;
}

.detail-sidebar-nav {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 14px;
  min-height: 100%;
  padding: 20px 12px;
}

.detail-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 13px 14px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.45;
  text-align: left;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
}

.detail-nav-item:hover {
  background: var(--bg-tertiary);
}

.detail-nav-item.active {
  font-weight: 700;
  background: color-mix(in srgb, var(--brand-primary) 6%, var(--bg-tertiary));
  border-color: var(--border-color);
}

.detail-nav-icon {
  flex-shrink: 0;
  width: 18px;
  color: color-mix(in srgb, var(--text-primary) 78%, var(--text-tertiary));
}

.detail-nav-item:hover .detail-nav-icon {
  color: var(--text-primary);
}

.detail-nav-item.active .detail-nav-icon {
  color: var(--brand-primary);
}

.detail-nav-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.detail-main,
.content-card,
.activity-list,
.search-result-list {
  display: grid;
  gap: 18px;
}

.detail-main {
  min-height: 100%;
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

.document-meta-cell,
.document-table-head,
.table-actions-head,
.search-result-meta-row,
.activity-header p {
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.content-card {
  padding: 24px;
}

.documents-toolbar {
  gap: 14px;
}

.documents-batch-actions {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
  margin-left: auto;
}

.documents-batch-count {
  font-size: 0.88rem;
  color: var(--text-secondary);
  white-space: nowrap;
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
  grid-template-columns: 36px minmax(140px, 1.6fr) minmax(108px, 0.9fr) 0.6fr 0.72fr 0.5fr 0.5fr minmax(272px, 1.25fr);
  gap: 8px 10px;
  align-items: center;
}

.document-table-head {
  padding: 0 12px 8px;
  font-weight: 700;
  font-size: 0.8rem;
  border-bottom: 1px solid var(--border-color);
}

.document-table-body {
  display: grid;
  gap: 8px;
}

.documents-pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 14px 20px;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid var(--border-color);
}

.documents-pagination-meta {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.documents-pagination-size {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin: 0;
}

.documents-pagination-size .field-label {
  margin: 0;
  white-space: nowrap;
}

.documents-pagination-size .select {
  min-width: 88px;
}

.documents-pagination-nav {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.documents-pagination-page {
  font-size: 0.9rem;
  color: var(--text-primary);
  min-width: 72px;
  text-align: center;
}

.document-row {
  position: relative;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-tertiary);
  box-shadow: none;
}

.doc-checkbox {
  width: 16px;
  height: 16px;
  margin: 0;
  cursor: pointer;
  accent-color: var(--brand-primary);
}

.document-col-check {
  display: flex;
  align-items: center;
  justify-content: center;
}

.document-row-check {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  cursor: pointer;
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
  border-radius: 8px;
  padding: 3px 6px;
  margin: -3px -6px;
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

.document-row .row-actions.document-row-actions .btn-row {
  min-width: 0;
}

.document-row .row-actions.document-row-actions {
  display: inline-flex;
  justify-content: flex-end;
  flex-wrap: nowrap;
  gap: 5px;
  align-items: center;
  min-width: 0;
  white-space: nowrap;
}

.document-row .row-actions.document-row-actions .btn-row-compact {
  min-width: 0;
  flex-shrink: 0;
  padding: 3px 7px;
  font-size: 0.7rem;
  line-height: 1.2;
  white-space: nowrap;
}

.document-row .row-actions.document-row-actions .doc-parse-progress {
  flex: 0 1 auto;
}

.document-row .row-actions.document-row-actions .parse-log-dot-btn {
  flex-shrink: 0;
}

.document-row .row-actions.document-row-actions .kebab-menu {
  flex-shrink: 0;
}

.document-row .document-main-cell strong {
  font-size: 0.88rem;
  font-weight: 600;
  line-height: 1.25;
}

.document-row .document-main-cell p {
  margin: 1px 0 0;
  line-height: 1.3;
  font-size: 0.75rem;
}

.document-row .document-meta-cell {
  font-size: 0.76rem;
  line-height: 1.3;
}

.document-row .status-pill {
  font-size: 0.68rem;
  padding: 1px 7px;
  line-height: 1.35;
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
  font-size: 0.78rem;
  color: var(--text-tertiary);
  padding: 0 2px;
  white-space: nowrap;
  flex-shrink: 0;
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
  margin-top: 2px;
  padding: 6px 10px;
  font-size: 0.78rem;
  line-height: 1.4;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}

.document-row-error-text {
  margin: 0;
  flex: 1 1 200px;
}

.document-row-error-action {
  flex: 0 0 auto;
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

.retrieval-config-save-hint {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.retrieval-config-save-hint.ok {
  color: var(--success-color);
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

.parse-log-progress-summary {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-secondary, #64748b);
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

.upload-folder-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
}

.upload-folder-hint {
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.55;
  max-width: 620px;
}

.upload-selected-panel {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-tertiary);
}

.upload-selected-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.upload-selected-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: min(240px, 40vh);
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.upload-selected-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
}

.upload-selected-meta {
  display: grid;
  gap: 4px;
  min-width: 0;
  flex: 1;
}

.upload-selected-name {
  display: block;
  color: var(--text-primary);
  font-size: 0.88rem;
  word-break: break-all;
}

.upload-selected-size {
  font-size: 0.8rem;
  color: var(--text-secondary);
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
    --detail-sidebar-width: 156px;
  }

  .document-table-head {
    display: none;
  }

  .document-table-head,
  .document-row {
    grid-template-columns: 34px minmax(100px, 1.35fr) minmax(88px, 0.8fr) 0.58fr 0.68fr 0.48fr 0.48fr minmax(240px, 1.15fr);
    gap: 6px 8px;
  }

  .document-row {
    align-items: center;
  }

  .document-row .row-actions.document-row-actions {
    flex-wrap: nowrap;
  }

  .document-row-error {
    grid-column: 1 / -1;
  }
}

@media (max-width: 900px) {
  .knowledge-detail-layout {
    --detail-sidebar-width: 140px;
    gap: 12px;
  }

  .detail-sidebar-nav {
    padding: 16px 10px;
    gap: 12px;
  }

  .detail-nav-item {
    padding: 12px 12px;
    gap: 8px;
    font-size: 0.875rem;
  }

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

.graph-viz-card {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  gap: 16px;
}

.knowledge-detail-view--graph-tab {
  --graph-viz-viewport-offset: 220px;
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--graph-viz-viewport-offset));
  min-height: 560px;
}

.knowledge-detail-view--graph-tab .knowledge-detail-layout {
  flex: 1;
  min-height: 0;
  align-items: stretch;
}

.knowledge-detail-view--graph-tab .detail-main {
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.knowledge-detail-view--graph-tab .graph-viz-card {
  padding-bottom: 20px;
}

.knowledge-detail-view--graph-tab .graph-viz-card .section-heading {
  flex-shrink: 0;
  margin: 0;
}

.knowledge-detail-view--graph-tab .graph-viz-card :deep(.graph-viz-panel) {
  flex: 1;
  min-height: 0;
}
</style>
