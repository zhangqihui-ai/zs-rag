<template>
  <Layout>
    <div
      class="page-shell chat-view"
      :class="{
        'page-shell--kb-dropdown-open': settingsFloatingOpen,
      }"
    >
      <!-- Grid View：对话列表 -->
      <div v-if="!chatStore.activeConversationId" class="chat-grid-view">
        <div class="chat-grid-header">
          <div class="chat-grid-title">
            <AppIcon name="chat" :size="24" style="color: var(--brand-primary);" />
            <h2>聊天</h2>
          </div>
          <div class="chat-grid-actions">
            <div class="search-box">
              <AppIcon name="search" :size="16" style="color: var(--text-tertiary);" />
              <input type="text" placeholder="搜索" v-model="searchQuery" class="input search-input" />
            </div>
            <button class="btn btn-primary" type="button" @click="openCreateChatModal">
              <AppIcon name="plus" :size="16" />
              创建聊天
            </button>
          </div>
        </div>

        <div class="chat-cards-container">
          <div 
            v-for="chat in filteredConversations" 
            :key="chat.id" 
            class="chat-grid-card"
            @click="chatStore.selectConversation(chat.id)"
          >
            <div class="chat-grid-card-icon">
              <AppIcon name="chat" :size="16" />
            </div>
            <div class="chat-grid-card-content" style="flex: 1;">
              <template v-if="editGridChatId === chat.id">
                <input 
                  type="text" 
                  class="input" 
                  v-model="editGridChatTitle" 
                  @click.stop 
                  @keyup.enter="saveGridTitle" 
                  @keyup.esc="cancelEditGridTitle" 
                  @blur="saveGridTitle"
                  style="padding: 4px 8px; font-size: 1rem; margin: 0; width: 100%;"
                  v-focus
                />
              </template>
              <template v-else>
                <h4 :title="chat.title">{{ chat.title }}</h4>
              </template>
              <span>{{ new Date(chat.updated_at).toLocaleString() }}</span>
            </div>
            
            <div class="chat-grid-card-menu-container">
              <button class="tile-menu-trigger" type="button" @click.stop="toggleMenu(chat.id)">⋯</button>
              <div v-if="openMenuId === chat.id" class="tile-menu" @click.stop>
                <button class="tile-menu-item" type="button" @click.stop="startEditGridTitle(chat)">修改</button>
                <button class="tile-menu-item danger" type="button" @click.stop="openDeleteConversation(chat)">删除...</button>
              </div>
            </div>
          </div>
          <EmptyState
            v-if="filteredConversations.length === 0"
            title="没有找到对话"
            description="请点击右上角的“创建聊天”开始您的第一次探索吧！"
            icon="chat"
            style="grid-column: 1 / -1; margin-top: 40px;"
          />
        </div>
      </div>

      <!-- Detail View -->
      <div
        v-else
        class="chat-detail-view"
        :class="{ 'chat-detail-view--kb-dropdown-open': settingsFloatingOpen }"
      >

        <div
          class="chat-layout"
          :class="{
            'chat-layout--settings-open': settingsDrawerOpen && chatStore.activeSessionId,
            'chat-layout--kb-dropdown-open': settingsFloatingOpen,
          }"
        >
          <aside class="surface-card conversation-rail">
          <div class="rail-back-nav">
            <button type="button" class="rail-back-btn" @click="chatStore.leaveConversation()">
              <AppIcon name="chat" :size="16" />
              <span>聊天</span>
            </button>
            <span class="rail-bc-sep">/</span>
            <span class="rail-bc-title" :title="chatStore.activeConversation?.title || ''">
              {{ chatStore.activeConversation?.title || '…' }}
            </span>
          </div>
          <div class="session-rail-header">
            <h3 class="session-rail-title">会话</h3>
            <div class="session-rail-header-actions">
              <button type="button" class="btn-new-session" @click.stop="addSession">
                <AppIcon name="plus" :size="14" />
                新建会话
              </button>
              <button
                type="button"
                class="btn-session-batch"
                :class="{ active: sessionBatchMode }"
                title="批量选择删除"
                aria-label="批量选择删除"
                @click.stop="toggleSessionBatchMode"
              >
                <AppIcon name="close" :size="14" />
              </button>
            </div>
          </div>

          <div v-if="sessionBatchMode" class="session-batch-toolbar">
            <span class="session-batch-count">已选 {{ sessionBatchSelectedSet.size }} 个</span>
            <button type="button" class="btn-text-inline" @click.stop="toggleSelectAllSessionsForBatch">
              {{ sessionBatchAllSelected ? '取消全选' : '全选' }}
            </button>
            <button
              type="button"
              class="btn-text-inline danger"
              :disabled="sessionBatchSelectedSet.size === 0"
              @click.stop="openBatchDeleteModal"
            >
              删除选中
            </button>
            <button type="button" class="btn-text-inline" @click.stop="exitSessionBatchMode">完成</button>
          </div>

          <div class="session-lines scrollbar-pill">
            <div
              v-for="session in sortedSessionsInConversation"
              :key="session.id"
              class="session-line"
              :class="{
                active: session.id === chatStore.activeSessionId,
                'menu-open': sessionMenuOpenId === session.id,
                'batch-mode': sessionBatchMode,
                'batch-selected':
                  sessionBatchMode && sessionBatchSelectedSet.has(normSessionId(session.id)),
              }"
              @click="onSessionRowClick(session, $event)"
            >
              <input
                v-if="sessionBatchMode"
                type="checkbox"
                class="session-line-check"
                :checked="sessionBatchSelectedSet.has(normSessionId(session.id))"
                @click.prevent.stop="toggleSessionBatchSelection(session.id)"
              />
              <template v-if="renamingSessionId === session.id">
                <input
                  v-model="renameSessionDraft"
                  class="input session-line-input"
                  @click.stop
                  @blur="saveRenameSession"
                  @keyup.enter="saveRenameSession"
                  @keyup.esc="cancelRenameSession"
                  ref="renameSessionInputRef"
                />
              </template>
              <template v-else>
                <span class="session-line-title" :title="session.title">{{ session.title }}</span>
              </template>
              <div v-if="!sessionBatchMode" class="session-line-actions" @click.stop>
                <button
                  type="button"
                  class="session-line-more"
                  :aria-expanded="sessionMenuOpenId === session.id"
                  aria-label="会话操作"
                  @click.stop="toggleSessionMenu(session.id)"
                >
                  <AppIcon name="more-vertical" :size="16" />
                </button>
                <div
                  v-if="sessionMenuOpenId === session.id"
                  class="session-line-menu"
                  @click.stop
                >
                  <button type="button" class="session-line-menu-item" @click="onPinSession(session)">
                    <AppIcon name="pin" :size="16" />
                    置顶
                  </button>
                  <button type="button" class="session-line-menu-item" @click="onRenameSession(session)">
                    <AppIcon name="pencil" :size="16" />
                    重命名
                  </button>
                  <button type="button" class="session-line-menu-item danger" @click="onDeleteSessionFromMenu(session)">
                    <AppIcon name="trash" :size="16" />
                    删除
                  </button>
                </div>
              </div>
            </div>
          </div>
        </aside>

        <section class="surface-card chat-main" v-if="chatStore.activeSessionId">
          <div class="chat-main-header">
            <p v-if="chatStore.activeSession" class="chat-session-line">
              当前会话：{{ chatStore.activeSession.title }}
            </p>
            <div class="chat-header-meta">
              <div class="header-model-picker">
                <button
                  type="button"
                  class="header-model-trigger"
                  :disabled="!activeConfig"
                  :aria-expanded="headerModelMenuOpen"
                  aria-haspopup="listbox"
                  aria-label="选择聊天模型"
                  @click.stop="toggleHeaderModelMenu"
                >
                  <span class="header-model-label" :title="headerModelTriggerTitle">{{ headerModelTriggerLabel }}</span>
                  <AppIcon
                    name="chevron-down"
                    :size="14"
                    class="header-model-chevron"
                    :class="{ 'is-open': headerModelMenuOpen }"
                  />
                </button>
                <div
                  v-if="headerModelMenuOpen && activeConfig"
                  class="header-model-dropdown"
                  role="listbox"
                  aria-label="模型列表"
                  @click.stop
                >
                  <template v-if="sortedModelGroups.length > 0">
                    <div
                      v-for="group in sortedModelGroups"
                      :key="group.provider_id"
                      class="header-model-group"
                    >
                      <div class="header-model-group-title">{{ group.provider_name }}</div>
                      <button
                        v-for="m in group.models"
                        :key="m.id"
                        type="button"
                        role="option"
                        class="header-model-option"
                        :class="{ 'is-current': isHeaderModelOptionCurrent(m) }"
                        @click="pickHeaderModel(m)"
                      >
                        <span class="header-model-option-name">{{ m.model_name }}</span>
                      </button>
                    </div>
                  </template>
                  <div v-else class="header-model-empty">暂无可选模型，请在管理后台启用 LLM 或到模型管理同步</div>
                </div>
              </div>
              <button type="button" class="btn-multi-model-compare" @click="onMultiModelCompareClick">
                <AppIcon name="arrow-up-right" :size="16" />
                多模型对比
              </button>
              <button
                type="button"
                class="btn-chat-settings"
                aria-label="打开对话设置"
                :aria-expanded="settingsDrawerOpen"
                @click.stop="toggleSettingsPanel"
              >
                <AppIcon name="settings" :size="18" />
                设置
              </button>
            </div>
          </div>

          <div class="chat-main-body">
            <div
              ref="messageListRef"
              class="message-list scrollbar-pill"
              @scroll.passive="onMessageListScroll"
            >
            <div
              v-for="message in activeMessages"
              :key="message.id"
              class="msg-row"
              :class="message.role === 'user' ? 'msg-row--user' : 'msg-row--assistant'"
            >
              <template v-if="message.role === 'assistant'">
                <div class="msg-avatar msg-avatar--assistant" aria-hidden="true">
                  <AppIcon name="spark" :size="20" />
                </div>
                <div class="msg-stack msg-stack--assistant">
                  <div class="msg-toolbar">
                    <button type="button" class="msg-tool" title="复制" @click="copyMessageText(message.content)">
                      <AppIcon name="copy" :size="16" />
                    </button>
                    <button type="button" class="msg-tool" title="删除" @click="removeMessageLocal(message.id)">
                      <AppIcon name="trash" :size="16" />
                    </button>
                  </div>
                  <div
                    class="msg-text msg-text--assistant"
                    :class="{ 'is-streaming': isMessageStreaming(message) }"
                  >
                    <template
                      v-if="showCitationsEnabled && !isMessageStreaming(message)"
                    >
                      <template v-for="(seg, si) in assistantContentSegments(message.content)" :key="si">
                        <span v-if="seg.k === 't'">{{ seg.v }}</span>
                        <span
                          v-else
                          tabindex="0"
                          role="button"
                          class="msg-citation-badge"
                          :title="citationRefTitle(seg.n, message) + '（点击查看切片）'"
                          @click="openCitationDetailByRef(seg.n, message)"
                          @keydown.enter.prevent="openCitationDetailByRef(seg.n, message)"
                          @keydown.space.prevent="openCitationDetailByRef(seg.n, message)"
                        >{{ seg.n }}</span>
                      </template>
                    </template>
                    <template v-else>{{ message.content }}</template>
                  </div>
                  <div
                    v-if="showAssistantCitationsFoot(message)"
                    class="msg-citations-block"
                    aria-label="知识库引文"
                  >
                    <div class="msg-citations-title">引文出处</div>
                    <ul class="msg-citations-list">
                      <li v-for="c in message.citations" :key="c.ref">
                        <button
                          type="button"
                          class="msg-citation-row-btn"
                          @click="openCitationDetail(c)"
                        >
                          <span class="msg-citation-ref">{{ c.ref }}</span>
                          <span class="msg-citation-meta">
                            <span class="msg-citation-doc">{{ c.document_name }}</span>
                            <span v-if="c.page_no != null" class="msg-citation-page">第 {{ c.page_no }} 页</span>
                            <span v-if="c.chunk_index != null" class="msg-citation-chunk"
                              >片段 #{{ c.chunk_index + 1 }}</span
                            >
                          </span>
                        </button>
                      </li>
                    </ul>
                  </div>
                </div>
              </template>
              <template v-else>
                <div class="msg-stack msg-stack--user">
                  <div class="msg-toolbar msg-toolbar--user">
                    <button type="button" class="msg-tool" title="复制" @click="copyMessageText(message.content)">
                      <AppIcon name="copy" :size="16" />
                    </button>
                    <button type="button" class="msg-tool" title="删除" @click="removeMessageLocal(message.id)">
                      <AppIcon name="trash" :size="16" />
                    </button>
                  </div>
                  <div class="msg-bubble-row">
                    <div class="msg-bubble">{{ message.content }}</div>
                    <div class="msg-avatar msg-avatar--user" aria-hidden="true">
                      <AppIcon name="user" :size="18" />
                    </div>
                  </div>
                </div>
              </template>
            </div>
            </div>
            <button
              v-show="showJumpToBottom"
              type="button"
              class="chat-jump-bottom"
              aria-label="回到底部"
              @click="scrollChatToBottom"
            >
              <AppIcon name="chevron-down" :size="18" />
              回到底部
            </button>
          </div>

          <form class="composer" @submit.prevent="handleSend">
            <div class="composer-input-wrap">
              <textarea
                v-model="draftMessage"
                class="textarea composer-textarea"
                rows="4"
                aria-label="消息内容"
                placeholder="请输入问题..."
              />
              <button
                class="btn btn-primary composer-send"
                type="submit"
                :disabled="!draftMessage.trim() || chatStore.isGenerating"
              >
                <AppIcon name="send" :size="16" />
                发送问题
              </button>
            </div>
          </form>
        </section>
        <section class="surface-card chat-main" v-else>
          <EmptyState
            title="尚未选择或创建对话"
            description="请从左侧点击「聊天」返回首页，再创建或进入对话。"
            icon="chat"
          />
        </section>

        <aside
          v-if="settingsDrawerOpen && chatStore.activeSessionId"
          class="surface-card chat-settings-panel side-panel scrollbar-pill"
          :class="{ 'chat-settings-panel--kb-open': kbDropdownOpen }"
          aria-labelledby="chat-settings-title"
        >
            <div class="chat-settings-toolbar">
              <h3 id="chat-settings-title" class="chat-settings-title">对话设置</h3>
              <button type="button" class="btn btn-text btn-settings-close" aria-label="关闭设置" @click="closeSettingsDrawer">
                <AppIcon name="close" :size="20" />
              </button>
            </div>
          <div class="chat-side-actions">
            <button type="button" class="btn btn-embed-site" @click="showEmbedModal = true">
              <AppIcon name="send" :size="16" />
              嵌入网站
            </button>
            <button type="button" class="btn btn-access-api" @click="showAccessModal = true">
              接入
            </button>
          </div>
          <section v-if="activeConfig" class="surface-card chat-system-prompt-card">
            <div class="section-heading compact-heading">
              <h4>系统提示词</h4>
            </div>
            <label class="field system-prompt-field">
              <textarea
                v-model="systemPromptDraft"
                class="textarea system-prompt-textarea"
                rows="9"
                aria-label="系统提示词"
                @blur="flushSystemPrompt"
              />
            </label>
          </section>

          <section class="surface-card">
            <div class="section-heading compact-heading">
              <h4>知识库上下文</h4>
            </div>

            <div v-if="activeConfig" class="field kb-multiselect-field">
              <KnowledgeBaseMultiSelect
                v-model="chatKnowledgeBaseIds"
                v-model:open="kbDropdownOpen"
                :knowledge-bases="kbs"
                :embedding-models="embeddingModelsFlat"
                :embedding-space-default="embeddingSpaceDefault"
              />
            </div>
            <div v-else class="kb-settings-loading">加载配置中…</div>

            <div v-if="activeConfig" class="field chat-retrieval-topk-field">
              <span class="chat-topk-field-label">
                Top K
                <span class="chat-topk-help" :title="RETRIEVAL_TOP_K_HELP" tabindex="0" role="note">?</span>
              </span>
              <div class="chat-topk-slider-row">
                <input
                  v-model.number="chatTopK"
                  class="input chat-topk-number-input"
                  type="number"
                  min="1"
                  max="50"
                  step="1"
                  aria-label="Top K"
                  @change="onChatTopKCommit"
                  @blur="onChatTopKCommit"
                />
                <input
                  v-model.number="chatTopK"
                  class="chat-topk-progress-range"
                  type="range"
                  min="1"
                  max="50"
                  step="1"
                  :style="chatTopKSliderStyle"
                  aria-label="Top K 滑动条"
                  @change="onChatTopKCommit"
                />
              </div>
            </div>

            <div v-if="activeConfig" class="field chat-citation-toggle-field">
              <div class="chat-citation-toggle-head">
                <span class="field-label">显示引文</span>
                <span
                  class="chat-citation-help"
                  tabindex="0"
                  role="img"
                  title="开启后，助手回复中的 [1]、[2] 等会显示为角标，并在消息下方列出对应知识库文档与页码；仅在选择知识库并命中检索片段时生效。"
                >
                  <AppIcon name="help-circle" :size="16" />
                </span>
              </div>
              <label class="chat-switch">
                <input
                  type="checkbox"
                  role="switch"
                  :checked="activeConfig.show_citations !== false"
                  @change="updateConfig('show_citations', ($event.target as HTMLInputElement).checked)"
                />
                <span class="chat-switch-track" aria-hidden="true" />
              </label>
            </div>
          </section>

          <section id="chat-panel-model-config" class="surface-card">
            <div class="section-heading compact-heading">
              <div>
                <h4>模型配置</h4>
                <p>本对话下所有会话共用此配置</p>
              </div>
            </div>

            <div style="display:flex; flex-direction: column; gap: 16px;">
              <label class="field panel-model-field">
                <span class="field-label">选择大语言模型</span>
                <div v-if="activeConfig" ref="panelModelPickerRef" class="panel-model-picker">
                  <button
                    type="button"
                    class="panel-model-trigger"
                    :aria-expanded="sidePanelModelMenuOpen"
                    aria-haspopup="listbox"
                    aria-label="选择大语言模型"
                    @click.stop="toggleSidePanelModelMenu"
                  >
                    <span class="panel-model-trigger-label" :title="headerModelTriggerTitle">{{
                      headerModelTriggerLabel
                    }}</span>
                    <AppIcon
                      name="chevron-down"
                      :size="14"
                      class="header-model-chevron"
                      :class="{ 'is-open': sidePanelModelMenuOpen }"
                    />
                  </button>
                  <div
                    v-if="sidePanelModelMenuOpen"
                    class="panel-model-dropdown panel-model-dropdown--fixed"
                    :style="panelModelDropdownFloatingStyle"
                    role="presentation"
                    @click.stop
                  >
                    <div
                      class="panel-model-list scrollbar-pill"
                      role="listbox"
                      aria-label="大语言模型列表"
                    >
                      <template v-if="sortedModelGroups.length > 0">
                        <div
                          v-for="group in sortedModelGroups"
                          :key="group.provider_id"
                          class="header-model-group"
                        >
                          <div class="header-model-group-title">{{ group.provider_name }}</div>
                          <button
                            v-for="m in group.models"
                            :key="m.id"
                            type="button"
                            role="option"
                            :aria-selected="isHeaderModelOptionCurrent(m)"
                            class="header-model-option"
                            :class="{ 'is-current': isHeaderModelOptionCurrent(m) }"
                            @click="pickSidePanelModel(m)"
                          >
                            <span class="header-model-option-name">{{ m.model_name }}</span>
                          </button>
                        </div>
                      </template>
                      <div v-else class="header-model-empty">
                        暂无可选模型，请在管理后台启用 LLM 或到模型管理同步
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else class="panel-model-trigger panel-model-trigger--disabled" aria-disabled="true">
                  <span class="panel-model-trigger-label">加载配置中…</span>
                </div>
              </label>

              <label class="field">
                <span class="field-label">Temperature ({{ activeConfig?.temperature || 0.7 }})</span>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  :value="activeConfig?.temperature || 0.7"
                  @change="updateConfig('temperature', parseFloat(($event.target as HTMLInputElement).value))"
                />
              </label>

              <label class="field">
                <span class="field-label">Max Tokens ({{ activeConfig?.max_tokens || 2000 }})</span>
                <input
                  type="range"
                  min="100"
                  max="8000"
                  step="100"
                  :value="activeConfig?.max_tokens || 2000"
                  @change="updateConfig('max_tokens', parseInt(($event.target as HTMLInputElement).value, 10))"
                />
              </label>
            </div>
          </section>
        </aside>

      </div>
      </div>
      <!-- 引文 · 切片正文 -->
      <div v-if="citationModalOpen" class="modal-overlay" role="presentation" @click.self="closeCitationModal">
        <div class="modal-content citation-chunk-modal" @click.stop>
          <div class="modal-header">
            <h3>引文 · 召回切片</h3>
            <button type="button" class="btn btn-text" aria-label="关闭" @click="closeCitationModal">
              <AppIcon name="close" :size="20" />
            </button>
          </div>
          <div class="modal-body citation-chunk-modal-base">
            <p v-if="citationModalCitation" class="citation-chunk-modal-meta">
              <strong>{{ citationModalCitation.document_name }}</strong>
              <template v-if="citationModalCitation.page_no != null">
                · 第 {{ citationModalCitation.page_no }} 页</template
              >
              <template v-if="citationModalCitation.chunk_index != null">
                · 片段 #{{ citationModalCitation.chunk_index + 1 }}</template
              >
            </p>
            <div v-if="citationModalLoading" class="loading-inline">加载中…</div>
            <p v-else-if="citationModalError" class="status-box error citation-chunk-modal-err">{{ citationModalError }}</p>
            <pre v-else-if="citationModalChunk" class="citation-chunk-modal-body">{{ citationModalChunk.content }}</pre>
          </div>
          <div class="modal-footer citation-chunk-modal-footer">
            <button
              type="button"
              class="btn"
              style="background: var(--bg-secondary); border: 1px solid var(--border-color)"
              @click="closeCitationModal"
            >
              关闭
            </button>
            <button
              type="button"
              class="btn btn-primary"
              :disabled="
                !citationModalCitation ||
                resolveCitationKbId(citationModalCitation) == null ||
                citationModalCitation.document_id == null
              "
              @click="goCitationDocumentPage"
            >
              打开文档原文
            </button>
          </div>
        </div>
      </div>

      <!-- Create Chat Modal -->
      <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
        <div class="modal-content" style="max-width: 460px;">
          <div class="modal-header">
            <h3>创建聊天</h3>
            <button class="btn btn-text" @click="showCreateModal = false">
              <AppIcon name="close" :size="20" />
            </button>
          </div>
          <div class="modal-body">
            <div class="field">
              <label class="field-label">请输入新对话名称</label>
              <input 
                v-model="newChatTitle" 
                type="text" 
                class="input" 
                placeholder="例如：关于XX的讨论" 
                @keyup.enter="handleCreate"
                ref="createInputRef"
              />
            </div>
          </div>
          <div class="modal-footer" style="display: flex; justify-content: flex-end; gap: 12px; margin-top: 24px;">
            <button class="btn" style="background: var(--bg-secondary); border: 1px solid var(--border-color);" @click="showCreateModal = false">取消</button>
            <button class="btn btn-primary" :disabled="!newChatTitle.trim()" @click="handleCreate">确定</button>
          </div>
        </div>
      </div>

      <!-- Delete Chat Modal -->
      <div v-if="deleteModalOpen && deleteTarget" class="modal-overlay" @click.self="closeDeleteModal">
        <div class="modal-content" style="max-width: 460px;">
          <div class="modal-header">
            <h3>{{ deleteTarget.kind === 'conversation' ? '删除对话' : '删除会话' }}</h3>
            <button class="btn btn-text" @click="closeDeleteModal">
              <AppIcon name="close" :size="20" />
            </button>
          </div>
          <div class="modal-body">
            <p style="margin: 0 0 16px 0; color: var(--text-secondary); line-height: 1.5;">
              <template v-if="deleteTarget.kind === 'conversation'">
                将删除对话 <strong>「{{ deleteTarget.title }}」</strong> 及其下全部会话，且不可恢复。
              </template>
              <template v-else>
                将删除会话 <strong>「{{ deleteTarget.title }}」</strong> 及其消息记录，且不可恢复。
              </template>
            </p>
            <div class="field">
              <label class="field-label">请输入名称以确认删除</label>
              <input 
                v-model.trim="deleteConfirmName" 
                type="text" 
                class="input" 
                :placeholder="deleteTarget.title" 
                @keyup.enter="confirmDelete"
              />
              <p v-if="deleteConfirmName && !canSubmitDelete" style="margin: 6px 0 0; font-size: 0.82rem; color: var(--text-tertiary);">
                名称不匹配，无法提交。
              </p>
            </div>
          </div>
          <div class="modal-footer" style="display: flex; justify-content: flex-end; gap: 12px; margin-top: 24px;">
            <button class="btn" style="background: var(--bg-secondary); border: 1px solid var(--border-color);" @click="closeDeleteModal">取消</button>
            <button class="btn" style="background: var(--danger-color); color: #fff;" :disabled="!canSubmitDelete || isDeleting" @click="confirmDelete">
              {{ isDeleting ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 批量删除会话 -->
      <div v-if="batchDeleteModalOpen" class="modal-overlay" @click.self="closeBatchDeleteModal">
        <div class="modal-content" style="max-width: 460px;">
          <div class="modal-header">
            <h3>批量删除会话</h3>
            <button class="btn btn-text" type="button" @click="closeBatchDeleteModal">
              <AppIcon name="close" :size="20" />
            </button>
          </div>
          <div class="modal-body">
            <p style="margin: 0; color: var(--text-secondary); line-height: 1.5;">
              将删除 <strong>{{ sessionBatchSelectedSet.size }}</strong> 个会话及其消息记录，且不可恢复。
            </p>
          </div>
          <div class="modal-footer" style="display: flex; justify-content: flex-end; gap: 12px; margin-top: 24px;">
            <button
              class="btn"
              type="button"
              style="background: var(--bg-secondary); border: 1px solid var(--border-color);"
              @click="closeBatchDeleteModal"
            >
              取消
            </button>
            <button
              class="btn"
              type="button"
              style="background: var(--danger-color); color: #fff;"
              :disabled="isBatchDeleting"
              @click="confirmBatchDeleteSessions"
            >
              {{ isBatchDeleting ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 嵌入网站 -->
      <div v-if="showEmbedModal" class="modal-overlay" @click.self="showEmbedModal = false">
        <div class="modal-content modal-wide">
          <div class="modal-header">
            <h3>嵌入网站</h3>
            <button class="btn btn-text" type="button" @click="showEmbedModal = false">
              <AppIcon name="close" :size="20" />
            </button>
          </div>
          <div class="modal-body access-modal-body">
            <p class="access-intro">
              将下方地址或 iframe 代码嵌入企业内网门户；访问者需已登录且能加载本应用（注意同源策略与 Cookie）。
            </p>
            <div class="access-block">
              <div class="access-block-head">
                <span class="access-label">对话页 URL</span>
                <button type="button" class="btn btn-text btn-copy" @click="copyText(chatPageUrl)">复制</button>
              </div>
              <pre class="access-pre">{{ chatPageUrl }}</pre>
            </div>
            <div class="access-block">
              <div class="access-block-head">
                <span class="access-label">iframe 示例</span>
                <button type="button" class="btn btn-text btn-copy" @click="copyText(embedIframeSnippet)">复制</button>
              </div>
              <pre class="access-pre">{{ embedIframeSnippet }}</pre>
            </div>
          </div>
        </div>
      </div>

      <!-- 接入信息 -->
      <div v-if="showAccessModal" class="modal-overlay" @click.self="showAccessModal = false">
        <div class="modal-content modal-wide">
          <div class="modal-header">
            <h3>接入信息</h3>
            <button class="btn btn-text" type="button" @click="showAccessModal = false">
              <AppIcon name="close" :size="20" />
            </button>
          </div>
          <div class="modal-body access-modal-body">
            <p class="access-intro">
              以下说明面向当前选中会话的实时对话与相关 REST；请在请求中携带企业空间与登录态。
            </p>

            <h4 class="access-section-title">页面 URL</h4>
            <pre class="access-pre">{{ chatPageUrl }}</pre>

            <h4 class="access-section-title">流式对话（HTTP SSE）</h4>
            <p class="access-muted">
              使用 <strong>POST</strong> 提交本轮用户输入，响应为 <code>text/event-stream</code>；每条事件为
              <code>data: &lt;json&gt;</code>，与原先 WebSocket 推送的 JSON 结构一致（<code>assistant_delta</code> /
              <code>assistant_done</code>）。
            </p>
            <pre class="access-pre">{{ sseStreamUrlExample }}</pre>

            <h4 class="access-section-title">请求体（JSON）</h4>
            <pre class="access-pre">{{ sseBodyExample }}</pre>

            <h4 class="access-section-title">REST 接口示例</h4>
            <ul class="access-list">
              <li><code>GET {{ apiBaseUrl }}/api/v1/chats/sessions/{{ sessionIdPlaceholder }}/messages</code> — 历史消息</li>
              <li><code>GET {{ apiBaseUrl }}/api/v1/chats/sessions/{{ sessionIdPlaceholder }}/config</code> — 对话（chat）级模型配置</li>
              <li><code>GET {{ apiBaseUrl }}/api/v1/chats</code> — 对话列表</li>
              <li><code>GET {{ apiBaseUrl }}/api/v1/chats/{{ chatIdPlaceholder }}/sessions</code> — 会话列表</li>
              <li><code>POST {{ apiBaseUrl }}/api/v1/chat/completions</code> — OpenAI 形态补全（流式/非流式）</li>
            </ul>

            <h4 class="access-section-title">所需认证信息</h4>
            <pre class="access-pre">Authorization: Bearer &lt;登录后获得的 access_token&gt;
X-Enterprise-Space: &lt;企业空间 slug，缺省可为 default&gt;</pre>

            <h4 class="access-section-title">SSE 事件示例</h4>
            <pre class="access-pre">{{ sseEventsExample }}</pre>
          </div>
        </div>
      </div>

    </div>
  </Layout>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'

import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import Layout from '../components/Layout.vue'
import KnowledgeBaseMultiSelect from '../components/knowledge-base/KnowledgeBaseMultiSelect.vue'

import { useChatStore } from '../stores/chat'
import { streamChatCompletion } from '../lib/chat-sse'
import { useRouter } from 'vue-router'
import { knowledgeBaseApi, type KnowledgeBase, type KnowledgeChunk } from '../api/knowledge-base'
import { modelApi, defaultModelApi, type DefaultModelOption, type ModelItem, type ProviderModelsGroup } from '../api/model-management'
import type { ChatSession, ChatMessage, ChatCitation } from '../api/chat'

type AssistantSeg = { k: 't'; v: string } | { k: 'r'; n: number }

function normalizeCitations(raw: unknown): ChatCitation[] | undefined {
  if (!Array.isArray(raw) || raw.length === 0) {
    return undefined
  }
  const out: ChatCitation[] = []
  for (const row of raw) {
    if (!row || typeof row !== 'object') {
      continue
    }
    const r = row as Record<string, unknown>
    const ref = Number(r.ref)
    if (!Number.isFinite(ref)) {
      continue
    }
    out.push({
      ref,
      document_name: String(r.document_name ?? ''),
      page_no: r.page_no == null ? null : Number(r.page_no),
      knowledge_base_id: r.knowledge_base_id != null ? Number(r.knowledge_base_id) : undefined,
      chunk_id: r.chunk_id != null ? Number(r.chunk_id) : undefined,
      document_id: r.document_id != null ? Number(r.document_id) : undefined,
      chunk_index: r.chunk_index != null ? Number(r.chunk_index) : undefined,
      score: r.score != null ? Number(r.score) : undefined,
    })
  }
  return out.length ? out : undefined
}

function assistantContentSegments(text: string): AssistantSeg[] {
  const out: AssistantSeg[] = []
  const re = /\[(\d+)\]/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      out.push({ k: 't', v: text.slice(last, m.index) })
    }
    out.push({ k: 'r', n: parseInt(m[1], 10) })
    last = m.index + m[0].length
  }
  if (last < text.length) {
    out.push({ k: 't', v: text.slice(last) })
  }
  if (out.length === 0) {
    out.push({ k: 't', v: text })
  }
  return out
}

function citationRefTitle(refNum: number, message: ChatMessage): string {
  const c = message.citations?.find((x) => x.ref === refNum)
  if (!c) {
    return `引文 ${refNum}`
  }
  const page = c.page_no != null ? ` · 第 ${c.page_no} 页` : ''
  return `${c.document_name}${page}`
}

const chatStore = useChatStore()
const router = useRouter()

const citationModalOpen = ref(false)
const citationModalCitation = ref<ChatCitation | null>(null)
const citationModalChunk = ref<KnowledgeChunk | null>(null)
const citationModalLoading = ref(false)
const citationModalError = ref('')

function resolveCitationKbId(c: ChatCitation): number | null {
  if (c.knowledge_base_id != null && Number.isFinite(c.knowledge_base_id)) {
    return c.knowledge_base_id
  }
  const ids = chatStore.activeConfiguration?.knowledge_base_ids ?? []
  return ids.length === 1 ? ids[0]! : null
}

function closeCitationModal() {
  citationModalOpen.value = false
  citationModalCitation.value = null
  citationModalChunk.value = null
  citationModalError.value = ''
  citationModalLoading.value = false
}

async function openCitationDetail(c: ChatCitation) {
  citationModalCitation.value = c
  citationModalChunk.value = null
  citationModalError.value = ''
  citationModalOpen.value = true
  const kbId = resolveCitationKbId(c)
  const chunkId = c.chunk_id
  if (kbId == null || chunkId == null) {
    citationModalError.value =
      kbId == null
        ? '无法确定所属知识库（多库对话请在设置中暂只选一个，或重新对话以生成含知识库信息的引文）。'
        : '该引文缺少切片 ID，无法加载正文。'
    return
  }
  citationModalLoading.value = true
  try {
    citationModalChunk.value = await knowledgeBaseApi.getChunk(kbId, chunkId)
  } catch (e) {
    console.error(e)
    citationModalError.value = '加载切片正文失败，请稍后重试。'
  } finally {
    citationModalLoading.value = false
  }
}

function openCitationDetailByRef(refNum: number, message: ChatMessage) {
  const c = message.citations?.find((x) => x.ref === refNum)
  if (c) {
    void openCitationDetail(c)
  }
}

function goCitationDocumentPage() {
  const c = citationModalCitation.value
  if (!c) {
    return
  }
  const kbId = resolveCitationKbId(c)
  const docId = c.document_id
  if (kbId == null || docId == null) {
    return
  }
  closeCitationModal()
  void router.push({
    name: 'knowledge-document-detail',
    params: { kbId: String(kbId), docId: String(docId) },
    query: c.chunk_index != null ? { focus_chunk_index: String(c.chunk_index) } : {},
  })
}

function showAssistantCitationsFoot(message: ChatMessage): boolean {
  return (
    message.role === 'assistant' &&
    chatStore.activeConfiguration?.show_citations !== false &&
    Array.isArray(message.citations) &&
    message.citations.length > 0
  )
}

const showCitationsEnabled = computed(() => chatStore.activeConfiguration?.show_citations !== false)
const draftMessage = ref('')
const streamAbort = ref<AbortController | null>(null)
const kbs = ref<KnowledgeBase[]>([])
const embeddingModelsFlat = ref<ModelItem[]>([])
const embeddingSpaceDefault = ref<DefaultModelOption | null>(null)
const modelGroups = ref<ProviderModelsGroup[]>([])

const kbDropdownOpen = ref(false)

const flatChatModels = computed(() => modelGroups.value.flatMap((g) => g.models))

const sortedModelGroups = computed(() =>
  [...modelGroups.value]
    .map((g) => ({
      ...g,
      models: [...g.models].sort((a, b) => a.model_name.localeCompare(b.model_name, 'zh-CN')),
    }))
    .sort((a, b) => a.provider_name.localeCompare(b.provider_name, 'zh-CN')),
)

const MODEL_OPT_SEP = '\u001f'

function parseModelOptionValue(raw: string): ModelItem | undefined {
  if (!raw) {
    return undefined
  }
  if (/^\d+$/.test(raw)) {
    return flatChatModels.value.find((m) => m.id === Number(raw))
  }
  const i = raw.indexOf(MODEL_OPT_SEP)
  if (i === -1) {
    const sameName = flatChatModels.value.filter((m) => m.model_name === raw)
    return sameName.length === 1 ? sameName[0] : undefined
  }
  const code = raw.slice(0, i)
  const name = raw.slice(i + MODEL_OPT_SEP.length)
  const matches = flatChatModels.value.filter((m) => m.provider_code === code && m.model_name === name)
  return matches.length === 1 ? matches[0] : undefined
}

const headerModelMenuOpen = ref(false)
const sidePanelModelMenuOpen = ref(false)
const settingsDrawerOpen = ref(false)

watch(kbDropdownOpen, (v) => {
  if (v) {
    headerModelMenuOpen.value = false
    sidePanelModelMenuOpen.value = false
  }
})

/** 仅知识库多选下拉需抬升 Layout 溢出链；侧栏大模型列表改用 fixed 定位，不触碰会话区与主聊天区 */
const CHAT_SETTINGS_FLOATING_BODY_CLASS = 'chat-settings-floating-open'

const settingsFloatingOpen = computed(
  () =>
    settingsDrawerOpen.value &&
    Boolean(chatStore.activeSessionId) &&
    Boolean(chatStore.activeConversationId) &&
    kbDropdownOpen.value,
)

const panelModelPickerRef = ref<HTMLElement | null>(null)
const panelModelDropdownFloatingStyle = ref<Record<string, string>>({})

function layoutPanelModelDropdown() {
  if (!sidePanelModelMenuOpen.value) {
    return
  }
  const root = panelModelPickerRef.value
  const trigger = root?.querySelector('.panel-model-trigger') as HTMLElement | undefined
  if (!trigger) {
    return
  }
  const r = trigger.getBoundingClientRect()
  const gap = 6
  panelModelDropdownFloatingStyle.value = {
    position: 'fixed',
    left: `${Math.round(r.left)}px`,
    top: `${Math.round(r.bottom + gap)}px`,
    width: `${Math.round(r.width)}px`,
    zIndex: '2000',
  }
}

function bindPanelModelDropdownLayoutListeners() {
  layoutPanelModelDropdown()
  window.addEventListener('resize', layoutPanelModelDropdown)
  window.addEventListener('scroll', layoutPanelModelDropdown, true)
}

function unbindPanelModelDropdownLayoutListeners() {
  window.removeEventListener('resize', layoutPanelModelDropdown)
  window.removeEventListener('scroll', layoutPanelModelDropdown, true)
  panelModelDropdownFloatingStyle.value = {}
}

function openSettingsDrawer() {
  headerModelMenuOpen.value = false
  settingsDrawerOpen.value = true
}

function closeSettingsDrawer() {
  settingsDrawerOpen.value = false
  sidePanelModelMenuOpen.value = false
  kbDropdownOpen.value = false
}

function toggleSettingsPanel() {
  headerModelMenuOpen.value = false
  if (settingsDrawerOpen.value) {
    closeSettingsDrawer()
  } else {
    settingsDrawerOpen.value = true
  }
}

watch(settingsDrawerOpen, (open) => {
  if (open) {
    window.addEventListener('keydown', onSettingsDrawerEscape)
  } else {
    window.removeEventListener('keydown', onSettingsDrawerEscape)
  }
})

watch(
  settingsFloatingOpen,
  (open) => {
    if (typeof document === 'undefined') {
      return
    }
    document.body.classList.toggle(CHAT_SETTINGS_FLOATING_BODY_CLASS, open)
  },
  { immediate: true },
)

watch(sidePanelModelMenuOpen, async (open) => {
  if (typeof window === 'undefined') {
    return
  }
  if (open) {
    await nextTick()
    await nextTick()
    bindPanelModelDropdownLayoutListeners()
  } else {
    unbindPanelModelDropdownLayoutListeners()
  }
})

function onSettingsDrawerEscape(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    closeSettingsDrawer()
  }
}

const editGridChatId = ref<string | null>(null)
const editGridChatTitle = ref('')

const newChatTitle = ref('')
const createInputRef = ref<HTMLInputElement | null>(null)
const showCreateModal = ref(false)

const openMenuId = ref<string | null>(null)

const toggleMenu = (chatId: string) => {
  openMenuId.value = openMenuId.value === chatId ? null : chatId
}

const closeMenu = () => {
  openMenuId.value = null
}

const deleteModalOpen = ref(false)
const deleteTarget = ref<{ kind: 'conversation' | 'session'; id: string; title: string } | null>(null)
const deleteConfirmName = ref('')
const isDeleting = ref(false)

const showEmbedModal = ref(false)
const showAccessModal = ref(false)

const vFocus = {
  mounted: (el: HTMLElement) => el.focus()
}

const startEditGridTitle = (chat: any) => {
  closeMenu()
  editGridChatId.value = chat.id
  editGridChatTitle.value = chat.title
}

const saveGridTitle = async () => {
  if (editGridChatId.value && editGridChatTitle.value.trim()) {
    await chatStore.updateConversationTitle(editGridChatId.value, editGridChatTitle.value.trim())
    editGridChatId.value = null
  }
}

const cancelEditGridTitle = () => {
  editGridChatId.value = null
}

const openDeleteConversation = (chat: { id: string; title: string }) => {
  closeMenu()
  deleteTarget.value = { kind: 'conversation', id: chat.id, title: chat.title }
  deleteConfirmName.value = ''
  deleteModalOpen.value = true
}

const openDeleteSession = (session: { id: string; title: string }) => {
  deleteTarget.value = { kind: 'session', id: session.id, title: session.title }
  deleteConfirmName.value = ''
  deleteModalOpen.value = true
}

const closeDeleteModal = () => {
  if (isDeleting.value) return
  deleteModalOpen.value = false
  deleteTarget.value = null
  deleteConfirmName.value = ''
}

const canSubmitDelete = computed(() => {
  return (
    deleteTarget.value != null &&
    deleteConfirmName.value.trim() === deleteTarget.value.title.trim()
  )
})

const confirmDelete = async () => {
  if (!canSubmitDelete.value || !deleteTarget.value) return
  isDeleting.value = true
  try {
    if (deleteTarget.value.kind === 'conversation') {
      await chatStore.deleteConversation(deleteTarget.value.id)
    } else {
      await chatStore.deleteSession(deleteTarget.value.id)
    }
    closeDeleteModal()
  } catch (e) {
    console.error('Delete failed', e)
  } finally {
    isDeleting.value = false
  }
}

const activeMessages = computed(() => chatStore.messages)

const messageListRef = ref<HTMLElement | null>(null)
const showJumpToBottom = ref(false)
const streamingAssistantTempId = ref<string | null>(null)

function onMessageListScroll() {
  const el = messageListRef.value
  if (!el) {
    showJumpToBottom.value = false
    return
  }
  const threshold = 72
  showJumpToBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight > threshold
}

function scrollChatToBottom() {
  void nextTick(() => {
    const el = messageListRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
    onMessageListScroll()
  })
}

function isMessageStreaming(msg: ChatMessage) {
  return msg.role === 'assistant' && streamingAssistantTempId.value === msg.id
}

function copyMessageText(text: string) {
  void copyText(text)
}

function removeMessageLocal(id: string) {
  chatStore.removeMessageById(id)
}

function handleChatWsPayload(raw: unknown) {
  if (!raw || typeof raw !== 'object') {
    return
  }
  const d = raw as Record<string, unknown>

  if (d.type === 'error') {
    const tid = streamingAssistantTempId.value
    if (tid != null) {
      chatStore.appendMessageContent(tid, `\n\n【错误】${String((d as { message?: unknown }).message ?? '')}`)
    }
    streamingAssistantTempId.value = null
    chatStore.setGenerating(false)
    scrollChatToBottom()
    return
  }

  if (d.type === 'assistant_delta') {
    const chunk = String(d.content ?? '')
    const tid = streamingAssistantTempId.value
    if (tid != null && chunk) {
      chatStore.appendMessageContent(tid, chunk)
    }
    scrollChatToBottom()
    return
  }

  if (d.type === 'assistant_done') {
    const tid = streamingAssistantTempId.value
    const sid = chatStore.activeSessionId
    if (tid != null && sid != null) {
      const cites = normalizeCitations(d.citations)
      chatStore.replaceMessage(tid, {
        id: String(d.id),
        session_id: String(d.session_id ?? sid),
        role: 'assistant',
        content: String(d.content ?? ''),
        created_at: String(d.created_at ?? new Date().toISOString()),
        ...(cites ? { citations: cites } : {}),
      })
    }
    streamingAssistantTempId.value = null
    chatStore.setGenerating(false)
    scrollChatToBottom()
    return
  }

  if (d.role === 'assistant' && typeof d.content === 'string' && !('type' in d)) {
    const tid = streamingAssistantTempId.value
    const sid = chatStore.activeSessionId
    if (tid != null && sid != null) {
      chatStore.replaceMessage(tid, {
        id: tid,
        session_id: sid,
        role: 'assistant',
        content: d.content,
        created_at: new Date().toISOString(),
      })
    } else if (sid != null) {
      chatStore.addMessage({
        id: `legacy-${Date.now()}`,
        session_id: sid,
        role: 'assistant',
        content: d.content,
        created_at: new Date().toISOString(),
      })
    }
    streamingAssistantTempId.value = null
    chatStore.setGenerating(false)
    scrollChatToBottom()
  }
}

watch(
  () => chatStore.messages,
  () => {
    void nextTick(() => {
      const el = messageListRef.value
      if (!el) {
        return
      }
      const threshold = 100
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= threshold
      if (nearBottom) {
        el.scrollTop = el.scrollHeight
      }
      onMessageListScroll()
    })
  },
  { deep: true },
)
const activeConfig = computed(() => chatStore.activeConfiguration)

const chatKnowledgeBaseIds = computed({
  get(): number[] {
    return activeConfig.value?.knowledge_base_ids ?? []
  },
  set(ids: number[]) {
    updateConfig('knowledge_base_ids', ids)
  },
})

const RETRIEVAL_TOP_K_HELP =
  '各知识库仍按知识库检索设置召回候选；此处为合并排序后写入对话上下文的上限（1–50）。多库时分数统一排序后再截断。'

function clampChatRetrievalTopK(n: number): number {
  if (!Number.isFinite(n)) return 8
  return Math.min(50, Math.max(1, Math.round(n)))
}

const chatTopK = ref(8)

watch(
  () => activeConfig.value?.retrieval_top_k,
  (v) => {
    chatTopK.value = clampChatRetrievalTopK(v ?? 8)
  },
  { immediate: true },
)

const chatTopKSliderStyle = computed(() => {
  const min = 1
  const max = 50
  const raw = Number.isFinite(chatTopK.value) ? chatTopK.value : min
  const clamped = Math.min(Math.max(raw, min), max)
  const pct = ((clamped - min) / (max - min)) * 100
  return { '--progress': `${pct.toFixed(2)}%` } as Record<string, string>
})

/** 须与后端 `chat_service.DEFAULT_CHAT_SYSTEM_PROMPT` 保持一致 */
const DEFAULT_CHAT_SYSTEM_PROMPT =
  '你是一个智能助手，请总结知识库的内容来回答问题，请列举知识库中的数据详细回答。' +
  '当所有知识库内容都与问题无关时，你的回答必须包括「知识库中未找到您要的答案！」这句话。' +
  '回答需要考虑聊天历史。\n以下是知识库：\n{knowledge}\n以上是知识库。'

const systemPromptDraft = ref('')

watch(
  activeConfig,
  (c) => {
    const raw = c?.system_prompt
    systemPromptDraft.value = raw != null && String(raw).trim() !== '' ? String(raw) : DEFAULT_CHAT_SYSTEM_PROMPT
  },
  { immediate: true },
)

async function flushSystemPrompt() {
  const remote = activeConfig.value?.system_prompt ?? null
  const draftTrim = systemPromptDraft.value.trim()
  const defaultTrim = DEFAULT_CHAT_SYSTEM_PROMPT.trim()
  const nextPayload: string | null =
    draftTrim === '' || draftTrim === defaultTrim ? null : systemPromptDraft.value
  if (nextPayload === remote) {
    return
  }
  await chatStore.updateConfiguration({ system_prompt: nextPayload })
}

const headerModelTriggerLabel = computed(() => {
  const c = activeConfig.value
  const byId = c?.model_id != null ? flatChatModels.value.find((x) => x.id === c.model_id) : undefined
  const name = (byId?.model_name ?? c?.model_name)?.trim()
  if (name) {
    return name
  }
  return '选择模型'
})

const headerModelTriggerTitle = computed(() => {
  const c = activeConfig.value
  const byId = c?.model_id != null ? flatChatModels.value.find((x) => x.id === c.model_id) : undefined
  const m =
    byId ??
    flatChatModels.value.find(
      (x) =>
        x.model_name === c?.model_name?.trim() &&
        (!c?.model_provider || x.provider_code === c.model_provider),
    )
  if (!m && !c?.model_name?.trim()) {
    return ''
  }
  return m ? `${m.model_name} · ${m.provider_name}` : (c?.model_name?.trim() ?? '')
})

function toggleHeaderModelMenu() {
  if (!activeConfig.value) {
    return
  }
  if (!headerModelMenuOpen.value) {
    sidePanelModelMenuOpen.value = false
  }
  headerModelMenuOpen.value = !headerModelMenuOpen.value
}

function toggleSidePanelModelMenu() {
  if (!activeConfig.value) {
    return
  }
  if (!sidePanelModelMenuOpen.value) {
    headerModelMenuOpen.value = false
  }
  sidePanelModelMenuOpen.value = !sidePanelModelMenuOpen.value
}

function pickSidePanelModel(m: ModelItem) {
  updateConfig('model_name', m)
  sidePanelModelMenuOpen.value = false
}

function pickHeaderModel(m: ModelItem) {
  updateConfig('model_name', m)
  headerModelMenuOpen.value = false
  sidePanelModelMenuOpen.value = false
}

function isHeaderModelOptionCurrent(m: ModelItem): boolean {
  const c = activeConfig.value
  if (c?.model_id != null) {
    return c.model_id === m.id
  }
  if (!c?.model_name || c.model_name !== m.model_name) {
    return false
  }
  if (c.model_provider && c.model_provider !== m.provider_code) {
    return false
  }
  return true
}

const apiBaseUrl = computed(() => {
  const env = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (env != null && String(env).trim().length > 0) {
    return String(env).replace(/\/$/, '')
  }
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location
    return `${protocol}//${hostname}:8000`
  }
  return 'http://localhost:8000'
})

