<template>
  <Layout>
    <div
      class="page-shell knowledge-detail-view"
      :class="{
        'knowledge-detail-view--graph-tab': activeTab === 'graph',
        'knowledge-detail-view--documents-tab': activeTab === 'documents',
      }"
    >
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
        <div
          class="knowledge-detail-layout"
          :class="{ 'knowledge-detail-layout--settings': activeTab === 'settings' }"
        >
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
            <section
              v-if="activeTab === 'documents'"
              class="surface-card content-card documents-card"
              :class="{ 'documents-card--fresh-empty': documentsListIsFreshEmpty }"
            >
              <div v-if="documentsListIsFreshEmpty" class="section-heading">
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

              <div v-if="!documentsListIsFreshEmpty" class="toolbar-row documents-toolbar documents-toolbar--compact">
                <label class="field toolbar-field toolbar-field-search">
                  <span class="field-label">搜索</span>
                  <div class="input-wrap">
                    <AppIcon name="search" class="input-icon" :size="16" />
                    <input v-model.trim="documentKeyword" class="input" type="text" placeholder="按文档名称搜索" />
                  </div>
                </label>

                <div class="field toolbar-field">
                  <AppSelect
                    v-model="documentStatusFilter"
                    label="状态"
                    :options="documentStatusFilterOptions"
                  />
                </div>

                <div v-if="showDocumentFileTypeFilter" class="field toolbar-field">
                  <AppSelect
                    v-model="documentFileTypeFilter"
                    label="类型"
                    :options="documentFileTypeFilterOptions"
                  />
                </div>

                <div class="field toolbar-field">
                  <AppSelect v-model="sortOrder" label="排序" :options="documentSortOptions" />
                </div>

                <div class="documents-toolbar-actions">
                  <button class="btn btn-secondary" type="button" @click="refreshDocuments">
                    <AppIcon name="refresh" :size="16" />
                    刷新
                  </button>
                  <button class="btn btn-primary" type="button" @click="openUploadModal">
                    <AppIcon name="plus" :size="16" />
                    新增文件
                  </button>
                </div>

                <div v-if="selectedDocumentIds.length > 0" class="documents-batch-actions">
                  <span class="documents-batch-count">已选 {{ selectedDocumentIds.length }} 项</span>
                  <button
                    class="btn btn-primary"
                    type="button"
                    :disabled="batchParsing || batchStopping || batchDeleting || documentsLoading || !canBatchParseSelection"
                    @click="batchParseSelectedDocuments"
                  >
                    {{ batchParsing ? '批量解析中…' : '批量解析' }}
                  </button>
                  <button
                    class="btn btn-secondary"
                    type="button"
                    :disabled="batchStopping || batchDeleting || documentsLoading || !canBatchStopSelection"
                    @click="batchStopSelectedDocuments"
                  >
                    {{ batchStopping ? '批量停止中…' : '批量停止' }}
                  </button>
                  <button
                    class="btn btn-danger"
                    type="button"
                    :disabled="batchParsing || batchStopping || batchDeleting || documentsLoading"
                    @click="batchDeleteSelectedDocuments"
                  >
                    {{ batchDeleting ? '批量删除中…' : '批量删除' }}
                  </button>
                  <button
                    class="btn btn-ghost"
                    type="button"
                    :disabled="batchParsing || batchStopping || batchDeleting"
                    @click="clearDocumentSelection"
                  >
                    清除选择
                  </button>
                </div>
              </div>

              <div v-if="documentsLoading" class="loading-skeleton document-skeleton"></div>

              <div v-else-if="documents.length === 0" class="documents-empty-wrap">
                <EmptyState
                  :title="documentListEmptyTitle"
                  :description="documentListEmptyDescription"
                  :compact="documentListFilterActive"
                >
                  <template #icon>
                    <AppIcon name="folder" :size="20" />
                  </template>
                  <template v-if="documentListFilterActive" #actions>
                    <button class="btn btn-ghost" type="button" @click="clearDocumentListFilters">
                      清除筛选
                    </button>
                  </template>
                </EmptyState>
              </div>

              <template v-else>
                <div class="documents-list-shell">
                <div class="document-table-wrap" :style="documentTableStyle">
                <div class="document-table document-table-head">
                  <span class="document-col-check">
                    <input
                      ref="headerSelectAllRef"
                      class="doc-checkbox"
                      type="checkbox"
                      :checked="allDocumentsOnPageSelected"
                      :disabled="documents.length === 0 || documentsLoading || batchParsing || batchStopping || batchDeleting"
                      aria-label="全选本页"
                      @change="toggleSelectAllOnPage"
                    />
                  </span>
                  <span class="document-col-name">
                    名称
                    <span
                      class="col-resize-handle"
                      role="separator"
                      aria-orientation="vertical"
                      aria-label="拖动调整名称列宽，双击恢复默认"
                      title="拖动调整列宽，双击恢复默认"
                      @mousedown.prevent="startDocumentNameColResize"
                      @dblclick.prevent="resetDocumentNameColWidth"
                    />
                  </span>
                  <span>上传时间</span>
                  <span class="document-col-compact">类型</span>
                  <span class="document-col-status">状态</span>
                  <span class="document-col-compact">分块数</span>
                  <span class="document-col-compact">解析器</span>
                  <span class="table-actions-head">动作</span>
                </div>

                <div class="document-table-body">
                  <article v-for="document in documents" :key="document.id" class="document-row">
                    <label class="document-row-check" @click.stop>
                      <input
                        class="doc-checkbox"
                        type="checkbox"
                        :checked="selectedDocumentIds.includes(document.id)"
                        :disabled="documentsLoading || batchParsing || batchStopping || batchDeleting"
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
                      <DocumentFileIcon :ext="document.file_ext || uploadExtension(document)" />
                      <div class="document-name-wrap">
                        <span class="document-name">{{ documentDisplayName(document) }}</span>
                      </div>
                    </div>
                    <span class="document-meta-cell">{{ formatApiDateTime(document.created_at) }}</span>
                    <span class="document-meta-cell document-col-compact">{{ documentUploadTypeDisplay(document) }}</span>
                    <span class="document-col-status">
                      <span :class="['status-pill', statusToneMap[getDocumentDisplayStatus(document)] || 'info']">
                        {{ statusLabelMap[getDocumentDisplayStatus(document)] || getDocumentDisplayStatus(document) }}
                      </span>
                    </span>
                    <span class="document-meta-cell document-col-compact">{{ document.chunk_count }}</span>
                    <span class="document-meta-cell document-col-compact">{{ documentParserDisplay(document, knowledgeBase) }}</span>
                    <div class="row-actions document-row-actions">
                      <DocumentParseProgress
                        v-if="parseTasks.isRunning(document.id) || documentIsStuckProcessing(document)"
                        :percent="documentProcessingPercent(document)"
                        :title="parseLogDotTitle(document)"
                        @open-log="openParseLogModal(document)"
                        @cancel="cancelDocumentParseAction(document.id)"
                      />
                      <template v-else-if="!documentIsStuckProcessing(document)">
                        <button
                          v-if="documentCanStartParse(document)"
                          class="btn btn-primary btn-row btn-row-compact"
                          type="button"
                          :disabled="batchParsing || batchStopping || batchDeleting"
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
                          :disabled="batchParsing || batchStopping || batchDeleting"
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
                    <div
                      v-if="documentIsParseFailed(document) && document.error_message"
                      class="document-row-error status-box error"
                    >
                      <p class="document-row-error-text">{{ document.error_message }}</p>
                      <button
                        v-if="documentCanStartParse(document) && !isDocumentRowBusy(document)"
                        class="btn btn-primary btn-row btn-row-compact document-row-error-action"
                        type="button"
                        :disabled="isDocumentProcessingLocally(document) || batchParsing || batchStopping || batchDeleting"
                        @click="parseDocumentAction(document.id)"
                      >
                        {{ isDocumentProcessingLocally(document) ? '解析中…' : '重新解析' }}
                      </button>
                    </div>
                  </article>
                </div>
                </div>

                <div v-if="documentsTotal > 0" class="documents-pagination">
                  <span class="documents-pagination-meta">共 {{ documentsTotal }} 条</span>
                  <label class="field documents-pagination-size">
                    <span class="field-label">每页</span>
                    <select v-model.number="documentsPageSize" class="select">
                      <option :value="12">12</option>
                      <option :value="15">15</option>
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
                </div>
              </template>
            </section>

            <section v-else-if="activeTab === 'retrieval'" class="surface-card content-card retrieval-card">
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
                      <RetrievalSearchResultList
                        :results="searchResults.results"
                        :mode="searchResults.mode"
                        :kb-id="kbId"
                      />
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
                <div class="form-grid graph-search-grid">
                  <label class="field">
                    <span class="field-label">查询模式</span>
                    <select v-model="graphSearchMode" class="select" :title="LIGHTRAG_MODE_DESC[graphSearchMode]">
                      <option value="mix" :title="LIGHTRAG_MODE_DESC.mix">mix（推荐）</option>
                      <option value="naive" :title="LIGHTRAG_MODE_DESC.naive">naive</option>
                      <option value="local" :title="LIGHTRAG_MODE_DESC.local">local</option>
                      <option value="global" :title="LIGHTRAG_MODE_DESC.global">global</option>
                      <option value="hybrid" :title="LIGHTRAG_MODE_DESC.hybrid">hybrid</option>
                    </select>
                  </label>
                  <label class="field">
                    <span class="field-label">Top K（实体/关系）</span>
                    <input v-model.number="graphSearchTopK" class="input" type="number" min="1" max="50" />
                  </label>
                  <label class="field">
                    <span class="field-label">片段数（chunk_top_k）</span>
                    <input
                      v-model.number="graphSearchChunkTopK"
                      class="input"
                      type="number"
                      min="1"
                      max="100"
                      placeholder="默认 20"
                    />
                  </label>
                </div>
                <button class="btn btn-primary" type="submit" :disabled="graphSearching || !graphSearchQuery">
                  {{ graphSearching ? '检索中…' : '开始图检索' }}
                </button>
              </form>
              <div v-if="graphSearchError" class="status-box error">{{ graphSearchError }}</div>
              <div v-else-if="graphSearchResult" class="graph-search-results">
                <div class="graph-search-summary">
                  <span class="chip chip-brand">{{ graphModeLabelMap[graphSearchResult.mode] || graphSearchResult.mode }}</span>
                  <span class="chip">{{ graphChunks.length }} 片段</span>
                  <span class="chip">{{ graphEntities.length }} 实体</span>
                  <span class="chip">{{ graphEntityConceptCount }} 概念</span>
                  <span class="chip">{{ graphRelationships.length }} 关系</span>
                  <span class="chip">{{ graphCitations.length }} 引用</span>
                </div>

                <div class="graph-result-tabs" role="tablist">
                  <button
                    v-for="t in graphResultTabs"
                    :key="t.key"
                    type="button"
                    class="graph-result-tab"
                    :class="{ 'graph-result-tab--active': graphResultTab === t.key }"
                    @click="graphResultTab = t.key"
                  >
                    {{ t.label }}
                    <span v-if="t.key !== 'context'" class="graph-result-tab-count">{{ t.count }}</span>
                  </button>
                </div>

                <div class="graph-result-body">
                  <!-- 文档片段 -->
                  <template v-if="graphResultTab === 'chunks'">
                    <EmptyState v-if="!graphChunks.length" title="本次未召回文档片段" description="当前模式可能只命中实体/关系，可切到「实体」「关系」查看，或改用 mix 模式。" compact>
                      <template #icon><AppIcon name="retrieval" :size="18" /></template>
                    </EmptyState>
                    <ol v-else class="graph-chunk-list">
                      <li v-for="(ck, idx) in graphChunks" :key="idx" class="graph-chunk-card">
                        <div class="graph-chunk-head">
                          <span class="graph-chunk-index">#{{ idx + 1 }}</span>
                          <span v-if="ck.source" class="graph-chunk-source">{{ ck.source }}</span>
                        </div>
                        <p class="graph-chunk-content">{{ ck.content }}</p>
                      </li>
                    </ol>
                  </template>

                  <!-- 实体 -->
                  <template v-else-if="graphResultTab === 'entities'">
                    <EmptyState v-if="!graphEntities.length" title="本次未命中实体" description="" compact>
                      <template #icon><AppIcon name="graph" :size="18" /></template>
                    </EmptyState>
                    <template v-else>
                      <div class="graph-entity-toolbar">
                        <p class="graph-entity-stats">
                          共 <strong>{{ graphEntities.length }}</strong> 个实体，
                          <strong>{{ graphEntityConceptCount }}</strong> 种概念（类型）；
                          鼠标悬停实体名称或类型标签约 0.7 秒可查看介绍。
                        </p>
                        <label class="graph-group-toggle">
                          <input v-model="graphEntityGroupBy" type="checkbox" />
                          <span>按类型分组</span>
                        </label>
                      </div>

                      <!-- 平铺视图：保留相关度排序 -->
                      <div v-if="!graphEntityGroupBy" class="graph-table-wrap">
                        <table class="graph-table">
                          <thead>
                            <tr><th>实体</th><th>类型</th><th>描述</th><th class="graph-table-action"></th></tr>
                          </thead>
                          <tbody>
                            <tr v-for="(ent, idx) in graphEntities" :key="idx">
                              <td class="graph-cell-name">
                                <DelayedHoverPopover v-if="ent.name" :delay-ms="700">
                                  <span class="graph-entity-name-trigger">{{ ent.name }}</span>
                                  <template #content>
                                    <p class="popover-title">{{ ent.name }}</p>
                                    <p class="popover-desc">{{ graphEntityIntro(ent) }}</p>
                                  </template>
                                </DelayedHoverPopover>
                                <span v-else>—</span>
                              </td>
                              <td>
                                <GraphEntityTypeChip v-if="ent.type" :type="ent.type" />
                                <span v-else>—</span>
                              </td>
                              <td class="graph-cell-desc">{{ ent.description || '—' }}</td>
                              <td class="graph-table-action">
                                <ViewInGraphLink v-if="ent.name" :kb-id="kbId" :entity-id="ent.name" />
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      <!-- 分组视图：按 entity_type 归堆 -->
                      <div v-else class="graph-entity-groups">
                        <section
                          v-for="grp in graphEntityGroups"
                          :key="grp.type"
                          class="graph-entity-group"
                        >
                          <div class="graph-entity-group-head" :style="{ '--type-color': entTypeColor(grp.type) }">
                            <GraphEntityTypeChip :type="grp.type" />
                            <span class="graph-entity-group-count">{{ grp.items.length }} 个实体</span>
                          </div>
                          <div class="graph-table-wrap">
                            <table class="graph-table">
                              <tbody>
                                <tr v-for="(ent, idx) in grp.items" :key="idx">
                                  <td class="graph-cell-name">
                                    <DelayedHoverPopover v-if="ent.name" :delay-ms="700">
                                      <span class="graph-entity-name-trigger">{{ ent.name }}</span>
                                      <template #content>
                                        <p class="popover-title">{{ ent.name }}</p>
                                        <p class="popover-desc">{{ graphEntityIntro(ent) }}</p>
                                      </template>
                                    </DelayedHoverPopover>
                                    <span v-else>—</span>
                                  </td>
                                  <td class="graph-cell-desc">{{ ent.description || '—' }}</td>
                                  <td class="graph-table-action">
                                    <ViewInGraphLink v-if="ent.name" :kb-id="kbId" :entity-id="ent.name" />
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </section>
                      </div>
                    </template>
                  </template>

                  <!-- 关系 -->
                  <template v-else-if="graphResultTab === 'relationships'">
                    <EmptyState v-if="!graphRelationships.length" title="本次未命中关系" description="" compact>
                      <template #icon><AppIcon name="graph" :size="18" /></template>
                    </EmptyState>
                    <div v-else class="graph-table-wrap">
                      <table class="graph-table">
                        <thead>
                          <tr><th>关系（起点 → 终点）</th><th>权重</th><th>关键词</th><th>描述</th></tr>
                        </thead>
                        <tbody>
                          <tr v-for="(rel, idx) in graphRelationships" :key="idx">
                            <td class="graph-cell-rel">
                              <span class="graph-rel-node">{{ rel.src || '—' }}</span>
                              <span class="graph-rel-arrow">→</span>
                              <span class="graph-rel-node">{{ rel.tgt || '—' }}</span>
                            </td>
                            <td>
                              <span
                                v-if="rel.weight != null"
                                class="graph-weight"
                                :class="`graph-weight--${relWeightLevel(rel.weight)}`"
                                :title="`权重 ${formatWeight(rel.weight)}`"
                              >
                                {{ relWeightLabel(rel.weight) }} {{ formatWeight(rel.weight) }}
                              </span>
                              <span v-else>—</span>
                            </td>
                            <td>{{ rel.keywords || '—' }}</td>
                            <td class="graph-cell-desc">{{ rel.description || '—' }}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </template>

                  <!-- 引用来源 -->
                  <template v-else-if="graphResultTab === 'citations'">
                    <EmptyState v-if="!graphCitations.length" title="本次无引用来源" description="" compact>
                      <template #icon><AppIcon name="retrieval" :size="18" /></template>
                    </EmptyState>
                    <ul v-else class="graph-citation-list">
                      <li v-for="cite in graphCitations" :key="cite.ref" class="graph-citation-item">
                        <span class="graph-citation-ref">[{{ cite.ref }}]</span>
                        <span class="graph-citation-name">{{ cite.document_name }}</span>
                      </li>
                    </ul>
                  </template>

                  <!-- 原始上下文 -->
                  <template v-else>
                    <p class="graph-context-hint">LightRAG 注入给大模型的完整上下文（实体/关系/片段/引用拼接），用于调试。</p>
                    <pre class="graph-context-raw">{{ graphSearchResult.answer_context || '（空）' }}</pre>
                  </template>
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

            <section v-else-if="activeTab === 'logs'" class="surface-card content-card kb-process-log">
              <div class="section-heading">
                <div>
                  <h3>处理日志</h3>
                  <p>按用户与批次汇总文档操作审计；单文档技术日志仍可在文件列表中查看。</p>
                </div>
                <button
                  class="btn btn-ghost"
                  type="button"
                  :disabled="processLogLoading"
                  @click="fetchProcessLogData"
                >
                  <AppIcon name="refresh" :size="16" />
                  刷新
                </button>
              </div>

              <section v-if="processLogLoading && !processLogSummary" class="kb-log-kpi-grid">
                <article v-for="n in 3" :key="n" class="kb-log-kpi-card kb-log-kpi-card--skeleton"></article>
              </section>
              <section v-else-if="processLogSummary" class="kb-log-kpi-grid">
                <article class="kb-log-kpi-card">
                  <span class="kb-log-kpi-icon tone-blue">
                    <AppIcon name="folder" :size="22" />
                  </span>
                  <div class="kb-log-kpi-body">
                    <p class="kb-log-kpi-value">{{ processLogSummary.total_documents }}</p>
                    <p class="kb-log-kpi-label">文件总数</p>
                  </div>
                </article>
                <article class="kb-log-kpi-card">
                  <span class="kb-log-kpi-icon tone-green">
                    <AppIcon name="check" :size="22" />
                  </span>
                  <div class="kb-log-kpi-body">
                    <p class="kb-log-kpi-value">{{ processLogSummary.indexed_documents }}</p>
                    <p class="kb-log-kpi-label">已完成解析</p>
                  </div>
                </article>
                <article class="kb-log-kpi-card">
                  <span class="kb-log-kpi-icon tone-teal">
                    <AppIcon name="bolt" :size="22" />
                  </span>
                  <div class="kb-log-kpi-body">
                    <p class="kb-log-kpi-value">{{ processLogSummary.processing_documents }}</p>
                    <p class="kb-log-kpi-label">正在处理</p>
                    <div class="kb-log-kpi-substats">
                      <span><i class="kb-log-dot kb-log-dot--success"></i>成功 {{ processLogSummary.recent_24h_success }}</span>
                      <span><i class="kb-log-dot kb-log-dot--failed"></i>失败 {{ processLogSummary.recent_24h_failed }}</span>
                    </div>
                  </div>
                </article>
              </section>

              <div class="kb-log-toolbar">
                <AppSelect
                  v-model="processLogActionFilter"
                  :options="processLogActionOptions"
                  aria-label="动作筛选"
                  class="kb-log-filter-select"
                />
                <input
                  v-model.trim="processLogKeyword"
                  class="input kb-log-search"
                  type="search"
                  placeholder="搜索用户、文件名或摘要"
                  @keydown.enter="fetchProcessLogEvents"
                />
                <button class="btn btn-secondary" type="button" :disabled="processLogLoading" @click="fetchProcessLogEvents">
                  搜索
                </button>
              </div>

              <EmptyState
                v-if="!processLogLoading && processLogEvents.length === 0"
                title="暂无审计记录"
                description="上传、解析、删除等操作会在这里按批次展示。历史操作无法回溯。"
                compact
              >
                <template #icon>
                  <AppIcon name="clock" :size="18" />
                </template>
              </EmptyState>

              <div v-else class="kb-log-table-wrap">
                <table class="kb-log-table">
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>用户</th>
                      <th>动作</th>
                      <th>数量</th>
                      <th>状态</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <template v-for="event in processLogEvents" :key="event.id">
                      <tr>
                        <td>{{ formatDate(event.started_at) }}</td>
                        <td>{{ event.username }}</td>
                        <td>
                          <div class="kb-log-action-cell">
                            <strong>{{ event.action_label }}</strong>
                            <span class="kb-log-summary">{{ event.summary }}</span>
                          </div>
                        </td>
                        <td>
                          <span>{{ event.total_count }}</span>
                          <span v-if="event.success_count" class="status-pill success">{{ event.success_count }} 成功</span>
                          <span v-if="event.failed_count" class="status-pill error">{{ event.failed_count }} 失败</span>
                        </td>
                        <td>
                          <span :class="['status-pill', processLogStatusTone(event.status)]">
                            {{ processLogStatusLabel(event.status) }}
                          </span>
                        </td>
                        <td>
                          <button
                            class="btn btn-ghost btn-sm"
                            type="button"
                            @click="toggleProcessLogBatchExpand(event.id)"
                          >
                            {{ expandedProcessLogBatchId === event.id ? '收起' : '展开' }}
                          </button>
                        </td>
                      </tr>
                      <tr v-if="expandedProcessLogBatchId === event.id" class="kb-log-expand-row">
                        <td colspan="6">
                          <div v-if="processLogBatchItemsLoading" class="kb-log-expand-loading">加载明细…</div>
                          <ul v-else-if="processLogBatchItems.length > 0" class="kb-log-item-list">
                            <li v-for="item in processLogBatchItems" :key="item.id" class="kb-log-item-row">
                              <DocumentFileIcon :ext="uploadExtension(item.file_name)" />
                              <span class="kb-log-item-name">{{ item.file_name }}</span>
                              <span :class="['status-pill', processLogItemStatusTone(item.status)]">
                                {{ processLogItemStatusLabel(item.status) }}
                              </span>
                              <span v-if="item.error_message" class="kb-log-item-error">{{ item.error_message }}</span>
                              <button
                                v-if="item.document_id && (item.status === 'failed' || item.status === 'cancelled')"
                                class="btn btn-ghost btn-sm"
                                type="button"
                                @click="openParseLogFromBatchItem(item)"
                              >
                                查看日志
                              </button>
                            </li>
                          </ul>
                          <p v-else class="kb-log-expand-empty">暂无明细</p>
                        </td>
                      </tr>
                    </template>
                  </tbody>
                </table>
              </div>

              <div v-if="processLogTotalPages > 1" class="kb-log-pagination">
                <button
                  class="btn btn-ghost btn-sm"
                  type="button"
                  :disabled="processLogPage <= 1 || processLogLoading"
                  @click="goProcessLogPage(processLogPage - 1)"
                >
                  上一页
                </button>
                <span>{{ processLogPage }} / {{ processLogTotalPages }}</span>
                <button
                  class="btn btn-ghost btn-sm"
                  type="button"
                  :disabled="processLogPage >= processLogTotalPages || processLogLoading"
                  @click="goProcessLogPage(processLogPage + 1)"
                >
                  下一页
                </button>
              </div>
            </section>

            <section
              v-else
              :class="['surface-card', 'content-card', { 'kb-settings-card--panel-open': parserSettingsExpanded }]"
            >
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

              <ParserSettingsPanel
                v-if="knowledgeBase"
                :knowledge-base="knowledgeBase"
                @saved="onKbSettingsSaved"
                @expanded-change="parserSettingsExpanded = $event"
              />

              <EnrichmentSettingsPanel
                v-if="knowledgeBase && !isLightragKb"
                :knowledge-base="knowledgeBase"
                @saved="onKbSettingsSaved"
              />

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
                {{ knowledgeBase?.name || '当前知识库' }} · 支持 txt / md / pdf / doc / docx / csv / Excel（xls、xlsx），可多选文件或整个文件夹。
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
              accept=".txt,.md,.pdf,.doc,.docx,.csv,.xls,.xlsx,.xlsm"
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
                支持一次选择多个文件，或拖入多个文件；格式包括 txt、md、pdf、doc、docx、csv、Excel（xls / xlsx / xlsm）。旧版 .doc 上传后将自动转换为 docx 再解析。
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
                uploading
                  ? `上传中 (${Math.max(uploadCompletedCount, uploadProgress)}/${uploadFiles.length})${
                      uploadCurrentFileName ? ` · ${uploadCurrentFileName}` : ''
                    }…`
                  : '保存并上传'
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
              <p v-if="activeParseLogPhase === 'running' && activeParseLogTask" class="parse-log-progress-summary">
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
  cancelDocumentProcess,
  getKnowledgeBaseErrorMessage,
  knowledgeBaseApi,
  type DocumentFileExtOption,
  type KbProcessLogBatchItem,
  type KbProcessLogEvent,
  type KbProcessLogSummary,
  type KnowledgeBase,
  type KnowledgeDocument,
  type KnowledgeSearchResponse,
  type RetrievalMode,
} from '../api/knowledge-base'
import { formatApiDateTime } from '../lib/formatDateTime'
import { createBatchId } from '../lib/batchId'
import { modelApi, defaultModelApi, getErrorMessage as getModelErrorMessage, type ModelItem, type DefaultModelOption } from '../api/model-management'
import AppIcon from '../components/AppIcon.vue'
import AppSelect from '../components/AppSelect.vue'
import ChunkingSettingsPanel from '../components/knowledge-base/ChunkingSettingsPanel.vue'
import EnrichmentSettingsPanel from '../components/knowledge-base/EnrichmentSettingsPanel.vue'
import ParserSettingsPanel from '../components/knowledge-base/ParserSettingsPanel.vue'
import DocumentFileIcon from '../components/DocumentFileIcon.vue'
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
import RetrievalSearchResultList from '../components/knowledge-base/RetrievalSearchResultList.vue'
import EmptyState from '../components/EmptyState.vue'
import GraphVisualizationPanel from '../components/graph/GraphVisualizationPanel.vue'
import { useDocumentParseTasks, wasUserCancelledParseTask } from '../composables/useDocumentParseTasks'
import { useLayoutPageContext } from '../composables/useLayoutPageContext'
import ViewInGraphLink from '../components/graph/ViewInGraphLink.vue'
import DelayedHoverPopover from '../components/graph/DelayedHoverPopover.vue'
import GraphEntityTypeChip from '../components/graph/GraphEntityTypeChip.vue'
import Layout from '../components/Layout.vue'
import { graphSearch, getGraphErrorMessage, type GraphSearchResponse, type LightRagQueryMode } from '../api/graph-knowledge-base'
import { GRAPH_ENTITY_QUERY_KEY, GRAPH_TAB_QUERY_KEY } from '../lib/graphNavigation'
import { colorForEntityType } from '../lib/graphEntityColors'
import { countDistinctEntityTypes } from '../lib/graphEntityTypeMeta'
import { documentParserDisplay, documentUploadTypeDisplay, uploadExtension } from '../lib/parserDisplay'

const route = useRoute()
const router = useRouter()
const { setPageContext, clearPageContext, setFillPage } = useLayoutPageContext()

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
const LIGHTRAG_MODE_DESC: Record<LightRagQueryMode, string> = {
  mix: 'mix（推荐）：综合知识图谱与向量检索，覆盖最全面，既能利用实体/关系，也能召回原文片段，适合大多数场景。',
  naive: 'naive：基础向量相似度检索，不使用图谱结构，等同于普通 RAG，速度快但缺少关系推理。',
  local: 'local：侧重实体的邻域（局部子图），适合针对某个具体实体、细节或定义的问题。',
  global: 'global：侧重全局关系与主题脉络，适合概览、归纳、跨文档关联类的问题。',
  hybrid: 'hybrid：同时执行 local 与 global 并融合结果，兼顾细节与全局，但不含 mix 的向量片段召回。',
}

const graphSearchQuery = ref('')
const graphSearchMode = ref<LightRagQueryMode>('mix')
const graphSearchTopK = ref(5)
const graphSearchChunkTopK = ref<number | null>(null)
const graphSearching = ref(false)
const graphSearchError = ref('')
const graphSearchResult = ref<GraphSearchResponse | null>(null)
type GraphResultTab = 'chunks' | 'entities' | 'relationships' | 'citations' | 'context'
const graphResultTab = ref<GraphResultTab>('chunks')
const graphEntityGroupBy = ref(false)
const entTypeColor = (type: string | null | undefined) => colorForEntityType(type)