const chatPageUrl = computed(() =>
  typeof window !== 'undefined' ? `${window.location.origin}/chat` : '/chat',
)

const embedIframeSnippet = computed(
  () =>
    `<iframe src="${chatPageUrl.value}" title="知识对话" width="100%" height="720" frameborder="0" allow="clipboard-read; clipboard-write"></iframe>`,
)

const sseStreamUrlExample = computed(() => {
  const base = apiBaseUrl.value
  const sid = chatStore.activeSessionId
  if (sid != null) {
    return `POST ${base}/api/v1/chats/sessions/${sid}/stream`
  }
  return `POST ${base}/api/v1/chats/sessions/<session_id>/stream`
})

const sseBodyExample = `{
  "content": "用户本轮输入的纯文本"
}`

const sseEventsExample = `data: {"type":"assistant_delta","content":"片段"}

data: {"type":"assistant_done","id":"550e8400-e29b-41d4-a716-446655440000","session_id":"6ba7b810-9dad-11d1-80b4-00c04fd430c8","role":"assistant","content":"完整回复","created_at":"2026-01-01T00:00:00"}`

const sessionIdPlaceholder = computed(() =>
  chatStore.activeSessionId != null ? String(chatStore.activeSessionId) : '<session_id>',
)

const chatIdPlaceholder = computed(() =>
  chatStore.activeConversationId != null ? String(chatStore.activeConversationId) : '<chat_id>',
)