const pick = (row: Record<string, unknown>, ...keys: string[]): string => {
  for (const k of keys) {
    const v = row[k]
    if (v !== undefined && v !== null && String(v).trim()) return String(v)
  }
  return ''
}

const cleanFilePath = (raw: string): string => raw.split('|||')[0].trim()

const graphEntities = computed(() =>
  (graphSearchResult.value?.entities ?? []).map((e) => ({
    name: pick(e, 'entity_name', 'entity_id', 'name'),
    type: pick(e, 'entity_type', 'type'),
    description: pick(e, 'description'),
    source: cleanFilePath(pick(e, 'file_path')),
  })),
)

const graphEntityConceptCount = computed(() =>
  countDistinctEntityTypes(graphEntities.value.map((e) => e.type)),
)

function graphEntityIntro(ent: { name: string; description: string }): string {
  const desc = ent.description?.trim()
  if (desc) {
    return desc
  }
  if (ent.name) {
    return `实体「${ent.name}」暂无详细描述，可结合检索问题、关系 Tab 或知识图谱可视化理解其在文档中的角色。`
  }
  return '暂无介绍'
}

const graphRelationships = computed(() =>
  (graphSearchResult.value?.relationships ?? []).map((r) => {
    const raw = pick(r, 'weight')
    const num = raw ? Number(raw) : NaN
    return {
      src: pick(r, 'src_id', 'entity1', 'source'),
      tgt: pick(r, 'tgt_id', 'entity2', 'target'),
      keywords: pick(r, 'keywords'),
      description: pick(r, 'description'),
      weight: Number.isFinite(num) ? num : null,
    }
  }),
)

// 实体按类型分组（用于「按类型分组」开关）
const graphEntityGroups = computed(() => {
  const groups = new Map<string, typeof graphEntities.value>()
  for (const ent of graphEntities.value) {
    const key = ent.type || '未分类'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(ent)
  }
  // 组内条数多的排前面，便于先看主类
  return [...groups.entries()]
    .map(([type, items]) => ({ type, items }))
    .sort((a, b) => b.items.length - a.items.length)
})

// 关系权重未归一化，按结果集内最大值做相对分档
const graphRelMaxWeight = computed(() => {
  let max = 0
  for (const r of graphRelationships.value) {
    if (r.weight != null && r.weight > max) max = r.weight
  }
  return max
})

const relWeightLevel = (w: number | null): 'high' | 'mid' | 'low' | null => {
  if (w == null) return null
  const max = graphRelMaxWeight.value
  if (max <= 0) return 'mid'
  const ratio = w / max
  if (ratio >= 0.66) return 'high'
  if (ratio >= 0.33) return 'mid'
  return 'low'
}

const relWeightLabel = (w: number | null): string => {
  const lvl = relWeightLevel(w)
  if (lvl === 'high') return '强'
  if (lvl === 'mid') return '中'
  if (lvl === 'low') return '弱'
  return '—'
}