function copyText(text: string) {
  if (!text) return
  void navigator.clipboard.writeText(text).then(
    () => {
      alert('已复制到剪贴板')
    },
    () => {
      alert('复制失败，请手动选择文本')
    },
  )
}

const searchQuery = ref('')
const filteredConversations = computed(() => {
  if (!searchQuery.value) return chatStore.conversations
  const q = searchQuery.value.toLowerCase()
  return chatStore.conversations.filter((s) => s.title.toLowerCase().includes(q))
})

const addSession = async () => {
  exitSessionBatchMode()
  const n = chatStore.sessionsInConversation.length + 1
  await chatStore.createSessionInActiveConversation(`会话 ${n}`)
}

function pinsStorageKey(conversationId: string) {
  return `zs-rag-session-pins-${conversationId}`
}

function loadPinnedIds(conversationId: string): string[] {
  try {
    const raw = localStorage.getItem(pinsStorageKey(conversationId))
    if (!raw) return []
    const arr = JSON.parse(raw) as unknown
    if (!Array.isArray(arr)) return []
    return arr.map((x) => String(x)).filter((x) => x.length > 0)
  } catch {
    return []
  }
}

function savePinnedIds(conversationId: string, ids: string[]) {
  localStorage.setItem(pinsStorageKey(conversationId), JSON.stringify(ids))
}

const pinnedSessionIds = ref<string[]>([])
const sessionMenuOpenId = ref<string | null>(null)
const renamingSessionId = ref<string | null>(null)
const renameSessionDraft = ref('')
const renameSessionInputRef = ref<HTMLInputElement | null>(null)

const sessionBatchMode = ref(false)
const sessionBatchSelectedIds = ref<string[]>([])
const batchDeleteModalOpen = ref(false)
const isBatchDeleting = ref(false)

function normSessionId(id: number | string): string {
  return String(id)
}

const sessionBatchSelectedSet = computed(() => {
  const out = new Set<string>()
  for (const x of sessionBatchSelectedIds.value) {
    const s = String(x).trim()
    if (s) {
      out.add(s)
    }
  }
  return out
})

watch(
  () => chatStore.activeConversationId,
  (cid) => {
    pinnedSessionIds.value = cid != null ? loadPinnedIds(cid) : []
    sessionMenuOpenId.value = null
    renamingSessionId.value = null
    sessionBatchMode.value = false
    sessionBatchSelectedIds.value = []
    batchDeleteModalOpen.value = false
  },
  { immediate: true },
)

watch(
  () => chatStore.sessionsInConversation,
  (sessions) => {
    const cid = chatStore.activeConversationId
    if (cid == null) return
    const valid = new Set(sessions.map((s) => String(s.id)))
    const pruned = pinnedSessionIds.value.filter((id) => valid.has(String(id)))
    if (pruned.length !== pinnedSessionIds.value.length) {
      pinnedSessionIds.value = pruned
      savePinnedIds(cid, pruned)
    }
    const selPruned = [
      ...new Set(
        sessionBatchSelectedIds.value
          .map((id) => String(id).trim())
          .filter((id) => id.length > 0 && valid.has(id)),
      ),
    ]
    if (selPruned.length !== sessionBatchSelectedIds.value.length) {
      sessionBatchSelectedIds.value = selPruned
    }
  },
  { deep: true },
)