const formatWeight = (w: number | null): string => {
  if (w == null) return ''
  return Number.isInteger(w) ? String(w) : w.toFixed(1)
}

const graphChunks = computed(() =>
  (graphSearchResult.value?.chunks ?? [])
    .map((c) => ({
      content: pick(c, 'content'),
      source: cleanFilePath(pick(c, 'file_path')),
      chunkId: pick(c, 'chunk_id'),
    }))
    .filter((c) => c.content),
)

const graphCitations = computed(() => graphSearchResult.value?.citations ?? [])

const graphResultTabs = computed(() => [
  { key: 'chunks' as const, label: '文档片段', count: graphChunks.value.length },
  { key: 'entities' as const, label: '实体', count: graphEntities.value.length },
  { key: 'relationships' as const, label: '关系', count: graphRelationships.value.length },
  { key: 'citations' as const, label: '引用来源', count: graphCitations.value.length },
  { key: 'context' as const, label: '原始上下文', count: 0 },
])

const graphModeLabelMap: Record<string, string> = {
  mix: 'mix',
  naive: 'naive',
  local: 'local',
  global: 'global',
  hybrid: 'hybrid',
}

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
      chunk_top_k:
        typeof graphSearchChunkTopK.value === 'number' && graphSearchChunkTopK.value > 0
          ? graphSearchChunkTopK.value
          : null,
      include_references: true,
    })
    // 默认展示最有信息量的分页：有片段优先片段，否则退回实体
    graphResultTab.value = graphChunks.value.length
      ? 'chunks'
      : graphEntities.value.length
        ? 'entities'
        : 'context'
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
const documentFileTypeFilter = ref('all')
const documentFileExtOptions = ref<DocumentFileExtOption[]>([])
const documentFileTypeFilterOptions = computed(() => [
  { value: 'all', label: '全部' },
  ...documentFileExtOptions.value.map((opt) => ({
    value: opt.value,
    label: `${opt.label} (${opt.count})`,
  })),
])
const documentStatusFilterOptions = computed(() => {
  const options = [
    { value: 'all', label: '全部' },
    { value: 'uploaded', label: '待解析' },
    { value: 'parsing', label: '解析中' },
    { value: 'chunking', label: '分块中' },
    { value: 'indexing', label: '索引中' },
    { value: 'indexed', label: '已完成' },
  ]
  if (isLightragKb.value) {
    options.push(
      { value: 'graph_indexing', label: '图谱入库中' },
      { value: 'graph_indexed', label: '图谱就绪' },
    )
  }
  options.push({ value: 'failed', label: '失败' })
  if (isLightragKb.value) {
    options.push({ value: 'graph_failed', label: '解析失败' })
  }
  return options
})
const documentSortOptions = [
  { value: 'newest', label: '上传时间：最新优先' },
  { value: 'oldest', label: '上传时间：最早优先' },
  { value: 'name', label: '名称：A-Z' },
] as const
const showDocumentFileTypeFilter = computed(() => documentFileExtOptions.value.length > 0)
const sortOrder = ref<'newest' | 'oldest' | 'name'>('newest')
const documentsTotal = ref(0)
const documentsPage = ref(1)
const documentsPageSize = ref(12)
const processLogSummary = ref<KbProcessLogSummary | null>(null)
const processLogEvents = ref<KbProcessLogEvent[]>([])
const processLogLoading = ref(false)
const processLogPage = ref(1)
const processLogPageSize = ref(20)
const processLogTotal = ref(0)
const processLogKeyword = ref('')
const processLogActionFilter = ref('all')
const expandedProcessLogBatchId = ref<number | null>(null)
const processLogBatchItems = ref<KbProcessLogBatchItem[]>([])
const processLogBatchItemsLoading = ref(false)

const processLogActionOptions = [
  { value: 'all', label: '全部动作' },
  { value: 'upload', label: '上传' },
  { value: 'parse', label: '解析' },
  { value: 'reindex', label: '重建索引' },
  { value: 'delete', label: '删除' },
  { value: 'cancel', label: '取消解析' },
]

const processLogTotalPages = computed(() =>
  Math.max(1, Math.ceil(processLogTotal.value / processLogPageSize.value)),
)
let documentKeywordDebounceTimer: number | null = null
let suppressDocumentFileTypeFilterWatch = false
const selectedDocumentIds = ref<number[]>([])
const batchParsing = ref(false)
const batchStopping = ref(false)
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

function documentForParseLogModal(): KnowledgeDocument | undefined {
  const id = parseLogDocumentId.value
  if (id == null) {
    return undefined
  }
  return documents.value.find((item) => item.id === id)
}

function isParseLogModalDocActive(): boolean {
  const doc = documentForParseLogModal()
  if (!doc) {
    const id = parseLogDocumentId.value
    return id != null && parseTasks.isRunning(id)
  }
  return parseTasks.isRunning(doc.id) || isDocumentProcessingOnServer(doc)
}

const activeParseLogLines = computed(() => {
  const serverLines = parseLogLines.value
  const task = activeParseLogTask.value
  const preferServer = !isParseLogModalDocActive()

  if (preferServer && serverLines.length > 0) {
    return serverLines
  }
  if (task && task.logs.length > 0) {
    if (serverLines.length > task.logs.length) {
      return serverLines
    }
    return task.logs
  }
  return serverLines
})

const activeParseLogPhase = computed(() => {
  const doc = documentForParseLogModal()
  if (doc && !isDocumentProcessingOnServer(doc) && !parseTasks.isRunning(doc.id)) {
    if (parseLogPhase.value === 'success' || parseLogPhase.value === 'error' || parseLogPhase.value === 'cancelled') {
      return parseLogPhase.value
    }
    if (documentIsIndexed(doc)) {
      return 'success'
    }
    if (documentIsParseFailed(doc)) {
      return 'error'
    }
  }

  const task = activeParseLogTask.value
  if (task) {
    if (task.status === 'running') {
      return 'running'
    }
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
const parserSettingsExpanded = ref(false)

function onKbSettingsSaved(updated: KnowledgeBase) {
  knowledgeBase.value = updated
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

watch(
  activeTab,
  (tab) => {
    setFillPage(tab === 'documents' || tab === 'graph')
  },
  { immediate: true },
)

onUnmounted(() => {
  clearPageContext()
  if (toastClearTimer != null) {
    window.clearTimeout(toastClearTimer)
  }
  if (documentKeywordDebounceTimer != null) {
    window.clearTimeout(documentKeywordDebounceTimer)
  }
  stopDocumentNameColResize()
  stopParseLogPoll()
  for (const documentId of [...documentStatusPollTimers.keys()]) {
    stopDocumentStatusPoll(documentId)
  }
})

const showUploadModal = ref(false)
const uploadFiles = ref<File[]>([])
const uploadError = ref('')
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadCompletedCount = ref(0)
const uploadCurrentFileName = ref('')
const isDragOver = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const folderInputRef = ref<HTMLInputElement | null>(null)

const UPLOAD_ACCEPT_EXT = new Set(['.txt', '.md', '.pdf', '.doc', '.docx', '.csv', '.xls', '.xlsx', '.xlsm'])

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
  () =>
    documentKeyword.value.trim() !== '' ||
    documentStatusFilter.value !== 'all' ||
    documentFileTypeFilter.value !== 'all',
)

const documentsListIsFreshEmpty = computed(
  () => !documentsLoading.value && documents.value.length === 0 && !documentListFilterActive.value,
)

const documentListEmptyTitle = computed(() =>
  documentListFilterActive.value ? '没有匹配的文档' : '还没有文档',
)

const documentListEmptyDescription = computed(() => {
  if (documentListFilterActive.value) {
    return '请调整搜索关键词或筛选条件。'
  }
  if (isLightragKb.value) {
    return '支持 PDF、Word（doc/docx）、Excel 等格式。点击右上角「新增文件」上传，再执行「开始解析」完成分块与图谱入库。'
  }
  return '支持 PDF、Word（doc/docx）、Excel 等格式。点击右上角「新增文件」上传，再执行「开始解析」完成分块与向量索引。'
})

function clearDocumentListFilters() {
  documentKeyword.value = ''
  documentStatusFilter.value = 'all'
  documentFileTypeFilter.value = 'all'
}

function syncDocumentFileExtOptions(options: DocumentFileExtOption[] | undefined): boolean {
  documentFileExtOptions.value = options ?? []
  if (
    documentFileTypeFilter.value !== 'all' &&
    !documentFileExtOptions.value.some((opt) => opt.value === documentFileTypeFilter.value)
  ) {
    suppressDocumentFileTypeFilterWatch = true
    documentFileTypeFilter.value = 'all'
    suppressDocumentFileTypeFilterWatch = false
    return true
  }
  return false
}


function processLogStatusLabel(status: string) {
  const map: Record<string, string> = {
    running: '进行中',
    success: '成功',
    partial_failed: '部分失败',
    failed: '失败',
  }
  return map[status] || status
}

function processLogStatusTone(status: string) {
  if (status === 'success') return 'success'
  if (status === 'running') return 'info'
  if (status === 'partial_failed') return 'warning'
  if (status === 'failed') return 'error'
  return 'info'
}

function processLogItemStatusLabel(status: string) {
  const map: Record<string, string> = {
    running: '进行中',
    success: '成功',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || status
}

function processLogItemStatusTone(status: string) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'cancelled') return 'warning'
  return 'info'
}

async function fetchProcessLogSummary() {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    processLogSummary.value = null
    return
  }
  try {
    processLogSummary.value = await knowledgeBaseApi.getProcessLogSummary(kbId.value)
  } catch {
    processLogSummary.value = null
  }
}

async function fetchProcessLogEvents() {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    processLogEvents.value = []
    processLogTotal.value = 0
    return
  }
  processLogLoading.value = true
  try {
    const data = await knowledgeBaseApi.listProcessLogEvents(kbId.value, {
      page: processLogPage.value,
      page_size: processLogPageSize.value,
      keyword: processLogKeyword.value || undefined,
      action: processLogActionFilter.value === 'all' ? undefined : processLogActionFilter.value,
    })
    processLogEvents.value = data.items
    processLogTotal.value = data.total
  } catch {
    processLogEvents.value = []
    processLogTotal.value = 0
  } finally {
    processLogLoading.value = false
  }
}

async function fetchProcessLogData() {
  await Promise.all([fetchProcessLogSummary(), fetchProcessLogEvents()])
}

function goProcessLogPage(page: number) {
  processLogPage.value = Math.min(Math.max(1, page), processLogTotalPages.value)
  void fetchProcessLogEvents()
}

async function toggleProcessLogBatchExpand(batchId: number) {
  if (expandedProcessLogBatchId.value === batchId) {
    expandedProcessLogBatchId.value = null
    processLogBatchItems.value = []
    return
  }
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  expandedProcessLogBatchId.value = batchId
  processLogBatchItemsLoading.value = true
  try {
    const data = await knowledgeBaseApi.listProcessLogBatchItems(kbId.value, batchId)
    processLogBatchItems.value = data.items
  } catch {
    processLogBatchItems.value = []
  } finally {
    processLogBatchItemsLoading.value = false
  }
}

async function openParseLogFromBatchItem(item: KbProcessLogBatchItem) {
  if (!item.document_id) {
    return
  }
  parseLogDocumentId.value = item.document_id
  parseLogKind.value = 'parse'
  parseLogTitle.value = item.file_name
  parseLogLines.value = []
  parseLogPhase.value = item.status === 'failed' ? 'error' : 'cancelled'
  try {
    const data = await knowledgeBaseApi.getDocumentParseLog(kbId.value, item.document_id)
    parseLogKind.value = (data.kind as 'parse' | 'reindex') || 'parse'
    parseLogPhase.value = (data.phase as typeof parseLogPhase.value) || parseLogPhase.value
    parseLogLines.value = data.lines || []
  } catch {
    parseLogLines.value = item.error_message ? [{ t: '', text: item.error_message }] : []
  }
  showParseLogModal.value = true
}

function documentIsParseFailed(document: KnowledgeDocument) {
  return document.status === 'failed' || document.status === 'graph_failed'
}

function documentIsIndexed(document: KnowledgeDocument) {
  return document.status === 'indexed' || document.status === 'graph_indexed'
}

function documentIsStuckProcessing(document: KnowledgeDocument) {
  return isDocumentProcessingOnServer(document) && !parseTasks.isRunning(document.id)
}