const sortedSessionsInConversation = computed(() => {
  const list = [...chatStore.sessionsInConversation]
  const pinned = pinnedSessionIds.value
  const pinnedSet = new Set(pinned)
  const pinnedRows: ChatSession[] = []
  for (const id of pinned) {
    const row = list.find((s) => s.id === id)
    if (row) {
      pinnedRows.push(row)
    }
  }
  const rest = list.filter((s) => !pinnedSet.has(s.id))
  rest.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
  return [...pinnedRows, ...rest]
})

function exitSessionBatchMode() {
  sessionBatchMode.value = false
  sessionBatchSelectedIds.value = []
  batchDeleteModalOpen.value = false
}

function toggleSessionBatchMode() {
  if (sessionBatchMode.value) {
    exitSessionBatchMode()
    return
  }
  sessionMenuOpenId.value = null
  renamingSessionId.value = null
  sessionBatchMode.value = true
  sessionBatchSelectedIds.value = []
}

function toggleSessionBatchSelection(id: number | string) {
  const key = normSessionId(id).trim()
  if (!key) {
    return
  }
  const next = new Set(sessionBatchSelectedIds.value.map((x) => String(x).trim()).filter(Boolean))
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  sessionBatchSelectedIds.value = [...next]
}

const sessionBatchAllSelected = computed(() => {
  const allIds = sortedSessionsInConversation.value
    .map((s) => String(s.id).trim())
    .filter((id) => id.length > 0)
  if (allIds.length === 0) {
    return false
  }
  const set = sessionBatchSelectedSet.value
  if (set.size !== allIds.length) {
    return false
  }
  return allIds.every((id) => set.has(id))
})

function toggleSelectAllSessionsForBatch() {
  const all = sortedSessionsInConversation.value
    .map((s) => String(s.id).trim())
    .filter((id) => id.length > 0)
  if (all.length === 0) {
    return
  }
  if (sessionBatchAllSelected.value) {
    sessionBatchSelectedIds.value = []
  } else {
    sessionBatchSelectedIds.value = [...all]
  }
}

function openBatchDeleteModal() {
  if (sessionBatchSelectedSet.value.size === 0) {
    return
  }
  batchDeleteModalOpen.value = true
}

function closeBatchDeleteModal() {
  if (isBatchDeleting.value) {
    return
  }
  batchDeleteModalOpen.value = false
}

async function confirmBatchDeleteSessions() {
  const ids = [...sessionBatchSelectedSet.value]
  if (ids.length === 0) {
    return
  }
  isBatchDeleting.value = true
  try {
    await chatStore.deleteSessionsBatch(ids)
    const cid = chatStore.activeConversationId
    if (cid != null) {
      const idSet = new Set(ids)
      pinnedSessionIds.value = pinnedSessionIds.value.filter((id) => !idSet.has(id))
      savePinnedIds(cid, pinnedSessionIds.value)
    }
    exitSessionBatchMode()
  } catch {
    alert('批量删除失败，请重试')
  } finally {
    isBatchDeleting.value = false
  }
}

function onSessionRowClick(session: ChatSession, e?: MouseEvent) {
  if (renamingSessionId.value === session.id) {
    return
  }
  if (sessionBatchMode.value) {
    const t = e?.target as HTMLElement | undefined
    if (t?.closest('input.session-line-check')) {
      return
    }
    toggleSessionBatchSelection(session.id)
    return
  }
  void chatStore.selectSession(session.id)
}

function toggleSessionMenu(id: string) {
  sessionMenuOpenId.value = sessionMenuOpenId.value === id ? null : id
}

function onPinSession(session: ChatSession) {
  const cid = chatStore.activeConversationId
  if (cid == null) {
    return
  }
  const id = session.id
  const next = [...pinnedSessionIds.value]
  const idx = next.indexOf(id)
  if (idx >= 0) {
    next.splice(idx, 1)
  }
  next.unshift(id)
  pinnedSessionIds.value = next
  savePinnedIds(cid, next)
  sessionMenuOpenId.value = null
}

async function onRenameSession(session: ChatSession) {
  sessionMenuOpenId.value = null
  renamingSessionId.value = session.id
  renameSessionDraft.value = session.title
  await nextTick()
  renameSessionInputRef.value?.focus()
}

async function saveRenameSession() {
  const id = renamingSessionId.value
  if (id == null) {
    return
  }
  const title = renameSessionDraft.value.trim()
  renamingSessionId.value = null
  const prev = chatStore.sessionsInConversation.find((s) => s.id === id)?.title
  if (title && prev !== title) {
    await chatStore.updateSessionTitle(id, title)
  }
}

function cancelRenameSession() {
  renamingSessionId.value = null
}

function onDeleteSessionFromMenu(session: ChatSession) {
  sessionMenuOpenId.value = null
  openDeleteSession(session)
}

function onGlobalClick() {
  closeMenu()
  sessionMenuOpenId.value = null
  headerModelMenuOpen.value = false
  sidePanelModelMenuOpen.value = false
  kbDropdownOpen.value = false
}

onMounted(async () => {
  window.addEventListener('click', onGlobalClick)
  await Promise.all([
    chatStore.fetchConversations(),
    fetchKbs(),
    fetchModels(),
    fetchEmbeddingModels(),
    fetchEmbeddingSpaceDefault(),
  ])
})

onBeforeUnmount(() => {
  window.removeEventListener('click', onGlobalClick)
  window.removeEventListener('keydown', onSettingsDrawerEscape)
  unbindPanelModelDropdownLayoutListeners()
  if (typeof document !== 'undefined') {
    document.body.classList.remove(CHAT_SETTINGS_FLOATING_BODY_CLASS)
  }
  streamAbort.value?.abort()
  streamAbort.value = null
})

const fetchKbs = async () => {
  try {
    kbs.value = await knowledgeBaseApi.list()
  } catch (e) {
    console.error('Failed to load knowledge bases', e)
  }
}

const fetchModels = async () => {
  try {
    const res = await modelApi.getModels({
      view: 'grouped',
      model_type: 'llm',
      is_enabled: true,
    })
    modelGroups.value = res as ProviderModelsGroup[]
  } catch (e) {
    console.error('Failed to load models', e)
  }
}

const fetchEmbeddingModels = async () => {
  try {
    const res = await modelApi.getModels({
      view: 'flat',
      model_type: 'embedding',
      is_enabled: true,
    })
    embeddingModelsFlat.value = (res as ModelItem[]) ?? []
  } catch (e) {
    console.error('Failed to load embedding models', e)
    embeddingModelsFlat.value = []
  }
}

const fetchEmbeddingSpaceDefault = async () => {
  try {
    const data = await defaultModelApi.getDefaults()
    embeddingSpaceDefault.value = data.embedding ?? null
  } catch (e) {
    console.error('Failed to load embedding defaults', e)
    embeddingSpaceDefault.value = null
  }
}

watch(() => chatStore.activeSessionId, (newId, oldId) => {
  headerModelMenuOpen.value = false
  sidePanelModelMenuOpen.value = false
  settingsDrawerOpen.value = false
  kbDropdownOpen.value = false
  streamingAssistantTempId.value = null
  chatStore.setGenerating(false)
  streamAbort.value?.abort()
  streamAbort.value = null
  showJumpToBottom.value = false
  void nextTick(() => onMessageListScroll())
})

const openCreateChatModal = async () => {
  newChatTitle.value = ''
  showCreateModal.value = true
  await nextTick()
  createInputRef.value?.focus()
}

async function onMultiModelCompareClick() {
  openSettingsDrawer()
  await nextTick()
  document.getElementById('chat-panel-model-config')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const handleCreate = async () => {
  const title = newChatTitle.value.trim()
  if (!title) {
    return
  }
  try {
    await chatStore.createConversation(title)
    showCreateModal.value = false
  } catch (e: unknown) {
    console.error('Create conversation failed', e)
    const ax = e as { response?: { data?: { message?: string } } }
    const msg = ax.response?.data?.message ?? (e instanceof Error ? e.message : null) ?? '创建对话失败，请检查网络或登录状态'
    alert(msg)
  }
}

/** 与「新建会话」默认标题 `会话 ${n}` 一致，仅在此模式下用首条提问自动改名 */
const DEFAULT_SESSION_TITLE_PATTERN = /^会话 \d+$/
const SESSION_TITLE_MAX_CHARS = 48

function sessionTitleFromFirstUserMessage(text: string): string {
  const oneLine = text.replace(/\s+/g, ' ').trim()
  if (!oneLine) {
    return ''
  }
  const chars = [...oneLine]
  if (chars.length <= SESSION_TITLE_MAX_CHARS) {
    return oneLine
  }
  return chars.slice(0, SESSION_TITLE_MAX_CHARS).join('') + '…'
}

const handleSend = async () => {
  const content = draftMessage.value.trim()
  if (!content || chatStore.isGenerating) {
    return
  }

  const sessionId = chatStore.activeSessionId
  if (sessionId == null) {
    return
  }

  const priorUserCount = chatStore.messages.filter((m) => m.role === 'user').length
  const sessionTitle = chatStore.activeSession?.title?.trim() ?? ''

  const sendTs = Date.now()
  const tempUserId = `local-user-${sendTs}`
  const tempAssistantId = `local-assistant-${sendTs}`

  chatStore.addMessage({
    id: tempUserId,
    session_id: sessionId,
    role: 'user',
    content,
    created_at: new Date().toISOString(),
  })
  chatStore.addMessage({
    id: tempAssistantId,
    session_id: sessionId,
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString(),
  })
  streamingAssistantTempId.value = tempAssistantId
  chatStore.setGenerating(true)

  draftMessage.value = ''

  if (priorUserCount === 0 && sessionTitle && DEFAULT_SESSION_TITLE_PATTERN.test(sessionTitle)) {
    const nextTitle = sessionTitleFromFirstUserMessage(content)
    if (nextTitle) {
      await chatStore.updateSessionTitle(sessionId, nextTitle)
    }
  }

  scrollChatToBottom()

  streamAbort.value?.abort()
  const ac = new AbortController()
  streamAbort.value = ac

  try {
    await streamChatCompletion(sessionId, content, handleChatWsPayload, { signal: ac.signal })
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      streamingAssistantTempId.value = null
      chatStore.setGenerating(false)
      return
    }
    const tid = streamingAssistantTempId.value
    const msg = e instanceof Error ? e.message : '请求失败'
    if (tid != null) {
      chatStore.appendMessageContent(tid, `\n\n【请求失败】${msg}`)
    }
    streamingAssistantTempId.value = null
    chatStore.setGenerating(false)
  } finally {
    if (streamAbort.value === ac) {
      streamAbort.value = null
    }
  }
  scrollChatToBottom()
}