function documentProcessingPercent(document: KnowledgeDocument): number {
  const task = parseTasks.getTask(document.id)
  if (task && task.status === 'running') {
    return task.percent
  }
  const status = document.status
  if (status === 'graph_indexing') return 55
  if (status === 'indexing') return 78
  if (status === 'chunking') return 20
  if (status === 'parsing') return 8
  return 0
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

const TERMINAL_DOCUMENT_STATUSES = new Set([
  'indexed',
  'graph_indexed',
  'failed',
  'graph_failed',
  'deleted',
])

function isTerminalDocumentStatus(status: string) {
  return TERMINAL_DOCUMENT_STATUSES.has(status)
}

function mergeDocumentFromListApi(
  fresh: KnowledgeDocument,
  existing?: KnowledgeDocument,
): KnowledgeDocument {
  if (!existing) {
    return applyLocalProcessingOverlay(fresh)
  }
  const freshProcessing = isDocumentProcessingOnServer(fresh)
  const existingTerminal = isTerminalDocumentStatus(existing.status)
  if (existingTerminal && freshProcessing) {
    return applyLocalProcessingOverlay({
      ...fresh,
      status: existing.status,
      chunk_count: Math.max(existing.chunk_count ?? 0, fresh.chunk_count ?? 0),
      error_message: existing.error_message ?? fresh.error_message,
    })
  }
  return applyLocalProcessingOverlay(fresh)
}

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
  const task = parseTasks.getTask(document.id)
  if (task?.mode === 'reindex') {
    return {
      ...document,
      status: isLightragKb.value ? 'graph_indexing' : 'indexing',
    }
  }
  if (document.status === 'graph_indexed' || document.status === 'indexed') {
    return document
  }
  if (document.status === 'graph_indexing' || document.status === 'parsing' || document.status === 'indexing') {
    return document
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
  if (documentIsStuckProcessing(document)) {
    return document.status
  }
  return applyLocalProcessingOverlay(document).status
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
  const id = kbId.value
  if (!id || Number.isNaN(id)) {
    return
  }
  for (const [key, task] of parseTasks.tasks.entries()) {
    if (task.kbId !== id) {
      continue
    }
    if (!documents.value.some((d) => d.id === task.documentId) && task.status !== 'running') {
      parseTasks.tasks.delete(key)
    }
  }
}

async function reconcileProcessingTasks() {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  for (const documentId of parseTasks.runningDocumentIds()) {
    startDocumentStatusPoll(documentId)
  }
  for (const doc of documents.value) {
    if (parseTasks.isRunning(doc.id)) {
      parseTasks.reconcileTaskTerminalState(doc.id, doc.status)
    }
    if (parseTasks.isRunning(doc.id)) {
      continue
    }
    if (kbId.value != null && wasUserCancelledParseTask(kbId.value, doc.id)) {
      continue
    }
    if (!isDocumentProcessingOnServer(doc)) {
      continue
    }
    const mode: 'parse' | 'reindex' =
      doc.status === 'graph_indexing' ||
      doc.status === 'graph_failed' ||
      (doc.status === 'indexing' && (doc.chunk_count ?? 0) > 0)
        ? 'reindex'
        : 'parse'
    void parseTasks.resumeWatch(doc.id, {
      status: doc.status,
      mode,
      onTerminal: (snapshot) => {
        endDocumentStreamProcessing(doc.id, snapshot)
        persistParseLogSnapshot(doc.id)
        void refreshDocuments()
      },
    })
    startDocumentStatusPoll(doc.id)
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

function documentCanStopProcessing(document: KnowledgeDocument) {
  if (documentIsStuckProcessing(document)) {
    return true
  }
  if (isDocumentProcessingOnServer(document)) {
    return true
  }
  if (parseTasks.isRunning(document.id)) {
    return true
  }
  if (isDocumentProcessingLocally(document)) {
    return true
  }
  const displayStatus = getDocumentDisplayStatus(document)
  return DOCUMENT_PROCESSING_STATUSES.includes(
    displayStatus as (typeof DOCUMENT_PROCESSING_STATUSES)[number],
  )
}

const canBatchStopSelection = computed(() => {
  const sel = new Set(selectedDocumentIds.value)
  if (sel.size === 0) {
    return false
  }
  const onPage = documents.value.filter((d) => sel.has(d.id))
  if (onPage.some(documentCanStopProcessing)) {
    return true
  }
  return [...sel].some((id) => parseTasks.isRunning(id))
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

const DOC_NAME_COL_WIDTH_KEY = 'kb-document-name-col-width'
const DOC_NAME_COL_MIN = 140
const DOC_NAME_COL_MAX = 960

function readStoredDocumentNameColWidth(): number | null {
  try {
    const raw = localStorage.getItem(DOC_NAME_COL_WIDTH_KEY)
    if (!raw) {
      return null
    }
    const width = Number(raw)
    if (!Number.isFinite(width)) {
      return null
    }
    return Math.min(DOC_NAME_COL_MAX, Math.max(DOC_NAME_COL_MIN, width))
  } catch {
    return null
  }
}

const documentNameColWidth = ref<number | null>(readStoredDocumentNameColWidth())
const documentTableStyle = computed(() => {
  if (documentNameColWidth.value == null) {
    return undefined
  }
  return { '--doc-name-col-width': `${documentNameColWidth.value}px` }
})

let documentNameColResizeStartX = 0
let documentNameColResizeStartWidth = 0
let documentNameColResizeCleanup: (() => void) | null = null

function resetDocumentNameColWidth() {
  documentNameColWidth.value = null
  try {
    localStorage.removeItem(DOC_NAME_COL_WIDTH_KEY)
  } catch {
    /* ignore */
  }
}

function stopDocumentNameColResize() {
  documentNameColResizeCleanup?.()
  documentNameColResizeCleanup = null
}

function startDocumentNameColResize(event: MouseEvent) {
  stopDocumentNameColResize()

  const header = (event.currentTarget as HTMLElement).closest('.document-col-name')
  const measuredWidth = header?.getBoundingClientRect().width ?? DOC_NAME_COL_MIN
  documentNameColResizeStartX = event.clientX
  documentNameColResizeStartWidth = documentNameColWidth.value ?? measuredWidth

  const onMove = (moveEvent: MouseEvent) => {
    const delta = moveEvent.clientX - documentNameColResizeStartX
    const next = Math.min(
      DOC_NAME_COL_MAX,
      Math.max(DOC_NAME_COL_MIN, documentNameColResizeStartWidth + delta),
    )
    documentNameColWidth.value = next
  }

  const onUp = () => {
    document.body.classList.remove('col-resize-active')
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
    documentNameColResizeCleanup = null
    if (documentNameColWidth.value != null) {
      try {
        localStorage.setItem(DOC_NAME_COL_WIDTH_KEY, String(documentNameColWidth.value))
      } catch {
        /* ignore */
      }
    }
  }

  document.body.classList.add('col-resize-active')
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
  documentNameColResizeCleanup = () => {
    document.body.classList.remove('col-resize-active')
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
}

/** 列表主标题：优先展示带扩展名的文件名，更易辨认类型。 */
function documentDisplayName(document: KnowledgeDocument) {
  const fn = document.file_name?.trim() ?? ''
  if (fn) {
    const normalized = fn.replace(/\\/g, '/')
    return normalized.split('/').pop() ?? fn
  }
  return document.document_name?.trim() || '未命名文档'
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
      file_ext: documentFileTypeFilter.value === 'all' ? undefined : documentFileTypeFilter.value,
      sort: documentListSort.value,
    }
    let data = await knowledgeBaseApi.listDocuments(kbId.value, params)
    const lastPage = Math.max(1, Math.ceil(data.total / documentsPageSize.value) || 1)
    if (data.total > 0 && documentsPage.value > lastPage) {
      documentsPage.value = lastPage
      data = await knowledgeBaseApi.listDocuments(kbId.value, { ...params, page: lastPage })
    }
    documentsTotal.value = data.total
    const previous = new Map(documents.value.map((item) => [item.id, item]))
    documents.value = data.items.map((item) => mergeDocumentFromListApi(item, previous.get(item.id)))
    const filterReset = syncDocumentFileExtOptions(data.file_ext_options)
    pruneProcessingDocumentIds()
    await reconcileProcessingTasks()
    if (filterReset) {
      return fetchDocumentPage({ withLoading: false })
    }
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

async function refreshDocuments() {
  await fetchDocumentPage()
  if (activeTab.value === 'logs') {
    await fetchProcessLogData()
  }
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
  clearPageContext()
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
  uploadCompletedCount.value = 0
  uploadCurrentFileName.value = ''
  const okNames: string[] = []
  const skippedNames: string[] = []
  const failures: string[] = []
  const queue = [...uploadFiles.value]
  const total = queue.length
  try {
    const batchId = createBatchId()
    const batchAuditItems: Array<{ document_id: number; file_name: string }> = []
    for (let index = 0; index < total; index += 1) {
      const file = queue[index]
      uploadProgress.value = index + 1
      uploadCurrentFileName.value = file.name
      await nextTick()
      try {
        const res = await knowledgeBaseApi.uploadDocument(kbId.value, {
          file,
          skip_if_duplicate: true,
        })
        batchAuditItems.push({ document_id: res.id, file_name: res.file_name || file.name })
        if (res.upload_skipped) {
          skippedNames.push(file.name)
        } else {
          okNames.push(file.name)
        }
        uploadCompletedCount.value = index + 1
      } catch (value) {
        failures.push(`${file.name}：${getKnowledgeBaseErrorMessage(value, '上传失败')}`)
        uploadCompletedCount.value = index + 1
      }
    }
    if (batchAuditItems.length > 0) {
      try {
        await knowledgeBaseApi.recordUploadBatch(kbId.value, {
          batch_uid: batchId,
          items: batchAuditItems,
        })
      } catch (value) {
        /* 上传已成功，审计批次失败不阻断 */
        console.warn('recordUploadBatch failed', value)
      }
    }
    await refreshDocuments()
    if (failures.length === 0) {
      closeUploadModal()
      if (okNames.length === 0 && skippedNames.length > 0) {
        showToast(
          skippedNames.length === 1
            ? `「${skippedNames[0]}」内容未变化，已跳过上传。`
            : `${skippedNames.length} 个文件内容未变化，已跳过上传。`,
          5000,
        )
      } else if (skippedNames.length === 0) {
        showToast(
          okNames.length === 1
            ? `「${okNames[0]}」上传成功，已加入列表。请点击「开始解析」完成分块与索引。`
            : `已成功上传 ${okNames.length} 个文件，已加入列表。请点击「开始解析」完成分块与索引。`,
          okNames.length === 1 ? 4000 : 5000,
        )
      } else {
        showToast(
          `新上传 ${okNames.length} 个，跳过重复 ${skippedNames.length} 个。请点击「开始解析」处理新文件。`,
          5000,
        )
      }
    } else {
      uploadError.value =
        failures.length === total
          ? `全部上传失败：${failures.join('；')}`
          : `部分失败（${failures.length}/${total}）：${failures.join('；')}`
      if (okNames.length > 0 || skippedNames.length > 0) {
        const parts: string[] = []
        if (okNames.length > 0) {
          parts.push(`已上传 ${okNames.length} 个`)
        }
        if (skippedNames.length > 0) {
          parts.push(`跳过重复 ${skippedNames.length} 个`)
        }
        showToast(`${parts.join('，')}，另有 ${failures.length} 个失败，请查看下方错误信息。`, 5000)
      }
    }
  } catch (value) {
    uploadError.value = getKnowledgeBaseErrorMessage(value, '上传失败')
  } finally {
    uploading.value = false
    uploadProgress.value = 0
    uploadCompletedCount.value = 0
    uploadCurrentFileName.value = ''
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
  stopParseLogPoll()
  showParseLogModal.value = false
}

const parseLogPollTimer = ref<number | null>(null)

function stopParseLogPoll() {
  if (parseLogPollTimer.value != null) {
    window.clearInterval(parseLogPollTimer.value)
    parseLogPollTimer.value = null
  }
}

function formatParseLogTimeDisplay(t: string): string {
  if (!t) {
    return ''
  }
  const d = new Date(t)
  if (!Number.isNaN(d.getTime())) {
    return d.toLocaleTimeString('zh-CN', { hour12: false })
  }
  return t
}

function applyRemoteParseLog(remote: Awaited<ReturnType<typeof knowledgeBaseApi.getDocumentParseLog>>) {
  if (remote.kind === 'reindex' || remote.kind === 'parse') {
    parseLogKind.value = remote.kind
  }
  if (remote.phase === 'error') {
    parseLogPhase.value = 'error'
  } else if (remote.phase === 'success') {
    parseLogPhase.value = 'success'
  } else if (remote.phase === 'running') {
    parseLogPhase.value = 'running'
  }
  if (remote.lines?.length) {
    parseLogLines.value = remote.lines.map((line) => ({
      t: formatParseLogTimeDisplay(line.t),
      text: line.text,
    }))
  }
}

async function refreshParseLogFromServer(documentId: number) {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return
  }
  try {
    const remote = await knowledgeBaseApi.getDocumentParseLog(kbId.value, documentId)
    applyRemoteParseLog(remote)
    await parseTasks.syncLogsFromServer(documentId)
  } catch {
    /* 轮询时忽略瞬时失败 */
  }
}

function startParseLogPoll(documentId: number) {
  stopParseLogPoll()
  parseLogPollTimer.value = window.setInterval(() => {
    void refreshParseLogFromServer(documentId)
  }, 3000)
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
  if (isDocumentProcessingOnServer(document)) {
    return true
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
  parseLogDocumentId.value = targetId

  const isActive = parseTasks.isRunning(document.id) || isDocumentProcessingOnServer(document)
  if (!isActive) {
    parseTasks.reconcileTaskTerminalState(document.id, document.status)
  }

  if (isActive) {
    const task = parseTasks.getTask(document.id)
    if (task && task.logs.length > 0) {
      parseLogKind.value = task.mode
      parseLogPhase.value = 'running'
      parseLogLines.value = [...task.logs]
    } else {
      const stored = loadParseLogSnapshot(document.id)
      if (stored) {
        parseLogKind.value = stored.kind
        parseLogPhase.value = stored.phase
        parseLogLines.value = [...stored.lines]
      } else {
        parseLogLines.value = []
        parseLogKind.value = 'parse'
        parseLogPhase.value = 'running'
      }
    }
  } else {
    const stored = loadParseLogSnapshot(document.id)
    if (stored && stored.lines.length > 0) {
      parseLogKind.value = stored.kind
      parseLogPhase.value = stored.phase
      parseLogLines.value = [...stored.lines]
    } else {
      parseLogLines.value = []
      parseLogKind.value = 'parse'
      if (documentIsIndexed(document)) {
        parseLogPhase.value = 'success'
      } else if (documentIsParseFailed(document)) {
        parseLogPhase.value = 'error'
      } else {
        parseLogPhase.value = 'running'
      }
    }
  }

  showParseLogModal.value = true

  parseLogLoading.value = true
  try {
    await refreshParseLogFromServer(document.id)
    if (parseLogModalOpenedFor.value !== targetId) {
      return
    }
  } catch (value) {
    showNotice(getKnowledgeBaseErrorMessage(value, '加载解析日志失败'), 'error')
  } finally {
    parseLogLoading.value = false
  }

  if (parseTasks.isRunning(document.id) || isDocumentProcessingOnServer(document)) {
    startParseLogPoll(document.id)
  } else {
    stopParseLogPoll()
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

async function runDocumentParseSilent(documentId: number, batchId?: string): Promise<{ ok: boolean; message?: string }> {
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
    const result = await parseTasks.startTask(documentId, mode, {
      force: needsForce,
      graphKb: isLightragKb.value && mode === 'reindex',
      batchId,
    })
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

async function waitForBatchDocumentsCompletion(documentIds: number[]) {
  if (!kbId.value || Number.isNaN(kbId.value) || documentIds.length === 0) {
    return
  }
  const pending = new Set(documentIds)
  while (pending.size > 0) {
    await new Promise((resolve) => window.setTimeout(resolve, 3000))
    for (const documentId of [...pending]) {
      try {
        const doc = await knowledgeBaseApi.getDocument(kbId.value, documentId)
        patchDocumentInList(documentId, doc)
        parseTasks.reconcileTaskTerminalState(documentId, doc.status)
        if (!isDocumentProcessingOnServer(doc)) {
          pending.delete(documentId)
          parseTasks.finishTask(documentId)
        }
      } catch {
        /* 网络抖动时继续轮询 */
      }
    }
  }
}

async function batchParseSelectedDocuments() {
  const ids = [...new Set(selectedDocumentIds.value)]
  if (!kbId.value || Number.isNaN(kbId.value) || ids.length === 0) {
    return
  }
  batchParsing.value = true
  let ok = 0
  let fail = 0
  let skipped = 0
  const batchId = createBatchId()
  const queuedIds: number[] = []
  try {
    await knowledgeBaseApi.startProcessBatch(kbId.value, { batch_uid: batchId, action: 'parse' })
    const batchResult = await knowledgeBaseApi.batchEnqueueProcess(kbId.value, {
      document_ids: ids,
      batch_uid: batchId,
    })
    for (const item of batchResult.items) {
      if (item.queued) {
        ok += 1
        queuedIds.push(item.document_id)
        const mode = item.mode ?? 'parse'
        const optimisticStatus =
          mode === 'reindex' ? (isLightragKb.value ? 'graph_indexing' : 'indexing') : 'parsing'
        patchDocumentInList(item.document_id, { status: optimisticStatus })
        startDocumentStatusPoll(item.document_id)
        void parseTasks.resumeWatch(item.document_id, {
          status: optimisticStatus,
          mode,
          onTerminal: (doc) => {
            patchDocumentInList(item.document_id, doc)
            stopDocumentStatusPoll(item.document_id)
            persistParseLogSnapshot(item.document_id)
          },
        })
      } else if (item.skipped) {
        skipped += 1
      } else {
        fail += 1
      }
    }
    void fetchDocumentPage({ withLoading: false })
    if (queuedIds.length > 0) {
      await waitForBatchDocumentsCompletion(queuedIds)
    }
    for (const documentId of queuedIds) {
      stopDocumentStatusPoll(documentId)
      parseTasks.finishTask(documentId)
      persistParseLogSnapshot(documentId)
    }
    await fetchDocumentPage({ withLoading: false })
    try {
      await knowledgeBaseApi.reconcileProcessBatch(kbId.value, { batch_uid: batchId })
    } catch {
      /* 对账失败不阻断批量解析结果提示 */
    }
    if (activeTab.value === 'logs') {
      await fetchProcessLogData()
    }
    clearDocumentSelection()
    const parts: string[] = []
    if (ok > 0) {
      parts.push(`成功 ${ok} 个`)
    }
    if (skipped > 0) {
      parts.push(`跳过 ${skipped} 个`)
    }
    if (fail > 0) {
      parts.push(`失败 ${fail} 个`)
    }
    if (fail === 0 && skipped === 0) {
      showNotice(`已批量解析完成，共 ${ok} 个文件。`, 'success', 4000)
    } else {
      showNotice(
        `批量解析结束：${parts.join('，')}。`,
        fail === ids.length ? 'error' : 'info',
        6000,
      )
    }
  } finally {
    batchParsing.value = false
  }
}

function onDocumentRowCheckboxChange(document: KnowledgeDocument, event: Event) {
  if (documentsLoading.value || batchParsing.value || batchStopping.value || batchDeleting.value) {
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

async function stopDocumentProcessingSafely(documentId: number): Promise<boolean> {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return false
  }
  stopDocumentStatusPoll(documentId)
  const wasRunningLocally = parseTasks.isRunning(documentId)
  try {
    const snapshot = await parseTasks.cancelTask(documentId)
    if (snapshot) {
      patchDocumentInList(documentId, snapshot)
    } else {
      patchDocumentInList(documentId, {
        status: 'uploaded',
        error_message: null,
        chunk_count: 0,
      })
    }
    return true
  } catch {
    if (wasRunningLocally && !parseTasks.isRunning(documentId)) {
      await refreshDocuments()
      return true
    }
    try {
      const snapshot = await cancelDocumentProcess(kbId.value, documentId)
      patchDocumentInList(documentId, snapshot)
      return true
    } catch {
      return false
    }
  }
}

async function resolveStoppableDocumentIds(ids: number[]): Promise<number[]> {
  if (!kbId.value || Number.isNaN(kbId.value)) {
    return []
  }
  const stoppable: number[] = []
  for (const documentId of ids) {
    if (parseTasks.isRunning(documentId)) {
      stoppable.push(documentId)
      continue
    }
    const onPage = documents.value.find((d) => d.id === documentId)
    if (onPage) {
      if (documentCanStopProcessing(onPage)) {
        stoppable.push(documentId)
      }
      continue
    }
    try {
      const doc = await knowledgeBaseApi.getDocument(kbId.value, documentId)
      if (documentCanStopProcessing(doc)) {
        stoppable.push(documentId)
      }
    } catch {
      /* 跳过无法读取的文档 */
    }
  }
  return stoppable
}

async function batchStopSelectedDocuments() {
  const ids = [...new Set(selectedDocumentIds.value)]
  if (!kbId.value || Number.isNaN(kbId.value) || ids.length === 0) {
    return
  }
  const stoppable = await resolveStoppableDocumentIds(ids)
  if (stoppable.length === 0) {
    showNotice('所选文档中没有进行中的解析任务。', 'info', 4000)
    return
  }
  if (
    !window.confirm(
      `确定停止已选的 ${stoppable.length} 个进行中的解析任务吗？已写入的部分将被清理。`,
    )
  ) {
    return
  }
  batchStopping.value = true
  let ok = 0
  let fail = 0
  try {
    for (const documentId of stoppable) {
      const stopped = await stopDocumentProcessingSafely(documentId)
      if (stopped) {
        ok += 1
      } else {
        fail += 1
      }
    }
    await refreshDocuments()
    if (fail === 0) {
      showNotice(`已停止 ${ok} 个解析任务。`, 'success', 4000)
    } else {
      showNotice(
        `批量停止结束：成功 ${ok} 个，失败 ${fail} 个。`,
        fail === stoppable.length ? 'error' : 'info',
        6000,
      )
    }
  } finally {
    batchStopping.value = false
  }
}

async function cancelDocumentParseAction(documentId: number) {
  if (!window.confirm('确定停止该文档的解析吗？已写入的部分将被清理。')) {
    return
  }
  try {
    const snapshot = await parseTasks.cancelTask(documentId)
    stopDocumentStatusPoll(documentId)
    parseLogDocumentId.value = documentId
    parseLogPhase.value = 'cancelled'
    if (snapshot) {
      patchDocumentInList(documentId, snapshot)
    } else {
      patchDocumentInList(documentId, {
        status: 'uploaded',
        error_message: null,
        chunk_count: 0,
      })
    }
    await refreshDocuments()
    showNotice('已停止解析', 'info', 3000)
  } catch (value) {
    showNotice(getKnowledgeBaseErrorMessage(value, '停止解析失败'), 'error')
    await refreshDocuments()
  }
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
    const result = await parseTasks.startTask(documentId, 'reindex', {
      force: options?.force,
      graphKb: isLightragKb.value,
    })
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
  const batchId = createBatchId()
  try {
    await knowledgeBaseApi.startProcessBatch(kbId.value, { batch_uid: batchId, action: 'delete' })
    for (const documentId of ids) {
      deletingDocumentIds.value = [...deletingDocumentIds.value, documentId]
      try {
        await knowledgeBaseApi.deleteDocument(kbId.value, documentId, batchId)
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
      include_image_ocr: f.include_image_ocr,
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
  processLogActionFilter,
  () => {
    processLogPage.value = 1
    if (activeTab.value === 'logs') {
      void fetchProcessLogEvents()
    }
  },
)

watch(
  activeTab,
  (tab) => {
    if (tab === 'logs') {
      void fetchProcessLogData()
    }
  },
)

watch(
  () => knowledgeBase.value?.name,
  (name) => {
    if (!name?.trim()) {
      return
    }
    setPageContext({ title: name, breadcrumbTail: name })
  },
  { immediate: true },
)

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
  tabs,
  (items) => {
    if (!items.some((tab) => tab.key === activeTab.value)) {
      activeTab.value = 'documents'
    }
  },
  { immediate: true },
)

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

watch(documentFileTypeFilter, () => {
  if (suppressDocumentFileTypeFilterWatch) {
    return
  }
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

.kb-settings-card--panel-open {
  overflow: visible;
  position: relative;
  z-index: 4;
}

/* 配置页多个可折叠面板展开时，避免被父级裁剪或下层块遮挡 */
.knowledge-detail-layout--settings .detail-main {
  overflow: visible;
}

.knowledge-detail-layout--settings .content-card {
  overflow: visible;
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

.activity-card strong,
.search-result-card strong,
.error-panel h3 {
  color: var(--text-primary);
}

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

.document-table-wrap {
  min-width: 0;
}

.document-table-head,
.document-row {
  display: grid;
  grid-template-columns:
    36px var(--doc-name-col-width, minmax(140px, 1.6fr)) minmax(108px, 0.9fr) minmax(42px, 0.3fr)
    minmax(68px, 0.48fr) minmax(36px, 0.24fr) minmax(88px, 0.66fr) minmax(300px, 1.75fr);
  gap: 8px 8px;
  align-items: center;
}

.document-col-name {
  position: relative;
  min-width: 0;
  padding-right: 6px;
}

.col-resize-handle {
  position: absolute;
  top: -6px;
  right: -8px;
  bottom: -6px;
  width: 12px;
  cursor: col-resize;
  touch-action: none;
  z-index: 2;
}

.col-resize-handle::after {
  content: '';
  position: absolute;
  top: 2px;
  right: 5px;
  bottom: 2px;
  width: 2px;
  border-radius: 1px;
  background: transparent;
  transition: background 0.15s ease;
}

.document-col-name:hover .col-resize-handle::after,
.col-resize-handle:hover::after {
  background: color-mix(in srgb, var(--brand-primary) 42%, var(--border-color));
}

:global(body.col-resize-active),
:global(body.col-resize-active *) {
  cursor: col-resize !important;
  user-select: none;
}

.document-table-head {
  padding: 0 14px 10px;
  font-weight: 500;
  font-size: 0.8125rem;
  color: var(--text-tertiary);
  letter-spacing: 0.02em;
  border-bottom: 1px solid var(--border-color);
}

.table-actions-head {
  text-align: center;
  justify-self: center;
}

.document-col-compact {
  min-width: 0;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.document-col-status {
  display: flex;
  justify-content: center;
  align-items: center;
  min-width: 0;
}

.document-table-body {
  display: grid;
  gap: 0;
  border: 1px solid color-mix(in srgb, var(--border-color) 88%, transparent);
  border-radius: 10px;
  overflow: hidden;
  background: var(--bg-primary);
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
  padding: 13px 14px;
  border: none;
  border-radius: 0;
  border-bottom: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
  background: transparent;
  box-shadow: none;
  transition: background 0.15s ease;
}

.document-row:last-child {
  border-bottom: none;
}

.document-row:hover {
  background: color-mix(in srgb, var(--bg-secondary) 65%, var(--bg-primary));
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
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.document-name-wrap {
  min-width: 0;
  flex: 1;
}

.document-name {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.875rem;
  font-weight: 400;
  line-height: 1.5;
  letter-spacing: 0.01em;
  color: color-mix(in srgb, var(--text-primary) 88%, var(--text-secondary));
}

.doc-preview-trigger {
  cursor: pointer;
  border-radius: 6px;
  padding: 2px 4px;
  margin: -2px -4px;
  outline: none;
  transition: opacity 0.15s ease;
}

.doc-preview-trigger:hover {
  background: transparent;
}

.doc-preview-trigger:hover .document-name {
  color: var(--text-primary);
}

.doc-preview-trigger:focus-visible {
  box-shadow: 0 0 0 2px var(--brand-primary-light);
}

.doc-preview-loading {
  pointer-events: none;
  opacity: 0.65;
}

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
  display: flex;
  justify-content: center;
  flex-wrap: nowrap;
  gap: 6px;
  align-items: center;
  width: 100%;
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
  flex: 0 0 auto;
  min-width: 176px;
}

.document-row .row-actions.document-row-actions .parse-log-dot-btn {
  flex-shrink: 0;
}

.document-row .row-actions.document-row-actions .kebab-menu {
  flex-shrink: 0;
}

.document-row .document-name {
  font-size: 0.875rem;
  font-weight: 400;
}

.document-row .document-meta-cell {
  font-size: 0.8125rem;
  font-weight: 400;
  line-height: 1.45;
  color: var(--text-secondary);
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

.graph-search-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

@media (max-width: 720px) {
  .graph-search-grid {
    grid-template-columns: 1fr;
  }
}

/* ===== 图检索结果 ===== */
.graph-search-results {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 16px;
}

.graph-search-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.graph-result-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  border-bottom: 1px solid var(--border-subtle, var(--border-color, #e5e7eb));
  padding-bottom: 0;
}

.graph-result-tab {
  appearance: none;
  border: none;
  background: transparent;
  padding: 8px 12px;
  font-size: 0.85rem;
  color: var(--text-tertiary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: color 0.15s ease, border-color 0.15s ease;
}

.graph-result-tab:hover {
  color: var(--text-primary);
}

.graph-result-tab--active {
  color: var(--brand-primary);
  border-bottom-color: var(--brand-primary);
  font-weight: 600;
}

.graph-result-tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  font-size: 0.7rem;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

.graph-result-tab--active .graph-result-tab-count {
  background: var(--brand-primary-light);
  color: var(--brand-primary);
}

.graph-result-body {
  min-height: 80px;
}

.chip-soft {
  background: var(--brand-primary-light);
  color: var(--brand-primary);
}

/* 文档片段卡片 */
.graph-chunk-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
}

.graph-chunk-card {
  border: 1px solid var(--border-subtle, var(--border-color, #e5e7eb));
  border-radius: 10px;
  padding: 12px 14px;
  background: var(--bg-secondary, #fff);
}

.graph-chunk-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.graph-chunk-index {
  font-weight: 600;
  color: var(--brand-primary);
  font-size: 0.85rem;
}

.graph-chunk-source {
  font-size: 0.78rem;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.graph-chunk-content {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.65;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

/* 实体 / 关系表格 */
.graph-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border-subtle, var(--border-color, #e5e7eb));
  border-radius: 10px;
}

.graph-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.graph-table th,
.graph-table td {
  text-align: left;
  padding: 9px 12px;
  border-bottom: 1px solid var(--border-subtle, var(--border-color, #eef0f3));
  vertical-align: top;
}

.graph-table thead th {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-weight: 600;
  white-space: nowrap;
}

.graph-table tbody tr:last-child td {
  border-bottom: none;
}

.graph-cell-name {
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.graph-cell-desc {
  color: var(--text-secondary);
  line-height: 1.55;
  max-width: 460px;
}

.graph-cell-rel {
  white-space: nowrap;
}

.graph-rel-node {
  font-weight: 600;
  color: var(--text-primary);
}

.graph-rel-arrow {
  margin: 0 6px;
  color: var(--brand-primary);
}

.graph-table-action {
  white-space: nowrap;
  width: 1%;
}

/* 引用来源 */
.graph-citation-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.graph-citation-item {
  display: flex;
  gap: 8px;
  align-items: baseline;
  font-size: 0.88rem;
  color: var(--text-primary);
}

.graph-citation-ref {
  color: var(--brand-primary);
  font-weight: 600;
  flex-shrink: 0;
}

/* 原始上下文 */
.graph-context-hint {
  margin: 0 0 8px;
  font-size: 0.8rem;
  color: var(--text-tertiary);
}

.graph-context-raw {
  margin: 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-subtle, var(--border-color, #e5e7eb));
  font-size: 0.8rem;
  line-height: 1.6;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 460px;
  overflow: auto;
}

/* 实体类型着色 chip */
.graph-type-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 9px 2px 7px;
  border-radius: 999px;
  font-size: 0.78rem;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--type-color) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--type-color) 32%, transparent);
  white-space: nowrap;
}

.graph-type-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--type-color, #94a3b8);
  flex-shrink: 0;
}

/* 实体分组 */
.graph-entity-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
  margin-bottom: 10px;
}

.graph-entity-stats {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.graph-entity-stats strong {
  color: var(--brand-primary);
  font-weight: 700;
}

.graph-entity-name-trigger {
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 1px dashed color-mix(in srgb, var(--brand-primary) 35%, transparent);
  cursor: help;
}

.graph-group-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.82rem;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}

.graph-group-toggle input {
  cursor: pointer;
}

.graph-entity-groups {
  display: grid;
  gap: 16px;
}

.graph-entity-group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 4px;
  margin-bottom: 4px;
  border-bottom: 1px solid color-mix(in srgb, var(--type-color) 30%, transparent);
}

.graph-entity-group-name {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.graph-entity-group-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  font-size: 0.7rem;
  background: color-mix(in srgb, var(--type-color) 16%, transparent);
  color: var(--text-secondary);
}

/* 关系权重分档色块 */
.graph-weight {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 0.76rem;
  font-weight: 600;
  white-space: nowrap;
}

.graph-weight--high {
  background: var(--success-soft, #dcfce7);
  color: var(--success-strong, #15803d);
}

.graph-weight--mid {
  background: var(--warning-soft, #fef3c7);
  color: var(--warning-strong, #b45309);
}

.graph-weight--low {
  background: var(--bg-tertiary, #f1f5f9);
  color: var(--text-tertiary, #64748b);
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
    grid-template-columns:
      34px var(--doc-name-col-width, minmax(100px, 1.35fr)) minmax(88px, 0.8fr) minmax(38px, 0.28fr)
      minmax(64px, 0.46fr) minmax(32px, 0.22fr) minmax(80px, 0.6fr) minmax(268px, 1.62fr);
    gap: 6px 6px;
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
    justify-content: center;
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

/* 知识图谱：与文件列表相同的一屏铺满布局，仅抽屉/画布内部滚动 */
.knowledge-detail-view--graph-tab {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin-top: 0;
  gap: 8px;
}

.knowledge-detail-view--graph-tab .knowledge-detail-layout {
  flex: 1;
  min-height: 0;
  gap: 12px;
  align-items: stretch;
}

.knowledge-detail-view--graph-tab .detail-sidebar-nav {
  padding: 12px 10px;
  gap: 8px;
}

.knowledge-detail-view--graph-tab .detail-nav-item {
  padding: 10px 12px;
}

.knowledge-detail-view--graph-tab .detail-main {
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  gap: 0;
}

.knowledge-detail-view--graph-tab .graph-viz-card {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 8px;
  overflow: hidden;
  padding: 10px 18px 10px;
}

.knowledge-detail-view--graph-tab .graph-viz-card .section-heading {
  flex-shrink: 0;
  margin: 0;
  gap: 0;
  align-items: center;
}

.knowledge-detail-view--graph-tab .graph-viz-card .section-heading p {
  display: none;
}

.knowledge-detail-view--graph-tab .graph-viz-card .section-heading h3 {
  font-size: 1.05rem;
}

.knowledge-detail-view--graph-tab .graph-viz-card :deep(.graph-viz-panel) {
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

/* 文件列表：一屏铺满，无页面级滚动条，15 行完整可见 */
.knowledge-detail-view--documents-tab.page-shell {
  flex: 1;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  margin-top: -20px;
  margin-left: -16px;
  gap: 0;
}

.knowledge-detail-view--documents-tab {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin-top: 0;
  gap: 0;
}

.knowledge-detail-view--documents-tab .knowledge-detail-layout {
  flex: 1;
  min-height: 0;
  height: 100%;
  gap: 12px;
  align-items: stretch;
  grid-template-rows: minmax(0, 1fr);
}

.knowledge-detail-view--documents-tab .detail-sidebar-nav {
  padding: 12px 10px;
  gap: 8px;
}

.knowledge-detail-view--documents-tab .detail-nav-item {
  padding: 10px 12px;
}

.knowledge-detail-view--documents-tab .detail-main {
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.knowledge-detail-view--documents-tab .documents-card {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 8px;
  overflow: hidden;
  padding: 8px 18px 8px;
}

.knowledge-detail-view--documents-tab .documents-card .section-heading {
  flex-shrink: 0;
  margin-bottom: 0;
  gap: 12px;
  align-items: center;
}

.knowledge-detail-view--documents-tab .documents-card .section-heading p {
  display: none;
}

.knowledge-detail-view--documents-tab .documents-card .section-heading h3 {
  font-size: 1.05rem;
}

.knowledge-detail-view--documents-tab .documents-card .documents-toolbar {
  flex-shrink: 0;
  gap: 10px;
}

.knowledge-detail-view--documents-tab .documents-toolbar--compact {
  align-items: flex-end;
}

.knowledge-detail-view--documents-tab .documents-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  flex-shrink: 0;
}

.knowledge-detail-view--documents-tab .documents-card .toolbar-field .field-label {
  margin-bottom: 4px;
  font-size: 0.8rem;
}

.knowledge-detail-view--documents-tab .documents-list-shell {
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.knowledge-detail-view--documents-tab .documents-list-shell .document-table-wrap {
  flex: 1;
  min-height: 0;
}

.knowledge-detail-view--documents-tab .documents-list-shell .documents-pagination {
  margin-top: auto;
  flex-shrink: 0;
  border-top: none;
  padding-top: 6px;
}

.knowledge-detail-view--documents-tab .document-table-wrap {
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.knowledge-detail-view--documents-tab .document-table-head {
  flex-shrink: 0;
  padding-bottom: 6px;
}

.knowledge-detail-view--documents-tab .document-table-body {
  flex: 1 1 auto;
  min-height: 0;
  max-height: 100%;
  overflow-y: auto;
  align-content: start;
}

.knowledge-detail-view--documents-tab .document-row {
  padding: 9px 12px;
}

.knowledge-detail-view--documents-tab .documents-pagination {
  flex-shrink: 0;
  margin-top: 0;
  padding-top: 6px;
  gap: 10px 16px;
}

.knowledge-detail-view--documents-tab .documents-batch-actions {
  flex-basis: 100%;
  margin-left: 0;
  justify-content: flex-end;
}

.documents-card--fresh-empty {
  grid-template-rows: auto minmax(0, 1fr);
}

.documents-empty-wrap {
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.documents-empty-wrap :deep(.empty-state-card) {
  width: min(100%, 440px);
  margin: 0 auto;
  padding: 28px 24px;
  border-style: dashed;
}

.documents-empty-wrap :deep(.empty-state-copy p) {
  max-width: 360px;
  font-size: 0.9rem;
  line-height: 1.6;
}

.kb-process-log {
  gap: 20px;
}

.kb-log-kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.kb-log-kpi-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 16px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-secondary);
  box-shadow: var(--card-shadow-xs);
}

.kb-log-kpi-card--skeleton {
  min-height: 88px;
  background: linear-gradient(120deg, var(--bg-tertiary) 0%, rgba(148, 163, 184, 0.14) 50%, var(--bg-tertiary) 100%);
}

.kb-log-kpi-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  flex-shrink: 0;
}

.kb-log-kpi-icon.tone-blue {
  background: color-mix(in srgb, #3b82f6 14%, var(--bg-tertiary));
  color: #2563eb;
}

.kb-log-kpi-icon.tone-green {
  background: color-mix(in srgb, #22c55e 14%, var(--bg-tertiary));
  color: #16a34a;
}

.kb-log-kpi-icon.tone-teal {
  background: color-mix(in srgb, #14b8a6 14%, var(--bg-tertiary));
  color: #0d9488;
}

.kb-log-kpi-body {
  min-width: 0;
}

.kb-log-kpi-value {
  margin: 0;
  font-size: 1.65rem;
  font-weight: 700;
  line-height: 1.1;
  color: var(--text-primary);
}

.kb-log-kpi-label {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 0.84rem;
}

.kb-log-kpi-substats {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.kb-log-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 4px;
  border-radius: 999px;
  vertical-align: middle;
}

.kb-log-dot--success {
  background: #22c55e;
}

.kb-log-dot--failed {
  background: #ef4444;
}

.kb-log-toolbar {
  display: flex;
  flex-wrap: nowrap;
  gap: 10px;
  align-items: center;
  justify-content: flex-end;
}

.kb-log-filter-select {
  flex: 0 0 auto;
  width: 132px;
}

.kb-log-search {
  width: 320px;
  max-width: 320px;
  flex: 0 0 auto;
  min-width: 0;
}

.kb-log-toolbar .btn {
  flex: 0 0 auto;
  white-space: nowrap;
}

.kb-log-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border-color);
  border-radius: 16px;
}

.kb-log-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}

.kb-log-table th,
.kb-log-table td {
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
  vertical-align: top;
}

.kb-log-table th {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-weight: 600;
}

.kb-log-table tbody tr:last-child td {
  border-bottom: none;
}

.kb-log-action-cell {
  display: grid;
  gap: 4px;
}

.kb-log-summary {
  color: var(--text-tertiary);
  font-size: 0.8rem;
}

.kb-log-expand-row td {
  background: var(--bg-tertiary);
}

.kb-log-item-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.kb-log-item-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.kb-log-item-name {
  min-width: 0;
  flex: 1 1 180px;
}

.kb-log-item-error {
  color: var(--text-secondary);
  font-size: 0.8rem;
}

.kb-log-expand-loading,
.kb-log-expand-empty {
  color: var(--text-tertiary);
  font-size: 0.84rem;
}

.kb-log-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

@media (max-width: 960px) {
  .kb-log-kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