const updateConfig = (key: string, value: any) => {
  if (activeConfig.value) {
    if (key === 'model_name') {
      let selected: ModelItem | undefined
      if (value != null && typeof value === 'object' && 'provider_code' in value && 'model_name' in value) {
        selected = value as ModelItem
      } else if (typeof value === 'string') {
        selected = parseModelOptionValue(value)
      }
      if (selected) {
        chatStore.updateConfiguration({
          model_id: selected.id,
          model_name: selected.model_name,
          model_provider: selected.provider_code,
        })
      }
    } else {
      chatStore.updateConfiguration({ [key]: value })
    }
  }
}

function onChatTopKCommit() {
  if (!activeConfig.value) return
  const v = clampChatRetrievalTopK(chatTopK.value)
  chatTopK.value = v
  const prev = clampChatRetrievalTopK(activeConfig.value.retrieval_top_k ?? 8)
  if (v !== prev) {
    updateConfig('retrieval_top_k', v)
  }
}

</script>

<style scoped>
.rail-back-nav {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  flex-wrap: wrap;
  padding: 8px 0 12px;
  margin: 0 0 10px;
  border-bottom: 1px solid var(--border-color);
}

.rail-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: none;
  border-radius: 10px;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.rail-back-btn:hover {
  background: rgba(37, 99, 235, 0.18);
}

.rail-bc-sep {
  color: var(--text-tertiary);
  font-size: 0.9rem;
  user-select: none;
}

.rail-bc-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-rail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 0 0 10px;
  padding: 8px 0 12px;
  border-bottom: 1px solid var(--border-color);
}

.session-rail-title {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
}

.session-rail-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.btn-session-batch {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
}

.btn-session-batch:hover,
.btn-session-batch.active {
  border-color: var(--brand-primary);
  color: var(--brand-primary);
  background: var(--brand-primary-light);
}

.session-batch-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  background: var(--bg-tertiary);
  font-size: 0.8125rem;
  color: var(--text-secondary);
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

.btn-text-inline:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-text-inline.danger {
  color: var(--danger-color);
}

.session-line-check {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  margin: 0;
  accent-color: var(--brand-primary);
  cursor: pointer;
  appearance: auto;
  -webkit-appearance: auto;
}

.btn-new-session {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 0.8125rem;
  font-weight: 600;
  border-radius: 8px;
  border: none;
  background: var(--brand-primary);
  color: #fff;
  cursor: pointer;
  flex-shrink: 0;
  white-space: nowrap;
}

.btn-new-session:hover {
  filter: brightness(1.05);
}

.session-lines {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-line {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 8px 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.session-line:hover,
.session-line.active,
.session-line.batch-selected {
  background: var(--bg-tertiary);
}

.session-line.active,
.session-line.batch-selected {
  box-shadow: inset 0 0 0 1px var(--border-color);
}

.session-line-title {
  flex: 1;
  min-width: 0;
  font-size: 0.9rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-line-input {
  flex: 1;
  min-width: 0;
  margin: 0;
  padding: 4px 8px;
  font-size: 0.9rem;
}

.session-line-actions {
  position: relative;
  flex-shrink: 0;
}

.session-line-more {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.12s ease, background 0.12s ease;
}

.session-line:hover .session-line-more,
.session-line.menu-open .session-line-more,
.session-line.active .session-line-more {
  opacity: 1;
}

.session-line-more:hover {
  background: rgba(15, 23, 42, 0.06);
  color: var(--text-primary);
}

.session-line-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  min-width: 148px;
  padding: 6px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
  z-index: 20;
  display: grid;
  gap: 2px;
}

.session-line-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
  text-align: left;
}

.session-line-menu-item:hover {
  background: var(--bg-tertiary);
}

.session-line-menu-item.danger {
  color: var(--danger-color);
}

.chat-side-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.btn-embed-site {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  border: none;
  border-radius: 12px;
  background: #111827;
  color: #f9fafb;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.btn-embed-site:hover {
  opacity: 0.92;
}

.btn-access-api {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-weight: 600;
  cursor: pointer;
}

.btn-access-api:hover {
  border-color: var(--brand-primary);
  color: var(--brand-primary);
}

.modal-wide {
  max-width: 640px;
  max-height: min(90vh, 720px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.access-modal-body {
  overflow-y: auto;
  flex: 1;
  padding-right: 4px;
}

.access-intro {
  margin: 0 0 16px;
  color: var(--text-secondary);
  line-height: 1.6;
  font-size: 0.9rem;
}

.access-block {
  margin-bottom: 18px;
}

.access-block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.access-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}

.btn-copy {
  font-size: 0.82rem;
  padding: 4px 8px !important;
}

.access-pre {
  margin: 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  font-size: 0.78rem;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: var(--text-primary);
}

.access-section-title {
  margin: 20px 0 8px;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-primary);
}

.access-section-title:first-of-type {
  margin-top: 0;
}

.access-muted {
  margin: 0 0 8px;
  font-size: 0.84rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.access-list {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
  font-size: 0.84rem;
  line-height: 1.65;
}

.access-list code {
  font-size: 0.76rem;
  word-break: break-all;
}

.page-shell.chat-view.page-shell--kb-dropdown-open {
  overflow: visible;
}

.page-shell.chat-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
  flex: 1 1 0%;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
}

.chat-layout.chat-layout--kb-dropdown-open {
  overflow: visible;
}

.chat-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 24px;
  align-items: stretch;
  flex: 1 1 0%;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
  transition: grid-template-columns 0.22s ease;
}

.chat-layout.chat-layout--settings-open {
  grid-template-columns: 320px minmax(0, 1fr) minmax(300px, 380px);
}

.chat-layout > .conversation-rail,
.chat-layout > .chat-main,
.chat-layout > .chat-settings-panel {
  min-width: 0;
  min-height: 0;
}

.chat-detail-view.chat-detail-view--kb-dropdown-open {
  overflow: visible;
}

.chat-detail-view {
  flex: 1 1 0%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.conversation-rail {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
  max-height: 100%;
  overflow: hidden;
}

.conversation-rail .session-lines {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.chat-main,
.side-panel {
  display: grid;
  gap: 18px;
  min-height: 0;
}

.message-list,
.reference-list,
.guideline-list {
  display: grid;
  gap: 14px;
}

.reference-item,
.guideline-item {
  display: grid;
  gap: 10px;
  width: 100%;
  padding: 16px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: var(--bg-tertiary);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}

.reference-item strong,
.chat-main-header h3 {
  color: var(--text-primary);
}

.reference-item p,
.chat-main-header p,
.guideline-item span {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.65;
}

.chat-main {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  align-self: stretch;
  overflow: hidden;
  gap: 18px;
}

.chat-main-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0 14px;
  border-bottom: 1px solid var(--border-color);
}

.chat-session-line {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.45;
  min-width: 0;
}

.chat-header-meta {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.btn-multi-model-compare {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid rgba(37, 99, 235, 0.35);
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    filter 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease;
}

.btn-multi-model-compare:hover {
  filter: brightness(0.98);
  border-color: var(--brand-primary);
}

.btn-chat-settings {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    filter 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}

.btn-chat-settings:hover {
  border-color: var(--border-strong);
  color: var(--text-primary);
  background: var(--bg-tertiary);
}

.header-model-picker {
  position: relative;
  flex-shrink: 0;
}

.header-model-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: min(280px, 52vw);
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary, var(--bg-tertiary));
  color: var(--text-primary);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.header-model-trigger:hover:not(:disabled) {
  border-color: rgba(100, 116, 139, 0.45);
  background: var(--bg-primary);
}

.header-model-trigger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.header-model-label {
  flex: 1;
  min-width: 0;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
  font-weight: 600;
}

.header-model-chevron {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform 0.15s ease;
}

.header-model-chevron.is-open {
  transform: rotate(180deg);
}

.header-model-dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  z-index: 40;
  min-width: min(320px, 92vw);
  max-height: 280px;
  overflow-y: auto;
  padding: 6px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
}

.header-model-group + .header-model-group {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border-color);
}

.header-model-group-title {
  padding: 4px 10px 8px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.header-model-option {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  transition: background 0.12s ease;
}

.header-model-option:hover {
  background: var(--brand-primary-light);
}

.header-model-option.is-current {
  background: rgba(37, 99, 235, 0.1);
}

.header-model-option-name {
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.3;
}

.header-model-empty {
  padding: 12px;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.panel-model-field {
  margin-bottom: 0;
}

.panel-model-picker {
  position: relative;
  width: 100%;
}

.panel-model-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  max-width: 100%;
  padding: 8px 12px;
  margin: 0;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary, var(--bg-tertiary));
  color: var(--text-primary);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
  box-sizing: border-box;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.panel-model-trigger:not(.panel-model-trigger--disabled):hover {
  border-color: rgba(100, 116, 139, 0.45);
  background: var(--bg-primary);
}

.panel-model-trigger--disabled {
  opacity: 0.55;
  cursor: not-allowed;
  pointer-events: none;
}

.panel-model-trigger-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.panel-model-dropdown {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 6px);
  z-index: 45;
}

.panel-model-dropdown.panel-model-dropdown--fixed {
  position: fixed;
  left: auto;
  right: auto;
  top: auto;
  margin: 0;
  max-width: min(100vw - 24px, 420px);
}

.panel-model-dropdown .panel-model-list {
  margin-top: 0;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.14);
}

.panel-model-list {
  position: static;
  width: 100%;
  max-height: 280px;
  overflow-y: auto;
  margin-top: 6px;
  padding: 8px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.6);
}

.panel-model-list .header-model-group:first-child {
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}

.panel-model-list .header-model-group + .header-model-group {
  margin-top: 8px;
  padding-top: 10px;
  border-top: 1px solid rgba(148, 163, 184, 0.35);
}

.panel-model-list .header-model-option-name {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-primary);
}

.panel-model-list .header-model-option {
  border-radius: 10px;
  margin-bottom: 2px;
}

.panel-model-list .header-model-option.is-current {
  background: var(--brand-primary-light);
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.2);
}

.panel-model-list .header-model-option:hover:not(.is-current) {
  background: var(--bg-tertiary);
}

.chat-main-body {
  position: relative;
  flex: 1 1 0%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.message-list {
  flex: 1 1 0%;
  display: flex;
  flex-direction: column;
  gap: 28px;
  align-content: start;
  overflow-x: hidden;
  overflow-y: auto;
  min-height: 0;
  padding: 8px 4px 16px;
  overscroll-behavior: contain;
}

.chat-jump-bottom {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 0.85rem;
  font-weight: 600;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.chat-jump-bottom:hover {
  background: var(--bg-tertiary);
  border-color: rgba(37, 99, 235, 0.35);
  color: var(--brand-primary);
}

.msg-row--assistant {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  max-width: 100%;
}

.msg-row--user {
  display: flex;
  justify-content: flex-end;
}

.msg-avatar {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.msg-avatar--assistant {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.msg-avatar--user {
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  border: 1px solid rgba(37, 99, 235, 0.2);
}

.msg-stack--assistant {
  flex: 1;
  min-width: 0;
  max-width: min(720px, 100%);
}

.msg-stack--user {
  max-width: min(680px, 92%);
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.msg-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 6px;
}

.msg-toolbar--user {
  justify-content: flex-end;
}

.msg-tool {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.msg-tool:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.msg-tool.is-active {
  color: var(--brand-primary);
  background: var(--brand-primary-light);
}

.msg-text--assistant {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.75;
  font-size: 0.95rem;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-text--assistant.is-streaming::after {
  content: '';
  display: inline-block;
  width: 6px;
  height: 1em;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: var(--brand-primary);
  border-radius: 2px;
  animation: chat-stream-caret 0.9s ease-in-out infinite;
}

@keyframes chat-stream-caret {
  0%,
  100% {
    opacity: 0.2;
  }
  50% {
    opacity: 1;
  }
}

.msg-bubble-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.msg-bubble {
  padding: 12px 16px;
  border-radius: 16px 16px 6px 16px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  line-height: 1.65;
  font-size: 0.95rem;
  white-space: pre-wrap;
  word-break: break-word;
  max-width: 100%;
}

.citation-list {
  display: grid;
  gap: 10px;
}

.citation-card,
.reference-item {
  display: flex;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-secondary);
}

.reference-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  flex-shrink: 0;
}

.composer {
  flex-shrink: 0;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.composer-input-wrap {
  position: relative;
  display: block;
}

.composer-textarea {
  display: block;
  width: 100%;
  box-sizing: border-box;
  padding: 12px 118px 52px 14px;
  min-height: 120px;
  resize: vertical;
}

.composer-send {
  position: absolute;
  right: 10px;
  bottom: 10px;
  z-index: 1;
  flex-shrink: 0;
  padding: 8px 14px;
  min-height: 38px;
  border-radius: 12px;
}

.compact-heading {
  margin-bottom: 12px;
}

.chat-settings-panel {
  align-self: stretch;
  max-height: 100%;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 0 18px 22px;
  box-sizing: border-box;
}

.chat-settings-panel.chat-settings-panel--kb-open {
  overflow: visible;
  z-index: 12;
}

.chat-settings-panel:has(.kb-select--open) {
  overflow: visible;
  z-index: 8;
}

.chat-settings-toolbar {
  position: sticky;
  top: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 -18px 14px;
  padding: 10px 18px 14px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
}

.chat-settings-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text-primary);
}

.btn-settings-close {
  flex-shrink: 0;
}

.chat-retrieval-topk-field {
  margin-top: 14px;
}

.chat-topk-field-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
  color: var(--text-primary);
  font-weight: 600;
  font-size: 0.9rem;
}

.chat-topk-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-tertiary);
  border: 1px solid var(--border-color);
  cursor: help;
  vertical-align: middle;
}

.chat-topk-slider-row {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.chat-topk-number-input {
  flex: 0 0 auto;
  width: 92px;
  min-width: 0;
  padding: 4px 8px;
  text-align: left;
}

.chat-topk-progress-range {
  --progress: 0%;
  --progress-color: var(--brand-primary, #3b82f6);
  --progress-track: rgba(59, 130, 246, 0.12);
  -webkit-appearance: none;
  appearance: none;
  flex: 1 1 auto;
  min-width: 0;
  height: 6px;
  margin: 0;
  border-radius: 999px;
  outline: none;
  cursor: pointer;
  background: linear-gradient(
    to right,
    var(--progress-color) 0%,
    var(--progress-color) var(--progress),
    var(--progress-track) var(--progress),
    var(--progress-track) 100%
  );
}

.chat-topk-progress-range::-webkit-slider-runnable-track {
  height: 6px;
  border-radius: 999px;
  background: transparent;
}

.chat-topk-progress-range::-moz-range-track {
  height: 6px;
  border-radius: 999px;
  background: transparent;
}

.chat-topk-progress-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  margin-top: -6px;
  border-radius: 50%;
  background: #ffffff;
  border: 1px solid var(--border-strong, #d1d5db);
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.2);
  cursor: pointer;
  transition: transform 0.15s ease;
}

.chat-topk-progress-range::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #ffffff;
  border: 1px solid var(--border-strong, #d1d5db);
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.2);
  cursor: pointer;
  transition: transform 0.15s ease;
}

.chat-topk-progress-range::-webkit-slider-thumb:hover,
.chat-topk-progress-range:focus::-webkit-slider-thumb {
  transform: scale(1.08);
}

.chat-topk-progress-range::-moz-range-thumb:hover,
.chat-topk-progress-range:focus::-moz-range-thumb {
  transform: scale(1.08);
}

.chat-citation-toggle-field {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--border-color);
}

.chat-citation-toggle-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.chat-citation-toggle-head .field-label {
  margin-bottom: 0;
}

.chat-citation-help {
  display: inline-flex;
  color: var(--text-tertiary);
  cursor: help;
}

.chat-switch {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  position: relative;
}

.chat-switch input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.chat-switch-track {
  width: 44px;
  height: 26px;
  border-radius: 999px;
  background: var(--border-color);
  position: relative;
  transition: background 0.2s ease;
}

.chat-switch-track::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 4px;
  width: 20px;
  height: 20px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.2);
  transition: transform 0.2s ease;
}

.chat-switch input:checked + .chat-switch-track {
  background: #14b8a6;
}

.chat-switch input:checked + .chat-switch-track::after {
  transform: translateX(16px);
}

.chat-switch input:focus-visible + .chat-switch-track {
  outline: 2px solid var(--brand-primary);
  outline-offset: 2px;
}

.msg-citation-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.35em;
  margin: 0 1px;
  padding: 0 6px;
  border-radius: 6px;
  font-size: 0.72rem;
  font-weight: 700;
  line-height: 1.5;
  vertical-align: 0.15em;
  background: rgba(100, 116, 139, 0.16);
  color: var(--text-secondary);
  border: 1px solid rgba(100, 116, 139, 0.35);
  cursor: pointer;
}

.msg-citation-badge:hover {
  background: rgba(37, 99, 235, 0.12);
  border-color: rgba(37, 99, 235, 0.35);
  color: var(--brand-primary);
}

.msg-citation-badge:focus-visible {
  outline: 2px solid var(--brand-primary);
  outline-offset: 2px;
}

.msg-citations-block {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.msg-citations-title {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-tertiary);
  letter-spacing: 0.06em;
  margin-bottom: 8px;
}

.msg-citations-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}

.msg-citations-list li {
  margin: 0;
}

.msg-citation-row-btn {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  width: 100%;
  margin: 0;
  padding: 8px 10px;
  text-align: left;
  font-size: 0.86rem;
  line-height: 1.45;
  border: 1px solid transparent;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.35);
  color: inherit;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.msg-citation-row-btn:hover {
  background: rgba(37, 99, 235, 0.08);
  border-color: rgba(37, 99, 235, 0.2);
}

.msg-citation-row-btn:focus-visible {
  outline: 2px solid var(--brand-primary);
  outline-offset: 2px;
}

.msg-citation-ref {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 700;
  background: rgba(20, 184, 166, 0.15);
  color: #0d9488;
}

.msg-citation-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  color: var(--text-primary);
}

.msg-citation-doc {
  font-weight: 600;
}

.msg-citation-page,
.msg-citation-chunk {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.citation-chunk-modal {
  max-width: 640px;
  width: min(96vw, 640px);
}

.citation-chunk-modal-base {
  max-height: min(58vh, 520px);
  overflow: auto;
}

.citation-chunk-modal-meta {
  margin: 0 0 12px;
  font-size: 0.88rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.citation-chunk-modal-meta strong {
  color: var(--text-primary);
}

.citation-chunk-modal-err {
  margin: 0;
}

.citation-chunk-modal-body {
  margin: 0;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  font-family: inherit;
  font-size: 0.84rem;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-primary);
}

.citation-chunk-modal-footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 12px;
}

.loading-inline {
  padding: 16px 0;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 0.88rem;
}

.kb-settings-loading {
  margin-top: 8px;
  font-size: 0.9rem;
  color: var(--text-tertiary);
}

.chat-settings-panel .section-heading.compact-heading > h4:only-child {
  margin: 0;
}

.system-prompt-field {
  margin-top: 4px;
}

.system-prompt-textarea {
  min-height: 180px;
  font-size: 0.9rem;
  line-height: 1.55;
  resize: vertical;
}

.chat-grid-view {
  display: flex;
  flex-direction: column;
  gap: 32px;
  padding: 16px 24px;
  flex: 1;
  min-height: 0;
}

.chat-grid-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.chat-grid-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-grid-title h2 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
}

.chat-grid-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 4px 12px;
  width: 240px;
}

.search-input {
  border: none;
  background: transparent;
  padding: 4px 0;
  width: 100%;
  font-size: 0.9rem;
}

.search-input:focus {
  outline: none;
  box-shadow: none;
}

.chat-cards-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  align-content: start;
}

.chat-grid-card {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px 20px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-tertiary);
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  position: relative;
}

.chat-grid-card:hover {
  border-color: var(--brand-primary);
  box-shadow: var(--card-shadow-sm);
}

.chat-grid-card-menu-container {
  position: relative;
  display: flex;
  align-items: center;
  align-self: flex-start;
}

.tile-menu-trigger {
  width: 30px;
  height: 30px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-bottom: 8px;
  transition: all 0.2s ease;
}

.tile-menu-trigger:hover, .chat-grid-card-menu-container:has(.tile-menu) .tile-menu-trigger {
  border-color: var(--border-color);
  background: var(--bg-secondary);
}

.tile-menu {
  position: absolute;
  top: 34px;
  right: 0;
  z-index: 5;
  min-width: 120px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-secondary);
  box-shadow: var(--card-shadow-sm);
  padding: 6px;
  display: grid;
  gap: 4px;
}

.tile-menu-item {
  border: none;
  background: transparent;
  text-align: left;
  padding: 8px 10px;
  border-radius: 8px;
  color: var(--text-primary);
  cursor: pointer;
  font-size: 0.9rem;
}

.tile-menu-item:hover:not(:disabled) {
  background: var(--bg-tertiary);
}

.tile-menu-item.danger {
  color: var(--danger-color);
}

.chat-grid-card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
  flex-shrink: 0;
}

.chat-grid-card-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0; /* allows text truncation */
}

.chat-grid-card-content h4 {
  margin: 0;
  font-size: 1rem;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-all;
  line-height: 1.4;
}

.chat-grid-card-content span {
  font-size: 0.85rem;
  color: var(--text-tertiary);
  margin-top: 4px;
}

@media (max-width: 1360px) {
  .chat-layout {
    grid-template-columns: 280px minmax(0, 1fr);
  }

  .chat-layout.chat-layout--settings-open {
    grid-template-columns: 280px minmax(0, 1fr) minmax(280px, 340px);
  }
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-primary);
  border-radius: 12px;
  padding: 24px;
  width: 100%;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.2rem;
}

.modal-body .field-label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: var(--text-primary);
}

@media (max-width: 960px) {
  .chat-layout {
    grid-template-columns: 1fr;
  }

  .chat-layout.chat-layout--settings-open {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr) auto;
  }

  .chat-layout.chat-layout--settings-open .conversation-rail {
    order: 0;
  }

  .chat-layout.chat-layout--settings-open .chat-main {
    order: 1;
    min-height: min(52vh, 480px);
  }

  .chat-layout.chat-layout--settings-open .chat-settings-panel {
    order: 2;
    max-height: min(42vh, 380px);
  }

  .chat-main-header,
  .msg-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>