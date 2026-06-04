<template>
  <Layout>
    <div
      class="page-shell chat-view"
      :class="{
        'page-shell--kb-dropdown-open': settingsFloatingOpen,
        'page-shell--embed-panel': isEmbedPanelMode,
      }"
    >
      <!-- Grid View：对话列表（嵌入精简模式不展示） -->
      <div v-if="!chatStore.activeConversationId && !isEmbedPanelMode" class="chat-grid-view">
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

      <!-- 嵌入精简模式：未选中对话时占位（避免露出完整聊天首页） -->
      <div v-else-if="!chatStore.activeConversationId && isEmbedPanelMode" class="chat-embed-panel-fallback">
        <EmptyState
          title="暂无法展示嵌入对话"
          description="请使用带 conversation_id 的嵌入链接，并确认嵌入密钥仍有效。"
          icon="chat"
        />
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
            'chat-layout--embed-panel': isEmbedPanelMode,
          }"
        >
          <aside v-if="!isEmbedPanelMode" class="surface-card conversation-rail">
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
            <p v-if="memoryHintVisible" class="chat-memory-hint" role="status">
              {{ memoryHintText }}
            </p>
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
                            <span v-if="c.source === 'graph'" class="msg-citation-graph-badge">
                              <AppIcon name="graph" :size="11" />
                              图检索
                            </span>
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

            <div v-if="showSuggestedQuestionsBlock" class="chat-suggest-questions">
              <div class="chat-suggest-questions-divider">
                <span>试着问问</span>
              </div>
              <div class="chat-suggest-questions-chips">
                <button
                  v-for="(q, qi) in displayedSuggestedQuestions"
                  :key="`${qi}-${q}`"
                  type="button"
                  class="chat-suggest-question-chip"
                  @click="applySuggestedQuestion(q)"
                >
                  {{ q }}
                </button>
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
            :description="
              isEmbedPanelMode
                ? '嵌入链接无效或会话尚未加载，请刷新页面或联系管理员检查 conversation_id。'
                : '请从左侧点击「聊天」返回首页，再创建或进入对话。'
            "
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
            <button v-if="!isEmbedPanelMode" type="button" class="btn btn-embed-site" @click="showEmbedModal = true">
              <AppIcon name="send" :size="16" />
              嵌入网站
            </button>
            <button type="button" class="btn btn-access-api" @click="openApiAccessModal">
              API 接入
            </button>
          </div>
          <section id="chat-panel-model-config" class="surface-card">
            <div class="section-heading compact-heading">
              <div>
                <h4>模型配置</h4>
                <p class="section-subtext">本对话下所有会话共用此配置</p>
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

              <div v-if="activeConfig" class="chat-model-params">
                <div class="chat-model-params-heading">参数</div>

                <div class="chat-model-param-row" :class="{ 'is-disabled': activeConfig.temperature_enabled !== true }">
                  <label class="chat-switch chat-model-param-switch">
                    <input
                      type="checkbox"
                      role="switch"
                      :checked="activeConfig.temperature_enabled === true"
                      @change="onTemperatureEnabledChange(($event.target as HTMLInputElement).checked)"
                    />
                    <span class="chat-switch-track" aria-hidden="true" />
                  </label>
                  <span class="chat-model-param-label chat-field-label-block">
                    Temperature
                    <span class="chat-field-hint-wrap" tabindex="0" role="button" aria-label="Temperature help">
                      <span class="chat-topk-help">?</span>
                    </span>
                    <span class="chat-field-hint-tooltip" role="tooltip">{{ TEMPERATURE_HELP }}</span>
                  </span>
                  <input
                    v-model.number="chatTemperature"
                    class="chat-model-param-range"
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    :style="chatTemperatureSliderStyle"
                    :disabled="activeConfig.temperature_enabled !== true"
                    aria-label="Temperature slider"
                    @change="onTemperatureCommit"
                  />
                  <input
                    v-model.number="chatTemperature"
                    class="input chat-model-param-number"
                    type="number"
                    min="0"
                    max="2"
                    step="0.1"
                    :disabled="activeConfig.temperature_enabled !== true"
                    aria-label="Temperature"
                    @change="onTemperatureCommit"
                    @blur="onTemperatureCommit"
                  />
                </div>

                <div class="chat-model-param-row" :class="{ 'is-disabled': activeConfig.max_tokens_enabled !== true }">
                  <label class="chat-switch chat-model-param-switch">
                    <input
                      type="checkbox"
                      role="switch"
                      :checked="activeConfig.max_tokens_enabled === true"
                      @change="onMaxTokensEnabledChange(($event.target as HTMLInputElement).checked)"
                    />
                    <span class="chat-switch-track" aria-hidden="true" />
                  </label>
                  <span class="chat-model-param-label chat-field-label-block">
                    Max Tokens
                    <span class="chat-field-hint-wrap" tabindex="0" role="button" aria-label="Max Tokens help">
                      <span class="chat-topk-help">?</span>
                    </span>
                    <span class="chat-field-hint-tooltip" role="tooltip">{{ MAX_TOKENS_HELP }}</span>
                  </span>
                  <input
                    v-model.number="chatMaxTokens"
                    class="chat-model-param-range"
                    type="range"
                    min="100"
                    :max="chatMaxTokensSliderMax"
                    step="100"
                    :style="chatMaxTokensSliderStyle"
                    :disabled="activeConfig.max_tokens_enabled !== true"
                    aria-label="Max Tokens slider"
                    @change="onMaxTokensCommit"
                  />
                  <input
                    v-model.number="chatMaxTokens"
                    class="input chat-model-param-number"
                    type="number"
                    min="100"
                    :max="chatMaxTokensSliderMax"
                    step="100"
                    :disabled="activeConfig.max_tokens_enabled !== true"
                    aria-label="Max Tokens"
                    @change="onMaxTokensCommit"
                    @blur="onMaxTokensCommit"
                  />
                </div>

                <div class="chat-model-param-row" :class="{ 'is-disabled': activeConfig.top_p_enabled !== true }">
                  <label class="chat-switch chat-model-param-switch">
                    <input
                      type="checkbox"
                      role="switch"
                      :checked="activeConfig.top_p_enabled === true"
                      @change="onTopPEnabledChange(($event.target as HTMLInputElement).checked)"
                    />
                    <span class="chat-switch-track" aria-hidden="true" />
                  </label>
                  <span class="chat-model-param-label chat-field-label-block">
                    Top P
                    <span class="chat-field-hint-wrap" tabindex="0" role="button" aria-label="Top P 说明">
                      <span class="chat-topk-help">?</span>
                    </span>
                    <span class="chat-field-hint-tooltip" role="tooltip">{{ TOP_P_HELP }}</span>
                  </span>
                  <input
                    v-model.number="chatTopP"
                    class="chat-model-param-range"
                    type="range"
                    min="0.05"
                    max="1"
                    step="0.05"
                    :style="chatTopPSliderStyle"
                    :disabled="activeConfig.top_p_enabled !== true"
                    aria-label="Top P 滑动条"
                    @change="onTopPCommit"
                  />
                  <input
                    v-model.number="chatTopP"
                    class="input chat-model-param-number"
                    type="number"
                    min="0.05"
                    max="1"
                    step="0.05"
                    :disabled="activeConfig.top_p_enabled !== true"
                    aria-label="Top P"
                    @change="onTopPCommit"
                    @blur="onTopPCommit"
                  />
                </div>
              </div>
            </div>
          </section>

          <section v-if="activeConfig" class="surface-card chat-system-prompt-card">
            <div class="section-heading compact-heading">
              <h4 class="chat-field-label-block">
                系统提示词
                <span class="chat-field-hint-wrap" tabindex="0" role="button" aria-label="系统提示词说明">
                  <span class="chat-topk-help">?</span>
                </span>
                <span class="chat-field-hint-tooltip" role="tooltip">{{ SYSTEM_PROMPT_HELP }}</span>
              </h4>
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
              <h4>知识库检索</h4>
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
              <span class="chat-topk-field-label chat-field-label-block">
                Top K
                <span
                  class="chat-field-hint-wrap"
                  tabindex="0"
                  role="button"
                  aria-label="Top K 说明"
                >
                  <span class="chat-topk-help">?</span>
                </span>
                <span class="chat-field-hint-tooltip" role="tooltip">{{ RETRIEVAL_TOP_K_HELP }}</span>
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

            <div v-if="activeConfig && hasLightragKbSelected" class="field chat-lightrag-mode-field">
              <span class="field-label chat-field-label-block">
                图检索模式（LightRAG）
                <span class="chat-field-hint-wrap" tabindex="0" role="button" aria-label="图检索模式说明">
                  <span class="chat-topk-help">?</span>
                </span>
                <span class="chat-field-hint-tooltip" role="tooltip">{{ LIGHTRAG_MODE_HELP }}</span>
              </span>
              <select
                class="select"
                :value="activeConfig.lightrag_query_mode || 'mix'"
                :title="LIGHTRAG_MODE_DESC[activeConfig.lightrag_query_mode || 'mix']"
                @change="onLightragModeChange"
              >
                <option value="mix" :title="LIGHTRAG_MODE_DESC.mix">mix（推荐）</option>
                <option value="naive" :title="LIGHTRAG_MODE_DESC.naive">naive</option>
                <option value="local" :title="LIGHTRAG_MODE_DESC.local">local</option>
                <option value="global" :title="LIGHTRAG_MODE_DESC.global">global</option>
                <option value="hybrid" :title="LIGHTRAG_MODE_DESC.hybrid">hybrid</option>
              </select>
            </div>

            <div v-if="activeConfig && hasLightragKbSelected" class="field chat-lightrag-chunk-field">
              <span class="field-label chat-field-label-block">
                图片段数（chunk_top_k）
                <span class="chat-field-hint-wrap" tabindex="0" role="button" aria-label="图片段数说明">
                  <span class="chat-topk-help">?</span>
                </span>
                <span class="chat-field-hint-tooltip" role="tooltip">{{ LIGHTRAG_CHUNK_TOP_K_HELP }}</span>
              </span>
              <input
                v-model.number="chatChunkTopK"
                class="input"
                type="number"
                min="1"
                max="100"
                placeholder="默认 20"
                aria-label="图片段数"
                @change="onChatChunkTopKCommit"
                @blur="onChatChunkTopKCommit"
              />
            </div>

            <div v-if="activeConfig" class="field chat-citation-toggle-field">
              <div class="chat-citation-toggle-head">
                <span class="field-label chat-field-label-block">
                  显示引文
                  <span
                    class="chat-field-hint-wrap"
                    tabindex="0"
                    role="button"
                    aria-label="显示引文说明"
                  >
                    <span class="chat-topk-help">?</span>
                  </span>
                  <span class="chat-field-hint-tooltip" role="tooltip">{{ SHOW_CITATIONS_HELP }}</span>
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

          <section class="surface-card">
            <div class="section-heading compact-heading">
              <div>
                <h4>对话记忆</h4>
                <p class="section-subtext">控制发给大模型的多轮历史；不影响知识库检索（仍仅用本轮问题）</p>
              </div>
            </div>

            <div v-if="activeConfig" class="field chat-memory-field">
              <span class="field-label chat-field-label-block">
                记忆窗口（消息条数）
                <span
                  class="chat-field-hint-wrap"
                  tabindex="0"
                  role="button"
                  aria-label="记忆窗口说明"
                >
                  <span class="chat-topk-help">?</span>
                </span>
                <span class="chat-field-hint-tooltip" role="tooltip">{{ MEMORY_WINDOW_HELP }}</span>
              </span>
              <div class="chat-topk-slider-row">
                <input
                  v-model.number="chatMaxHistoryMessages"
                  class="input chat-topk-number-input"
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  aria-label="记忆窗口消息条数"
                  @change="onMaxHistoryMessagesCommit"
                  @blur="onMaxHistoryMessagesCommit"
                />
                <input
                  v-model.number="chatMaxHistoryMessages"
                  class="chat-topk-progress-range"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  :style="chatMaxHistorySliderStyle"
                  aria-label="记忆窗口滑动条"
                  @change="onMaxHistoryMessagesCommit"
                />
              </div>
            </div>

            <div v-if="activeConfig" class="field chat-memory-field">
              <span class="field-label chat-field-label-block">
                记忆 token 上限（可选）
                <span
                  class="chat-field-hint-wrap"
                  tabindex="0"
                  role="button"
                  aria-label="记忆 token 上限说明"
                >
                  <span class="chat-topk-help">?</span>
                </span>
                <span class="chat-field-hint-tooltip" role="tooltip">{{ MEMORY_TOKEN_HELP }}</span>
              </span>
              <input
                v-model="chatMaxHistoryTokensDraft"
                class="input"
                type="number"
                min="1"
                max="128000"
                step="256"
                placeholder="留空不限"
                aria-label="记忆 token 上限"
                @blur="flushMaxHistoryTokens"
              />
            </div>

            <div v-if="activeConfig" class="field chat-citation-toggle-field">
              <div class="chat-citation-toggle-head">
                <span class="field-label chat-field-label-block">
                  多轮检索改写
                  <span
                    class="chat-field-hint-wrap"
                    tabindex="0"
                    role="button"
                    aria-label="多轮检索改写说明"
                  >
                    <span class="chat-topk-help">?</span>
                  </span>
                  <span class="chat-field-hint-tooltip" role="tooltip">{{ REFINE_MULTITURN_HELP }}</span>
                </span>
              </div>
              <label class="chat-switch">
                <input
                  type="checkbox"
                  role="switch"
                  :checked="activeConfig.refine_multiturn === true"
                  @change="updateConfig('refine_multiturn', ($event.target as HTMLInputElement).checked)"
                />
                <span class="chat-switch-track" aria-hidden="true" />
              </label>
            </div>
          </section>

          <section v-if="activeConfig" class="surface-card chat-dialog-extras-card">
            <div class="section-heading compact-heading">
              <div>
                <h4>对话体验</h4>
                <p class="section-subtext">开场白与无检索命中时的兜底回复</p>
              </div>
            </div>
            <label class="field">
              <span class="field-label chat-field-label-block">
                开场白
                <span class="chat-field-hint-wrap" tabindex="0" role="button" aria-label="开场白说明">
                  <span class="chat-topk-help">?</span>
                </span>
                <span class="chat-field-hint-tooltip" role="tooltip">{{ OPENING_GREETING_HELP }}</span>
              </span>
              <textarea
                v-model="openingGreetingDraft"
                class="textarea"
                rows="3"
                :placeholder="DEFAULT_OPENING_GREETING"
                aria-label="开场白"
                @blur="flushOpeningGreeting"
              />
            </label>
            <label class="field">
              <span class="field-label chat-field-label-block">
                空检索回复
                <span class="chat-field-hint-wrap" tabindex="0" role="button" aria-label="空检索回复说明">
                  <span class="chat-topk-help">?</span>
                </span>
                <span class="chat-field-hint-tooltip" role="tooltip">{{ EMPTY_RESPONSE_HELP }}</span>
              </span>
              <textarea
                v-model="emptyResponseDraft"
                class="textarea"
                rows="3"
                placeholder="已选知识库但未命中任何片段时的固定回复；留空则仍调用大模型"
                aria-label="空检索回复"
                @blur="flushEmptyResponse"
              />
            </label>
          </section>

          <section v-if="activeConfig" class="surface-card chat-suggest-settings-card">
            <div class="chat-suggest-setting-row">
              <div class="chat-suggest-setting-icon" aria-hidden="true">
                <AppIcon name="chat" :size="18" />
              </div>
              <div class="chat-suggest-setting-text">
                <div class="chat-suggest-setting-title chat-field-label-block">
                  下一步问题建议
                  <span class="chat-field-hint-wrap" tabindex="0" role="button" aria-label="下一步问题建议说明">
                    <span class="chat-topk-help">?</span>
                  </span>
                  <span class="chat-field-hint-tooltip" role="tooltip">{{ SUGGEST_QUESTIONS_HELP }}</span>
                </div>
              </div>
              <button
                type="button"
                class="btn btn-text chat-suggest-setting-gear"
                aria-label="下一步问题建议设置"
                @click="openSuggestQuestionsModal"
              >
                <AppIcon name="settings" :size="18" />
              </button>
              <label class="chat-switch chat-suggest-setting-switch">
                <input
                  type="checkbox"
                  role="switch"
                  :checked="activeConfig.suggest_next_questions_enabled === true"
                  @change="
                    updateConfig('suggest_next_questions_enabled', ($event.target as HTMLInputElement).checked)
                  "
                />
                <span class="chat-switch-track" aria-hidden="true" />
              </label>
            </div>
          </section>
        </aside>

      </div>
      </div>
      <!-- 下一步问题建议设置 -->
      <Teleport to="body">
        <div v-if="showSuggestQuestionsModal" class="modal-overlay" @click.self="closeSuggestQuestionsModal">
          <div class="modal-content chat-suggest-modal" @click.stop>
            <div class="modal-header">
              <h3>下一步问题建议设置</h3>
              <button type="button" class="btn btn-text" aria-label="关闭" @click="closeSuggestQuestionsModal">
                <AppIcon name="close" :size="20" />
              </button>
            </div>
            <div class="modal-body chat-suggest-modal-body">
              <label class="field">
                <span class="field-label">模型</span>
                <select v-model="suggestModelIdDraft" class="select">
                  <option :value="null">系统默认模型（与对话主模型相同）</option>
                  <option v-for="m in flatChatModels" :key="m.id" :value="m.id">
                    {{ m.model_name }} · {{ m.provider_name }}
                  </option>
                </select>
              </label>

              <div class="field">
                <span class="field-label">提示词</span>
                <div class="chat-suggest-prompt-options">
                  <label
                    class="chat-suggest-prompt-card"
                    :class="{ 'is-selected': suggestPromptModeDraft === 'system' }"
                  >
                    <input v-model="suggestPromptModeDraft" type="radio" class="sr-only" value="system" />
                    <div class="chat-suggest-prompt-card-head">
                      <span class="chat-suggest-prompt-card-title">系统默认提示词</span>
                      <span class="chat-suggest-prompt-card-radio" aria-hidden="true" />
                    </div>
                    <p class="chat-suggest-prompt-card-desc">使用内置提示词生成下一步问题。</p>
                    <pre class="chat-suggest-prompt-preview">{{ DEFAULT_SUGGEST_NEXT_QUESTIONS_PROMPT }}</pre>
                  </label>
                  <label
                    class="chat-suggest-prompt-card"
                    :class="{ 'is-selected': suggestPromptModeDraft === 'custom' }"
                  >
                    <input v-model="suggestPromptModeDraft" type="radio" class="sr-only" value="custom" />
                    <div class="chat-suggest-prompt-card-head">
                      <span class="chat-suggest-prompt-card-title">自定义提示词</span>
                      <span class="chat-suggest-prompt-card-radio" aria-hidden="true" />
                    </div>
                    <p class="chat-suggest-prompt-card-desc">编写并使用你自己的下一步问题生成提示词。</p>
                    <textarea
                      v-model="suggestCustomPromptDraft"
                      class="textarea chat-suggest-prompt-custom"
                      rows="4"
                      placeholder="请输入自定义提示词…"
                      :disabled="suggestPromptModeDraft !== 'custom'"
                    />
                  </label>
                </div>
              </div>
            </div>
            <div class="modal-footer chat-suggest-modal-footer">
              <button type="button" class="btn btn-secondary" @click="closeSuggestQuestionsModal">取消</button>
              <button type="button" class="btn btn-primary" @click="saveSuggestQuestionsModal">保存</button>
            </div>
          </div>
        </div>
      </Teleport>

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
            <pre v-else-if="citationModalContent" class="citation-chunk-modal-body">{{ citationModalContent }}</pre>
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
              <label class="field-label">请输入聊天助手名称</label>
              <input 
                v-model="newChatTitle" 
                type="text" 
                class="input" 
                placeholder="例如：智能对话助手" 
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
            <h3>删除对话</h3>
            <button class="btn btn-text" @click="closeDeleteModal">
              <AppIcon name="close" :size="20" />
            </button>
          </div>
          <div class="modal-body">
            <p style="margin: 0 0 16px 0; color: var(--text-secondary); line-height: 1.5;">
              将删除对话 <strong>「{{ deleteTarget.title }}」</strong> 及其下全部会话，且不可恢复。
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
        <div class="modal-content modal-wide modal-embed">
          <div class="modal-header modal-header--embed">
            <div>
              <h3>嵌入到网站中</h3>
              <p class="embed-modal-lead">选择一种方式将聊天应用嵌入到你的网站中</p>
            </div>
            <button class="btn btn-text" type="button" aria-label="关闭" @click="showEmbedModal = false">
              <AppIcon name="close" :size="20" />
            </button>
          </div>
          <div class="modal-body access-modal-body embed-modal-body">
            <div class="embed-security-warning">
              <strong>安全提示：</strong>嵌入 API Key 与登录 JWT 具备同等接口访问能力，滥用可能导致<strong>模型调用费用</strong>等损失。<strong>强烈建议</strong>由后端安全存储密钥，通过服务端渲染或网关反向代理注入
              <code>Authorization: Bearer …</code>，避免将完整 Key 写入公开前端仓库、静态资源或长期存放在访客浏览器中。
            </div>

            <div class="embed-method-grid" role="radiogroup" aria-label="嵌入方式">
              <button
                type="button"
                class="embed-method-card"
                :class="{ 'embed-method-card--active': embedMethod === 'iframe' }"
                role="radio"
                :aria-checked="embedMethod === 'iframe'"
                @click="embedMethod = 'iframe'"
              >
                <span v-if="embedMethod === 'iframe'" class="embed-method-selected-mark" aria-hidden="true">
                  <AppIcon name="check" :size="14" />
                </span>
                <div class="embed-method-thumb embed-method-thumb--iframe" aria-hidden="true">
                  <div class="emb-browser-chrome">
                    <span class="emb-dot" /><span class="emb-dot" /><span class="emb-dot" />
                  </div>
                  <div class="emb-browser-body">
                    <span class="emb-sidebar" />
                    <span class="emb-chat-pane" />
                  </div>
                </div>
                <span class="embed-method-title">页面内 iframe</span>
                <span class="embed-method-desc">在页面任意位置嵌入完整对话页</span>
              </button>
              <button
                type="button"
                class="embed-method-card"
                :class="{ 'embed-method-card--active': embedMethod === 'bubble' }"
                role="radio"
                :aria-checked="embedMethod === 'bubble'"
                @click="embedMethod = 'bubble'"
              >
                <span v-if="embedMethod === 'bubble'" class="embed-method-selected-mark" aria-hidden="true">
                  <AppIcon name="check" :size="14" />
                </span>
                <div class="embed-method-thumb embed-method-thumb--bubble" aria-hidden="true">
                  <div class="emb-browser-chrome emb-browser-chrome--mini">
                    <span class="emb-dot" /><span class="emb-dot" /><span class="emb-dot" />
                  </div>
                  <div class="emb-page-canvas">
                    <span class="emb-line" /><span class="emb-line emb-line--short" /><span class="emb-line" />
                  </div>
                  <span class="emb-bubble-fab" />
                </div>
                <span class="embed-method-title">悬浮气泡</span>
                <span class="embed-method-desc">右下角气泡按钮，点击展开对话窗口</span>
              </button>
            </div>

            <div class="embed-key-panel">
              <div v-if="embedConversationId" class="access-block embed-key-block">
                <div class="access-block-head">
                  <span class="access-label">聊天 ID</span>
                  <button type="button" class="btn btn-text btn-copy" @click.stop="copyEmbedChatId">复制</button>
                </div>
                <pre class="access-pre">{{ embedConversationId }}</pre>
                <p class="embed-field-hint">用于对外 API（如 <code>ZS_RAG_CHAT_ID</code>、OpenAI 路径中的 chat_id）</p>
              </div>

              <p v-if="embedKeyEnsureLoading" class="embed-key-meta embed-key-meta--inline">正在准备嵌入密钥…</p>
              <p v-if="embedKeyEnsureError" class="embed-key-meta embed-key-meta--error">{{ embedKeyEnsureError }}</p>

              <div class="embed-key-toolbar">
                <button
                  type="button"
                  class="btn btn-secondary"
                  :disabled="embedKeyEnsureLoading"
                  @click="rotateEmbedApiKey"
                >
                  轮换密钥
                </button>
                <span v-if="embedApiKeyPlaintext" class="embed-key-hint">
                  密钥仅此窗口展示一次，请复制保存。
                </span>
              </div>

              <div v-if="embedApiKeyPlaintext" class="access-block embed-key-block">
                <div class="access-block-head">
                  <span class="access-label">嵌入 API Key（Authorization: Bearer）</span>
                  <button type="button" class="btn btn-text btn-copy" @click.stop="copyText(embedApiKeyPlaintext || '')">
                    复制
                  </button>
                </div>
                <pre class="access-pre">{{ embedApiKeyPlaintext }}</pre>
              </div>
            </div>

            <p class="embed-snippet-hint">
              <template v-if="embedMethod === 'iframe'">
                将以下 iframe 粘贴到目标位置。URL 已包含 <code>api_key</code> 与当前企业空间 <code>space</code>；接口请求头为
                <code>Authorization: Bearer &lt;同一密钥&gt;</code>。示例中占位符请替换为轮换后的真实密钥或由后端注入。
              </template>
              <template v-else>
                将以下代码放在 <code>&lt;/body&gt;</code> 前；<code>src</code> 指向嵌入入口并携带 <code>api_key</code> /
                <code>space</code>。
              </template>
            </p>
            <div class="access-block embed-snippet-block">
              <div class="access-block-head">
                <span class="access-label">嵌入代码</span>
                <button type="button" class="btn btn-text btn-copy" @click="copyText(currentEmbedSnippet)">
                  复制
                </button>
              </div>
              <pre class="access-pre embed-snippet-pre">{{ currentEmbedSnippet }}</pre>
            </div>

            <div class="access-block">
              <div class="access-block-head">
                <span class="access-label">站内对话工作台（需已登录）</span>
                <button type="button" class="btn btn-text btn-copy" @click="copyText(chatPageUrl)">复制</button>
              </div>
              <pre class="access-pre">{{ chatPageUrl }}</pre>
            </div>
            <div class="access-block">
              <div class="access-block-head">
                <span class="access-label">嵌入入口（含 api_key / space 查询参数）</span>
                <button type="button" class="btn btn-text btn-copy" @click="copyText(embedFullChatEmbedUrl)">复制</button>
              </div>
              <pre class="access-pre">{{ embedFullChatEmbedUrl }}</pre>
            </div>
          </div>
        </div>
      </div>

      <!-- 接入信息 -->
      <div v-if="showAccessModal" class="modal-overlay" @click.self="showAccessModal = false">
        <div class="modal-content modal-wide modal-api-access">
          <div class="modal-header">
            <div>
              <h3>API 接入</h3>
              <p class="modal-subtitle">{{ apiAccessModalSubtitle }}</p>
            </div>
            <div class="modal-header-actions">
              <button
                v-if="apiAccessMode === 'zs-rag'"
                type="button"
                class="btn btn-text btn-download-doc"
                :disabled="chatApiDocDownloading"
                @click="onDownloadChatApiDoc"
              >
                {{ chatApiDocDownloading ? '下载中…' : '下载接入文档' }}
              </button>
              <button
                v-else
                type="button"
                class="btn btn-text btn-download-doc"
                :disabled="chatApiDocDownloading"
                @click="onDownloadOpenAiExampleDoc"
              >
                {{ chatApiDocDownloading ? '下载中…' : '下载 OpenAI 示例' }}
              </button>
              <button class="btn btn-text" type="button" @click="showAccessModal = false">
                <AppIcon name="close" :size="20" />
              </button>
            </div>
          </div>
          <div class="modal-body access-modal-body" @click="closeApiAccessDropdowns">
            <div class="api-access-mode-field" @click.stop>
              <span class="api-access-mode-label">接入方式</span>
              <div
                class="api-access-mode-picker"
                :class="{ 'api-access-mode-picker--open': apiAccessModeMenuOpen }"
              >
                <button
                  type="button"
                  class="api-access-mode-trigger"
                  :aria-expanded="apiAccessModeMenuOpen"
                  aria-haspopup="listbox"
                  aria-label="选择接入方式"
                  @click.stop="toggleApiAccessModeMenu"
                >
                  <span class="api-access-mode-trigger-label">{{ apiAccessModeLabel }}</span>
                  <AppIcon
                    name="chevron-down"
                    :size="14"
                    class="api-access-mode-chevron"
                    :class="{ 'is-open': apiAccessModeMenuOpen }"
                  />
                </button>
                <div
                  v-if="apiAccessModeMenuOpen"
                  class="api-access-mode-dropdown"
                  role="presentation"
                  @click.stop
                >
                  <div class="api-access-mode-list scrollbar-pill" role="listbox" aria-label="接入方式列表">
                    <button
                      v-for="opt in apiAccessModeOptions"
                      :key="opt.value"
                      type="button"
                      role="option"
                      class="api-access-mode-option"
                      :class="{ 'is-current': apiAccessMode === opt.value }"
                      :aria-selected="apiAccessMode === opt.value"
                      @click="pickApiAccessMode(opt.value)"
                    >
                      <span class="api-access-mode-option-name">{{ opt.label }}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <template v-if="apiAccessMode === 'openai'">
              <div class="openai-access-id-panel">
                <div class="access-block embed-key-block">
                  <div class="access-block-head">
                    <span class="access-label">base_url<span class="openai-field-tag">（必填）</span></span>
                    <button type="button" class="btn btn-text btn-copy" @click.stop="copyText(openAiBaseUrlDisplay)">
                      复制
                    </button>
                  </div>
                  <pre class="access-pre">{{ openAiBaseUrlDisplay }}</pre>
                </div>
                <div class="access-block embed-key-block">
                  <div class="access-block-head">
                    <span class="access-label">API Key<span class="openai-field-tag">（必填）</span></span>
                    <button
                      type="button"
                      class="btn btn-text btn-copy"
                      :disabled="!embedApiKeyPlaintext"
                      @click.stop="copyText(embedApiKeyPlaintext || '')"
                    >
                      复制
                    </button>
                  </div>
                  <pre class="access-pre">{{ openAiApiKeyDisplay }}</pre>
                  <p v-if="embedKeyEnsureError" class="embed-field-hint embed-field-hint--error">
                    {{ embedKeyEnsureError }}
                  </p>
                  <p v-else-if="!embedApiKeyPlaintext && !embedKeyEnsureLoading" class="embed-field-hint">
                    用于 <code>Authorization: Bearer</code>；也可在「嵌入网站」中轮换密钥。
                  </p>
                </div>
                <div class="access-block embed-key-block">
                  <div class="access-block-head">
                    <span class="access-label">chat_id<span class="openai-field-tag">（必填）</span></span>
                    <button type="button" class="btn btn-text btn-copy" @click.stop="copyText(openAiParamChatId)">
                      复制
                    </button>
                  </div>
                  <pre class="access-pre">{{ openAiParamChatId }}</pre>
                </div>
                <div class="access-block embed-key-block">
                  <div class="access-block-head">
                    <span class="access-label">session_id<span class="openai-field-tag openai-field-tag--optional">（非必须）</span></span>
                    <button type="button" class="btn btn-text btn-copy" @click.stop="copyText(openAiParamSessionId)">
                      复制
                    </button>
                  </div>
                  <pre class="access-pre">{{ openAiParamSessionId }}</pre>
                </div>
              </div>

              <section class="openai-access-example" @click.stop="openAiClientLangMenuOpen = false">
                <div class="openai-access-example-head">
                  <span class="openai-access-example-title">
                    <AppIcon name="arrow-up-right" :size="14" class="openai-access-example-icon" />
                    Create chat completion
                  </span>
                  <div class="openai-access-example-actions">
                    <div class="openai-access-tabs" role="tablist" aria-label="流式或非流式">
                      <button
                        type="button"
                        role="tab"
                        class="openai-access-tab"
                        :class="{ 'is-active': openAiCurlStream }"
                        :aria-selected="openAiCurlStream"
                        @click="openAiCurlStream = true"
                      >
                        流式
                      </button>
                      <button
                        type="button"
                        role="tab"
                        class="openai-access-tab"
                        :class="{ 'is-active': !openAiCurlStream }"
                        :aria-selected="!openAiCurlStream"
                        @click="openAiCurlStream = false"
                      >
                        非流式
                      </button>
                    </div>
                    <div
                      class="openai-access-lang-picker"
                      :class="{ 'openai-access-lang-picker--open': openAiClientLangMenuOpen }"
                      @click.stop
                    >
                      <button
                        type="button"
                        class="openai-access-lang-trigger"
                        :aria-expanded="openAiClientLangMenuOpen"
                        aria-haspopup="listbox"
                        aria-label="选择客户端语言"
                        @click.stop="toggleOpenAiClientLangMenu"
                      >
                        <span class="openai-access-lang-trigger-label">{{ openAiClientLangLabel }}</span>
                        <AppIcon
                          name="chevron-down"
                          :size="12"
                          class="openai-access-lang-chevron"
                          :class="{ 'is-open': openAiClientLangMenuOpen }"
                        />
                      </button>
                      <div
                        v-if="openAiClientLangMenuOpen"
                        class="openai-access-lang-dropdown"
                        role="presentation"
                        @click.stop
                      >
                        <div class="openai-access-lang-list scrollbar-pill" role="listbox" aria-label="客户端语言">
                          <button
                            v-for="opt in openAiClientLangOptions"
                            :key="opt.value"
                            type="button"
                            role="option"
                            class="openai-access-lang-option"
                            :class="{ 'is-current': openAiClientLang === opt.value }"
                            :aria-selected="openAiClientLang === opt.value"
                            @click="pickOpenAiClientLang(opt.value)"
                          >
                            {{ opt.label }}
                          </button>
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      class="btn btn-text btn-copy openai-access-copy-btn"
                      title="复制"
                      aria-label="复制代码"
                      @click="copyText(openAiCodeExample)"
                    >
                      <AppIcon name="copy" :size="16" />
                    </button>
                  </div>
                </div>
                <pre class="access-pre access-pre--code openai-access-code">{{ openAiCodeExample }}</pre>
                <div class="api-access-response-section">
                  <div class="api-access-response-head">
                    <span class="api-access-response-label">响应示例</span>
                    <span class="api-access-response-meta">{{ openAiCurlStream ? 'SSE' : 'JSON' }}</span>
                    <button
                      type="button"
                      class="btn btn-text btn-copy openai-access-copy-btn"
                      title="复制响应示例"
                      @click="copyText(openAiResponseExample)"
                    >
                      <AppIcon name="copy" :size="16" />
                    </button>
                  </div>
                  <pre class="access-pre access-pre--code api-access-response-body">{{ openAiResponseExample }}</pre>
                </div>
              </section>
              <ul class="openai-access-notes">
                <li><code>chat_id</code> 必须填写（已体现在 <code>base_url</code> 路径中）。</li>
                <li><code>session_id</code> 可不传；推荐传入，以复用平台的多轮对话上下文管理。</li>
              </ul>
              <p class="openai-access-doc-link">
                官方文档：
                <a
                  href="https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="openai-access-link"
                >Create chat completion</a>
              </p>
            </template>

            <template v-else>
              <div class="openai-access-id-panel">
                <div class="access-block embed-key-block">
                  <div class="access-block-head">
                    <span class="access-label">chat_id<span class="openai-field-tag">（必填）</span></span>
                    <button type="button" class="btn btn-text btn-copy" @click.stop="copyText(openAiParamChatId)">
                      复制
                    </button>
                  </div>
                  <pre class="access-pre">{{ openAiParamChatId }}</pre>
                </div>
                <div class="access-block embed-key-block">
                  <div class="access-block-head">
                    <span class="access-label">API Key<span class="openai-field-tag">（必填）</span></span>
                    <button
                      type="button"
                      class="btn btn-text btn-copy"
                      :disabled="!embedApiKeyPlaintext"
                      @click.stop="copyText(embedApiKeyPlaintext || '')"
                    >
                      复制
                    </button>
                  </div>
                  <pre class="access-pre">{{ openAiApiKeyDisplay }}</pre>
                  <p v-if="embedKeyEnsureError" class="embed-field-hint embed-field-hint--error">
                    {{ embedKeyEnsureError }}
                  </p>
                </div>
                <div class="access-block embed-key-block">
                  <div class="access-block-head">
                    <span class="access-label">session_id<span class="openai-field-tag openai-field-tag--optional">（非必须）</span></span>
                    <button type="button" class="btn btn-text btn-copy" @click.stop="copyText(openAiParamSessionId)">
                      复制
                    </button>
                  </div>
                  <pre class="access-pre">{{ openAiParamSessionId }}</pre>
                </div>
              </div>

              <section class="zs-rag-access-api">
                <h4 class="access-section-title">1. 对话级（不携带 session_id）</h4>
                <p class="access-muted">
                  站内 SSE：<code>POST /api/v1/chats/{chat_id}/stream</code>。自动建会话；请从
                  <code>assistant_done</code> 事件中复制 <code>session_id</code> 供接口 2 使用。
                </p>
                <div class="openai-access-example">
                  <div class="openai-access-example-head">
                    <span class="openai-access-example-title">
                      <span class="api-method api-method--post">POST</span>
                      <code class="zs-rag-access-path">{{ zsRagChatLevelPath }}</code>
                    </span>
                    <button
                      type="button"
                      class="btn btn-text btn-copy openai-access-copy-btn"
                      title="复制 curl"
                      @click="copyText(zsRagChatLevelCurl)"
                    >
                      <AppIcon name="copy" :size="16" />
                    </button>
                  </div>
                  <pre class="access-pre access-pre--code openai-access-code">{{ zsRagChatLevelCurl }}</pre>
                  <div class="api-access-response-section">
                    <div class="api-access-response-head">
                      <span class="api-access-response-label">响应示例</span>
                      <span class="api-access-response-meta">SSE</span>
                      <button
                        type="button"
                        class="btn btn-text btn-copy openai-access-copy-btn"
                        title="复制响应示例"
                        @click="copyText(zsRagChatLevelResponseExample)"
                      >
                        <AppIcon name="copy" :size="16" />
                      </button>
                    </div>
                    <pre class="access-pre access-pre--code api-access-response-body">{{ zsRagChatLevelResponseExample }}</pre>
                  </div>
                </div>
              </section>

              <section class="zs-rag-access-api">
                <h4 class="access-section-title">2. 会话级（绑定当前 session_id）</h4>
                <p class="access-muted">
                  绑定当前 <code>session_id</code>：流式 <code>…/stream</code>，非流式 <code>…/complete</code>，请求体均为
                  <code>{"content":"..."}</code>。
                </p>
                <div class="openai-access-example">
                  <div class="openai-access-example-head">
                    <span class="openai-access-example-title">
                      <span class="api-method api-method--post">POST</span>
                      <code class="zs-rag-access-path">{{ zsRagSessionApiPath }}</code>
                    </span>
                    <div class="openai-access-example-actions">
                      <div class="openai-access-tabs" role="tablist" aria-label="流式或非流式">
                        <button
                          type="button"
                          role="tab"
                          class="openai-access-tab"
                          :class="{ 'is-active': zsRagSessionStream }"
                          :aria-selected="zsRagSessionStream"
                          @click="zsRagSessionStream = true"
                        >
                          流式
                        </button>
                        <button
                          type="button"
                          role="tab"
                          class="openai-access-tab"
                          :class="{ 'is-active': !zsRagSessionStream }"
                          :aria-selected="!zsRagSessionStream"
                          @click="zsRagSessionStream = false"
                        >
                          非流式
                        </button>
                      </div>
                      <button
                        type="button"
                        class="btn btn-text btn-copy openai-access-copy-btn"
                        title="复制 curl"
                        @click="copyText(zsRagSessionCurlExample)"
                      >
                        <AppIcon name="copy" :size="16" />
                      </button>
                    </div>
                  </div>
                  <pre class="access-pre access-pre--code openai-access-code">{{ zsRagSessionCurlExample }}</pre>
                  <div class="api-access-response-section">
                    <div class="api-access-response-head">
                      <span class="api-access-response-label">响应示例</span>
                      <span class="api-access-response-meta">{{ zsRagSessionStream ? 'SSE' : 'JSON' }}</span>
                      <button
                        type="button"
                        class="btn btn-text btn-copy openai-access-copy-btn"
                        title="复制响应示例"
                        @click="copyText(zsRagSessionResponseExample)"
                      >
                        <AppIcon name="copy" :size="16" />
                      </button>
                    </div>
                    <pre class="access-pre access-pre--code api-access-response-body">{{ zsRagSessionResponseExample }}</pre>
                  </div>
                </div>
              </section>

              <p class="openai-access-doc-link">
                完整说明见
                <button type="button" class="btn btn-text btn-link-inline" @click="onDownloadChatApiDoc">
                  下载接入文档
                </button>
              </p>
            </template>

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
import { resolveApiBaseUrl } from '../lib/apiBaseUrl'
import { useRoute, useRouter } from 'vue-router'
import { knowledgeBaseApi, type KnowledgeBase, type KnowledgeChunk } from '../api/knowledge-base'
import {
  defaultRetrievalFormState,
  syncTopKToKnowledgeBases,
  topKFromKnowledgeBases,
} from '../components/knowledge-base/retrieval-form'
import { modelApi, defaultModelApi, type DefaultModelOption, type ModelItem, type ProviderModelsGroup } from '../api/model-management'
import {
  chatEmbedApiKeyApi,
  type ChatSession,
  type ChatMessage,
  type ChatCitation,
} from '../api/chat'
import { useAuthStore } from '../stores/auth'
import { useLayoutPageContext } from '../composables/useLayoutPageContext'
import {
  buildOpenAiAccessCurl,
  buildOpenAiAccessPython,
  buildOpenAiChatCompletionsBaseUrl,
  buildOpenAiNonStreamResponseExample,
  buildOpenAiStreamResponseExample,
  buildZsRagChatLevelCurl,
  buildZsRagCompleteResponseExample,
  buildZsRagSessionCompletionCurl,
  buildZsRagSessionStreamCurl,
  buildZsRagSseResponseExample,
  type OpenAiClientLang,
  downloadChatApiDoc,
  downloadOpenAiExampleDoc,
  type ApiAccessMode,
  type ChatApiAccessContext,
} from '../lib/chat-api-access'
import { copyToClipboard } from '../lib/copy-to-clipboard'

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
    const rawChunkId = r.chunk_id
    let chunk_id: number | string | undefined
    if (typeof rawChunkId === 'number' && Number.isFinite(rawChunkId)) {
      chunk_id = rawChunkId
    } else if (typeof rawChunkId === 'string' && rawChunkId.trim()) {
      const asNum = Number(rawChunkId)
      chunk_id = Number.isFinite(asNum) && String(asNum) === rawChunkId.trim() ? asNum : rawChunkId.trim()
    }
    const rawSource = r.source
    const source =
      typeof rawSource === 'string' && rawSource.trim() ? rawSource.trim() : undefined
    const rawContent = r.content
    const content =
      rawContent == null || rawContent === ''
        ? null
        : typeof rawContent === 'string'
          ? rawContent
          : String(rawContent)
    out.push({
      ref,
      document_name: String(r.document_name ?? ''),
      page_no: r.page_no == null ? null : Number(r.page_no),
      knowledge_base_id: r.knowledge_base_id != null ? Number(r.knowledge_base_id) : undefined,
      chunk_id,
      document_id: r.document_id != null ? Number(r.document_id) : undefined,
      chunk_index: r.chunk_index != null ? Number(r.chunk_index) : undefined,
      score: r.score != null ? Number(r.score) : undefined,
      source,
      content,
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
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const { setPageContext, setChatHomeHandler, clearPageContext } = useLayoutPageContext()

function syncChatPageHeader() {
  const conv = chatStore.activeConversation
  if (chatStore.activeConversationId && conv?.title) {
    setPageContext({ title: conv.title, breadcrumbTail: conv.title })
    setChatHomeHandler(() => chatStore.leaveConversation())
    return
  }
  setPageContext({ title: '对话', breadcrumbTail: null })
  setChatHomeHandler(null)
}

watch(
  () => [chatStore.activeConversationId, chatStore.activeConversation?.title] as const,
  () => syncChatPageHeader(),
  { immediate: true },
)

/** URL ?embed_panel=1：iframe 内仅展示对话主区（隐藏平台导航与「会话」侧栏） */
const isEmbedPanelMode = computed(() => {
  const ep = route.query.embed_panel
  return ep === '1' || ep === 'true'
})

const citationModalOpen = ref(false)
const citationModalCitation = ref<ChatCitation | null>(null)
const citationModalChunk = ref<KnowledgeChunk | null>(null)
const citationModalContent = ref('')
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
  citationModalContent.value = ''
  citationModalError.value = ''
  citationModalLoading.value = false
}

async function openCitationDetail(c: ChatCitation) {
  citationModalCitation.value = c
  citationModalChunk.value = null
  citationModalContent.value = ''
  citationModalError.value = ''
  citationModalOpen.value = true
  // 图谱库引用：chunk_id 为 LightRAG 内部 ID，无法 getChunk，直接展示随附正文
  if (c.source === 'graph' || (typeof c.chunk_id !== 'number' && c.content != null)) {
    if (c.content != null && String(c.content).trim()) {
      citationModalContent.value = String(c.content)
    } else {
      citationModalError.value = '该图谱引用未携带正文，请点击「打开文档原文」查看。'
    }
    return
  }
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
    const chunk = await knowledgeBaseApi.getChunk(kbId, chunkId)
    citationModalChunk.value = chunk
    citationModalContent.value = chunk.content
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
  const query: Record<string, string> = {}
  if (c.chunk_index != null) {
    query.focus_chunk_index = String(c.chunk_index)
  }
  if (c.page_no != null) {
    query.focus_page_no = String(c.page_no)
  }
  if (c.chunk_id != null) {
    query.focus_chunk_id = String(c.chunk_id)
  }
  void router.push({
    name: 'knowledge-document-detail',
    params: { kbId: String(kbId), docId: String(docId) },
    query,
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
const embedMethod = ref<'iframe' | 'bubble'>('iframe')
const embedApiKeyPlaintext = ref<string | null>(null)
const embedKeyEnsureLoading = ref(false)
const embedKeyEnsureError = ref('')

const embedConversationId = computed(() => {
  const id = chatStore.activeConversationId
  return id != null ? String(id) : ''
})
const showAccessModal = ref(false)
const apiAccessMode = ref<ApiAccessMode>('zs-rag')
const apiAccessModeMenuOpen = ref(false)
const openAiCurlStream = ref(true)
const zsRagSessionStream = ref(true)
const openAiClientLang = ref<OpenAiClientLang>('http')
const openAiClientLangMenuOpen = ref(false)

const openAiClientLangOptions = [
  { value: 'http' as const, label: 'HTTP' },
  { value: 'python' as const, label: 'Python' },
] as const

const openAiClientLangLabel = computed(
  () => openAiClientLangOptions.find((o) => o.value === openAiClientLang.value)?.label ?? 'HTTP',
)

const apiAccessModeOptions = [
  { value: 'zs-rag' as const, label: 'zs-rag 接口方式' },
  { value: 'openai' as const, label: 'OpenAI API 格式' },
] as const

const apiAccessModeLabel = computed(
  () =>
    apiAccessModeOptions.find((o) => o.value === apiAccessMode.value)?.label ?? 'zs-rag 接口方式',
)
const chatApiDocDownloading = ref(false)

async function ensureEmbedApiKey(opts?: { noConversationMessage?: string }) {
  embedKeyEnsureError.value = ''
  const cid = chatStore.activeConversationId
  if (!cid) {
    embedApiKeyPlaintext.value = null
    if (opts?.noConversationMessage) {
      embedKeyEnsureError.value = opts.noConversationMessage
    }
    return
  }

  const storageKey = `zs_rag_embed_api_key:${authStore.currentSpaceSlug || 'default'}:${cid}`
  const cached =
    typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(storageKey) : null
  embedApiKeyPlaintext.value = cached?.trim() ? cached : null

  embedKeyEnsureLoading.value = true
  try {
    const { data } = await chatEmbedApiKeyApi.ensureOrCreate({
      conversation_id: cid,
      regenerate: false,
    })
    if (data.api_key) {
      embedApiKeyPlaintext.value = data.api_key
      if (typeof sessionStorage !== 'undefined') {
        sessionStorage.setItem(storageKey, data.api_key)
      }
    } else if (!embedApiKeyPlaintext.value) {
      const { data: again } = await chatEmbedApiKeyApi.ensureOrCreate({
        conversation_id: cid,
        issue_new_for_share: true,
      })
      if (again.api_key) {
        embedApiKeyPlaintext.value = again.api_key
        if (typeof sessionStorage !== 'undefined') {
          sessionStorage.setItem(storageKey, again.api_key)
        }
      }
    }
  } catch {
    embedKeyEnsureError.value = '无法准备嵌入 API Key，请确认已登录且对本对话有权限。'
  } finally {
    embedKeyEnsureLoading.value = false
  }
}

watch(showEmbedModal, async (open) => {
  if (!open) return
  await ensureEmbedApiKey({
    noConversationMessage: '请先进入一则对话，并在右侧打开「嵌入网站」。',
  })
})

async function rotateEmbedApiKey() {
  const cid = chatStore.activeConversationId
  if (!cid) return

  embedKeyEnsureLoading.value = true
  embedKeyEnsureError.value = ''
  const storageKey = `zs_rag_embed_api_key:${authStore.currentSpaceSlug || 'default'}:${cid}`
  try {
    const { data } = await chatEmbedApiKeyApi.ensureOrCreate({
      conversation_id: cid,
      regenerate: true,
    })
    embedApiKeyPlaintext.value = data.api_key ?? null
    if (typeof sessionStorage !== 'undefined') {
      if (data.api_key) {
        sessionStorage.setItem(storageKey, data.api_key)
      } else {
        sessionStorage.removeItem(storageKey)
      }
    }
  } catch {
    embedKeyEnsureError.value = '轮换密钥失败，请稍后重试。'
  } finally {
    embedKeyEnsureLoading.value = false
  }
}

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

const closeDeleteModal = (force = false) => {
  if (!force && isDeleting.value) return
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
  if (!canSubmitDelete.value || !deleteTarget.value || deleteTarget.value.kind !== 'conversation') return
  isDeleting.value = true
  try {
    await chatStore.deleteConversation(deleteTarget.value.id)
    closeDeleteModal(true)
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
    scrollChatToBottom()
    return
  }

  if (d.type === 'suggested_questions') {
    const qs = d.questions
    suggestedQuestions.value = Array.isArray(qs)
      ? qs.map((x) => String(x).trim()).filter(Boolean).slice(0, 3)
      : []
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
    void updateConfig('knowledge_base_ids', ids)
  },
})

const hasLightragKbSelected = computed(() => {
  const ids = new Set(chatKnowledgeBaseIds.value)
  return kbs.value.some((kb) => ids.has(kb.id) && kb.kb_type === 'lightrag')
})

async function onLightragModeChange(evt: Event) {
  const value = (evt.target as HTMLSelectElement).value as 'naive' | 'local' | 'global' | 'hybrid' | 'mix'
  await updateConfig('lightrag_query_mode', value)
}

const RETRIEVAL_TOP_K_HELP =
  '与知识库「检索设置 / 检索测试」中的 Top K 相同：单库时召回条数一致；多库时为合并排序后写入上下文的上限。修改后会同步保存到已选知识库。'

const SHOW_CITATIONS_HELP =
  '开启后，助手回复中的 [1]、[2] 等会显示为角标，并在消息下方列出对应知识库文档与页码；仅在选择知识库并命中检索片段时生效。'

const MEMORY_WINDOW_HELP =
  '控制发给大模型多少条历史 user/assistant 消息，用于多轮理解。设为 0 表示每轮不带历史；不影响知识库检索（仍只用本轮问题）。'

const MEMORY_TOKEN_HELP =
  '在消息条数限制之外，按 token 估算从最新消息向前截断，避免历史占满模型上下文。留空则仅按消息条数限制。'

const REFINE_MULTITURN_HELP =
  '开启后，结合最近对话将「它呢」「刚才那个」等省略问句改写成完整检索语句，再搜索知识库。仅影响检索 query，不改变对话记忆窗口。'

const SYSTEM_PROMPT_HELP =
  '定义助手的人设与回答规则。可用 {knowledge} 占位符，本轮检索到的知识库片段会自动插入该位置；留空保存后服务端会按是否绑定知识库选择默认模板。'

const LIGHTRAG_MODE_HELP =
  '图知识库（LightRAG）的检索策略：mix 综合多种图检索；naive 简单向量；local 侧重实体邻域；global 侧重全局关系；hybrid 混合 local 与 global。'

const LIGHTRAG_MODE_DESC: Record<'naive' | 'local' | 'global' | 'hybrid' | 'mix', string> = {
  mix: 'mix（推荐）：综合知识图谱与向量检索，覆盖最全面，既能利用实体/关系，也能召回原文片段，适合大多数场景。',
  naive: 'naive：基础向量相似度检索，不使用图谱结构，等同于普通 RAG，速度快但缺少关系推理。',
  local: 'local：侧重实体的邻域（局部子图），适合针对某个具体实体、细节或定义的问题。',
  global: 'global：侧重全局关系与主题脉络，适合概览、归纳、跨文档关联类的问题。',
  hybrid: 'hybrid：同时执行 local 与 global 并融合结果，兼顾细节与全局，但不含 mix 的向量片段召回。',
}

const LIGHTRAG_CHUNK_TOP_K_HELP =
  '图知识库向量侧召回的文档片段数（chunk_top_k），与上方 Top K（控制实体/关系）相互独立。留空则沿用 LightRAG 默认值 20。'

const DEFAULT_OPENING_GREETING = '你好，我是你的智能助手，有什么需要帮助的吗？'

const OPENING_GREETING_HELP =
  '新建会话时自动写入一条助手消息作为欢迎语。仅对新创建的会话生效，已存在会话不会 retroactive 插入；留空则新建会话不再显示开场白。'

const EMPTY_RESPONSE_HELP =
  '已选择知识库但本轮检索无任何命中片段时的固定回复；留空则仍调用大模型，结合系统提示词作答。'

const SUGGEST_QUESTIONS_HELP =
  '开启后，助手每次回复完成会在聊天区生成最多 3 条「试着问问」追问建议；空会话则展示默认示例问题。'

const TEMPERATURE_HELP =
  '控制回答的随机性与多样性。值越高，候选词分布越平滑、结果越发散；值越低，越倾向高概率词、结果越稳定。'

const MAX_TOKENS_HELP =
  '限制模型单次回复最多生成的 token 数，仅为上限，实际输出可能更短。上限优先取模型管理中的「最大输出 token」，其次为上下文窗口，均未配置时最高 131072。'

const TOP_P_HELP =
  '核采样阈值（0~1）。例如 0.8 表示只从累计概率 ≥80% 的最小 token 集合中采样；越大越随机，越小越确定。'

const DEFAULT_CHAT_TEMPERATURE = 0.7
const DEFAULT_CHAT_MAX_TOKENS = 2000
const DEFAULT_CHAT_TOP_P = 1.0
/** 最大标记滑条/输入的全局上限（未探测到模型规格时使用） */
const CHAT_MAX_TOKENS_SLIDER_CEILING = 131072

const DEFAULT_SUGGEST_NEXT_QUESTIONS_PROMPT =
  '请预测用户最可能追问的 3 个问题，每个问题不超过 20 字，使用与助手最新回复相同的语言，仅输出 JSON 数组，例如 ["问题1", "问题2", "问题3"]。'

const DEFAULT_STARTER_QUESTIONS = ['你能做什么？', '帮我写代码', '讲个笑话']

const suggestedQuestions = ref<string[]>([])
const showSuggestQuestionsModal = ref(false)
const suggestPromptModeDraft = ref<'system' | 'custom'>('system')
const suggestCustomPromptDraft = ref('')
const suggestModelIdDraft = ref<number | null>(null)

const displayedSuggestedQuestions = computed(() => {
  if (suggestedQuestions.value.length > 0) {
    return suggestedQuestions.value
  }
  const hasUserMsg = chatStore.messages.some((m) => m.role === 'user')
  if (!hasUserMsg) {
    return DEFAULT_STARTER_QUESTIONS
  }
  return []
})

const showSuggestedQuestionsBlock = computed(() => {
  if (chatStore.isGenerating) {
    return false
  }
  if (activeConfig.value?.suggest_next_questions_enabled !== true) {
    return false
  }
  return displayedSuggestedQuestions.value.length > 0
})

function openSuggestQuestionsModal() {
  const c = activeConfig.value
  suggestPromptModeDraft.value = c?.suggest_next_questions_prompt_mode === 'custom' ? 'custom' : 'system'
  suggestCustomPromptDraft.value = c?.suggest_next_questions_custom_prompt ?? ''
  suggestModelIdDraft.value = c?.suggest_next_questions_model_id ?? null
  showSuggestQuestionsModal.value = true
}

function closeSuggestQuestionsModal() {
  showSuggestQuestionsModal.value = false
}

async function saveSuggestQuestionsModal() {
  const mode = suggestPromptModeDraft.value
  await chatStore.updateConfiguration({
    suggest_next_questions_model_id: suggestModelIdDraft.value,
    suggest_next_questions_prompt_mode: mode,
    suggest_next_questions_custom_prompt:
      mode === 'custom' ? suggestCustomPromptDraft.value.trim() || null : null,
  })
  showSuggestQuestionsModal.value = false
}

function applySuggestedQuestion(q: string) {
  const text = q.trim()
  if (!text || chatStore.isGenerating) {
    return
  }
  draftMessage.value = text
  void handleSend()
}

const DEFAULT_CHAT_TOP_K = defaultRetrievalFormState().top_k

function clampChatRetrievalTopK(n: number): number {
  if (!Number.isFinite(n)) return DEFAULT_CHAT_TOP_K
  return Math.min(50, Math.max(1, Math.round(n)))
}

const chatTopK = ref(DEFAULT_CHAT_TOP_K)
const skipTopKFromKbWatch = ref(false)
let prevKbIdsKey = ''

watch(
  () => activeConfig.value?.retrieval_top_k,
  (v) => {
    if (skipTopKFromKbWatch.value) {
      return
    }
    chatTopK.value = clampChatRetrievalTopK(v ?? DEFAULT_CHAT_TOP_K)
  },
  { immediate: true },
)

// 图知识库片段数（chunk_top_k）：null/空表示沿用 LightRAG 默认（20）
const chatChunkTopK = ref<number | null>(null)

watch(
  () => activeConfig.value?.lightrag_chunk_top_k,
  (v) => {
    chatChunkTopK.value = typeof v === 'number' && v > 0 ? v : null
  },
  { immediate: true },
)

watch(
  () => activeConfig.value?.knowledge_base_ids,
  async (ids) => {
    const key = (ids ?? []).join(',')
    if (key === prevKbIdsKey) {
      return
    }
    prevKbIdsKey = key
    if (!activeConfig.value || !ids?.length || kbs.value.length === 0) {
      return
    }
    const want = topKFromKnowledgeBases(ids, kbs.value)
    const cur = clampChatRetrievalTopK(activeConfig.value.retrieval_top_k ?? DEFAULT_CHAT_TOP_K)
    if (want === cur) {
      return
    }
    skipTopKFromKbWatch.value = true
    chatTopK.value = want
    await updateConfig('retrieval_top_k', want)
    skipTopKFromKbWatch.value = false
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

/** 与后端 `DEFAULT_CHAT_SYSTEM_PROMPT_GENERAL` 一致；未保存自定义时后端按本轮是否有检索片段在通用/RAG 模板间选择 */
const DEFAULT_CHAT_SYSTEM_PROMPT =
  '你是一个乐于助人的智能助手。请结合聊天历史自然回答用户问题。\n' +
  '当前对话未选择知识库，或本轮检索未返回任何参考片段：请按通用对话方式回复，不必强行关联知识库或编造文档来源。'

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

const DEFAULT_MAX_HISTORY_MESSAGES = 20

function clampMaxHistoryMessages(n: unknown): number {
  const v = typeof n === 'number' ? n : Number(n)
  if (!Number.isFinite(v)) return DEFAULT_MAX_HISTORY_MESSAGES
  return Math.min(100, Math.max(0, Math.round(v)))
}

const chatMaxHistoryMessages = ref(DEFAULT_MAX_HISTORY_MESSAGES)

watch(
  () => activeConfig.value?.max_history_messages,
  (v) => {
    chatMaxHistoryMessages.value = clampMaxHistoryMessages(v ?? DEFAULT_MAX_HISTORY_MESSAGES)
  },
  { immediate: true },
)

const chatMaxHistorySliderStyle = computed(() => {
  const min = 0
  const max = 100
  const raw = Number.isFinite(chatMaxHistoryMessages.value) ? chatMaxHistoryMessages.value : min
  const clamped = Math.min(Math.max(raw, min), max)
  const pct = ((clamped - min) / (max - min)) * 100
  return { '--progress': `${pct.toFixed(2)}%` } as Record<string, string>
})

function onMaxHistoryMessagesCommit() {
  if (!activeConfig.value) return
  const v = clampMaxHistoryMessages(chatMaxHistoryMessages.value)
  chatMaxHistoryMessages.value = v
  const prev = clampMaxHistoryMessages(activeConfig.value.max_history_messages ?? DEFAULT_MAX_HISTORY_MESSAGES)
  if (v === prev) return
  void updateConfig('max_history_messages', v)
}

const chatMaxHistoryTokensDraft = ref('')

watch(
  () => activeConfig.value?.max_history_tokens,
  (v) => {
    chatMaxHistoryTokensDraft.value = v != null && v > 0 ? String(v) : ''
  },
  { immediate: true },
)

async function flushMaxHistoryTokens() {
  const remote = activeConfig.value?.max_history_tokens ?? null
  const raw = chatMaxHistoryTokensDraft.value.trim()
  let next: number | null = null
  if (raw !== '') {
    const n = parseInt(raw, 10)
    if (!Number.isFinite(n) || n < 1) {
      chatMaxHistoryTokensDraft.value = remote != null && remote > 0 ? String(remote) : ''
      return
    }
    next = Math.min(128000, n)
  }
  if (next === remote) return
  await chatStore.updateConfiguration({ max_history_tokens: next })
}

const openingGreetingDraft = ref('')
const emptyResponseDraft = ref('')

watch(
  () => activeConfig.value?.opening_greeting,
  (v) => {
    openingGreetingDraft.value = v != null ? String(v) : ''
  },
  { immediate: true },
)

watch(
  () => activeConfig.value?.empty_response,
  (v) => {
    emptyResponseDraft.value = v != null ? String(v) : ''
  },
  { immediate: true },
)

async function flushOpeningGreeting() {
  const remote = activeConfig.value?.opening_greeting ?? null
  const draftTrim = openingGreetingDraft.value.trim()
  const nextPayload: string | null = draftTrim === '' ? null : openingGreetingDraft.value
  if (nextPayload === remote) return
  await chatStore.updateConfiguration({ opening_greeting: nextPayload })
}

async function flushEmptyResponse() {
  const remote = activeConfig.value?.empty_response ?? null
  const draftTrim = emptyResponseDraft.value.trim()
  const nextPayload: string | null = draftTrim === '' ? null : emptyResponseDraft.value
  if (nextPayload === remote) return
  await chatStore.updateConfiguration({ empty_response: nextPayload })
}

function estimateMessageTokens(text: string): number {
  const s = text || ''
  return s.length > 0 ? Math.max(1, Math.floor(s.length / 4)) : 0
}

function countMessagesForModelWindow(
  messages: { role: string; content: string }[],
  maxMsgs: number,
  maxTokens: number | null | undefined,
): number {
  if (maxMsgs <= 0) return 0
  const slice = messages.slice(-maxMsgs)
  if (maxTokens == null || maxTokens <= 0) {
    return slice.length
  }
  let used = 0
  let count = 0
  for (let i = slice.length - 1; i >= 0; i -= 1) {
    const t = estimateMessageTokens(slice[i].content)
    if (used + t > maxTokens && count > 0) break
    used += t
    count += 1
  }
  return count
}

function resolveSelectedModelItem(c: typeof activeConfig.value): ModelItem | undefined {
  if (!c) return undefined
  const byId = c.model_id != null ? flatChatModels.value.find((x) => x.id === c.model_id) : undefined
  return (
    byId ??
    flatChatModels.value.find(
      (x) =>
        x.model_name === c.model_name?.trim() &&
        (!c.model_provider || x.provider_code === c.model_provider),
    )
  )
}

const selectedModelContextWindow = computed(
  () => resolveSelectedModelItem(activeConfig.value)?.context_window ?? null,
)

const selectedModelMaxOutputTokens = computed(
  () => resolveSelectedModelItem(activeConfig.value)?.max_output_tokens ?? null,
)

function clampChatTemperature(raw: unknown): number {
  const n = typeof raw === 'number' ? raw : Number(raw)
  if (!Number.isFinite(n)) return DEFAULT_CHAT_TEMPERATURE
  return Math.min(2, Math.max(0, Math.round(n * 10) / 10))
}

function clampChatMaxTokens(raw: unknown, max: number): number {
  const n = typeof raw === 'number' ? raw : Number(raw)
  if (!Number.isFinite(n)) return DEFAULT_CHAT_MAX_TOKENS
  const hi = Math.max(100, max)
  return Math.min(hi, Math.max(100, Math.round(n)))
}

function clampChatTopP(raw: unknown): number {
  const n = typeof raw === 'number' ? raw : Number(raw)
  if (!Number.isFinite(n)) return DEFAULT_CHAT_TOP_P
  return Math.min(1, Math.max(0.05, Math.round(n * 100) / 100))
}

const chatTemperature = ref(DEFAULT_CHAT_TEMPERATURE)
const chatMaxTokens = ref(DEFAULT_CHAT_MAX_TOKENS)
const chatTopP = ref(DEFAULT_CHAT_TOP_P)

const chatMaxTokensSliderMax = computed(() => {
  const ceiling = CHAT_MAX_TOKENS_SLIDER_CEILING
  const out = selectedModelMaxOutputTokens.value
  if (out != null && out > 0) {
    return Math.min(Math.max(out, 256), ceiling)
  }
  const ctx = selectedModelContextWindow.value
  if (ctx != null && ctx > 0) {
    return Math.min(Math.max(ctx, 256), ceiling)
  }
  return ceiling
})

watch(chatMaxTokensSliderMax, (max) => {
  chatMaxTokens.value = clampChatMaxTokens(chatMaxTokens.value, max)
})

watch(
  () => activeConfig.value?.temperature,
  (v) => {
    chatTemperature.value = clampChatTemperature(v ?? DEFAULT_CHAT_TEMPERATURE)
  },
  { immediate: true },
)

watch(
  () => activeConfig.value?.max_tokens,
  (v) => {
    chatMaxTokens.value = clampChatMaxTokens(v ?? DEFAULT_CHAT_MAX_TOKENS, chatMaxTokensSliderMax.value)
  },
  { immediate: true },
)

watch(
  () => activeConfig.value?.top_p,
  (v) => {
    chatTopP.value = clampChatTopP(v ?? DEFAULT_CHAT_TOP_P)
  },
  { immediate: true },
)

const chatTemperatureSliderStyle = computed(() => {
  const min = 0
  const max = 2
  const clamped = clampChatTemperature(chatTemperature.value)
  const pct = ((clamped - min) / (max - min)) * 100
  return { '--progress': `${pct.toFixed(2)}%` } as Record<string, string>
})

const chatMaxTokensSliderStyle = computed(() => {
  const min = 100
  const max = chatMaxTokensSliderMax.value
  const clamped = clampChatMaxTokens(chatMaxTokens.value, max)
  const pct = ((clamped - min) / (max - min)) * 100
  return { '--progress': `${pct.toFixed(2)}%` } as Record<string, string>
})

const chatTopPSliderStyle = computed(() => {
  const min = 0.05
  const max = 1
  const clamped = clampChatTopP(chatTopP.value)
  const pct = ((clamped - min) / (max - min)) * 100
  return { '--progress': `${pct.toFixed(2)}%` } as Record<string, string>
})

async function onTemperatureEnabledChange(enabled: boolean) {
  await updateConfig('temperature_enabled', enabled)
  if (enabled) {
    await onTemperatureCommit()
  }
}

async function onMaxTokensEnabledChange(enabled: boolean) {
  await updateConfig('max_tokens_enabled', enabled)
  if (enabled) {
    await onMaxTokensCommit()
  }
}

async function onTopPEnabledChange(enabled: boolean) {
  await updateConfig('top_p_enabled', enabled)
  if (enabled) {
    await onTopPCommit()
  }
}

async function onTemperatureCommit() {
  if (activeConfig.value?.temperature_enabled !== true) {
    return
  }
  const v = clampChatTemperature(chatTemperature.value)
  chatTemperature.value = v
  const prev = clampChatTemperature(activeConfig.value.temperature ?? DEFAULT_CHAT_TEMPERATURE)
  if (v === prev) {
    return
  }
  await updateConfig('temperature', v)
}

async function onMaxTokensCommit() {
  if (activeConfig.value?.max_tokens_enabled !== true) {
    return
  }
  const max = chatMaxTokensSliderMax.value
  const v = clampChatMaxTokens(chatMaxTokens.value, max)
  chatMaxTokens.value = v
  const prev = clampChatMaxTokens(activeConfig.value.max_tokens ?? DEFAULT_CHAT_MAX_TOKENS, max)
  if (v === prev) {
    return
  }
  await updateConfig('max_tokens', v)
}

async function onTopPCommit() {
  if (activeConfig.value?.top_p_enabled !== true) {
    return
  }
  const v = clampChatTopP(chatTopP.value)
  chatTopP.value = v
  const prev = clampChatTopP(activeConfig.value.top_p ?? DEFAULT_CHAT_TOP_P)
  if (v === prev) {
    return
  }
  await updateConfig('top_p', v)
}

const memoryHintVisible = computed(() => {
  const displayed = activeMessages.value.length
  const maxMsgs = clampMaxHistoryMessages(activeConfig.value?.max_history_messages ?? DEFAULT_MAX_HISTORY_MESSAGES)
  const modelUsed = countMessagesForModelWindow(
    activeMessages.value,
    maxMsgs,
    activeConfig.value?.max_history_tokens,
  )
  return displayed > modelUsed
})

const memoryHintText = computed(() => {
  const displayed = activeMessages.value.length
  const maxMsgs = clampMaxHistoryMessages(activeConfig.value?.max_history_messages ?? DEFAULT_MAX_HISTORY_MESSAGES)
  const modelUsed = countMessagesForModelWindow(
    activeMessages.value,
    maxMsgs,
    activeConfig.value?.max_history_tokens,
  )
  let text = `界面可见 ${displayed} 条消息，模型推理使用最近 ${modelUsed} 条对话记忆（窗口上限 ${maxMsgs} 条）`
  const ctx = selectedModelContextWindow.value
  if (ctx != null && ctx > 0) {
    text += `；当前模型上下文约 ${ctx.toLocaleString()} tokens`
  }
  return text
})

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

async function pickSidePanelModel(m: ModelItem) {
  await updateConfig('model_name', m)
  sidePanelModelMenuOpen.value = false
}

async function pickHeaderModel(m: ModelItem) {
  await updateConfig('model_name', m)
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

const apiBaseUrl = computed(() => resolveApiBaseUrl())

const chatPageUrl = computed(() =>
  typeof window !== 'undefined' ? `${window.location.origin}/chat` : '/chat',
)

const chatEmbedPageUrl = computed(() =>
  typeof window !== 'undefined' ? `${window.location.origin}/chat/embed` : '/chat/embed',
)

/** 带 api_key、space、可选 conversation_id 的嵌入入口完整 URL（用于 iframe / 气泡 src） */
const embedFullChatEmbedUrl = computed(() => {
  const base = chatEmbedPageUrl.value
  const space = encodeURIComponent(authStore.currentSpaceSlug || 'default')
  const k = embedApiKeyPlaintext.value?.trim()
  const cid = chatStore.activeConversationId?.trim()
  const convSuffix = cid ? `&conversation_id=${encodeURIComponent(cid)}` : ''
  const panelSuffix = '&embed_panel=1'
  if (k) {
    return `${base}?api_key=${encodeURIComponent(k)}&space=${space}${convSuffix}${panelSuffix}`
  }
  return `${base}?api_key=YOUR_EMBED_API_KEY&space=${space}${convSuffix}${panelSuffix}`
})

const embedWidgetScriptUrl = computed(() =>
  typeof window !== 'undefined'
    ? `${window.location.origin}/embed/zs-rag-chat-widget.js`
    : '/embed/zs-rag-chat-widget.js',
)

const embedIframeSnippet = computed(() => {
  const u = embedFullChatEmbedUrl.value
  return `<iframe
 src="${u}"
 title="知识对话"
 style="width: 100%; height: 100%; min-height: 700px"
 frameborder="0"
 allow="microphone; clipboard-read; clipboard-write">
</iframe>`
})

const embedBubbleSnippet = computed(() => {
  const u = embedFullChatEmbedUrl.value
  const scr = embedWidgetScriptUrl.value
  return [
    '<script>',
    'window.zsRagChatEmbedConfig = {',
    `  src: '${u}', // api_key / space 须与嵌入入口一致；服务端代理 Bearer 时不要写死在前端`,
    '  // bubbleColor: "#1C64F2",',
    '  // panelWidth: "24rem",',
    '  // panelHeight: "40rem",',
    '  // allowMicrophone: true,',
    '}',
    '<\/script>',
    `<script src="${scr}" defer><\/script>`,
    '<style>',
    '  #zs-rag-chat-embed-button {',
    '    background-color: #1C64F2 !important;',
    '  }',
    '  #zs-rag-chat-embed-window {',
    '    width: 24rem !important;',
    '    height: 40rem !important;',
    '  }',
    '</style>',
  ].join('\n')
})

const currentEmbedSnippet = computed(() =>
  embedMethod.value === 'iframe' ? embedIframeSnippet.value : embedBubbleSnippet.value,
)

const chatApiAccessCtx = computed<ChatApiAccessContext>(() => ({
  apiBaseUrl: apiBaseUrl.value,
  chatId: chatStore.activeConversationId != null ? String(chatStore.activeConversationId) : '',
  sessionId: chatStore.activeSessionId != null ? String(chatStore.activeSessionId) : '',
  spaceSlug: authStore.currentSpaceSlug || 'default',
}))

const apiAccessModalSubtitle = computed(() => {
  if (apiAccessMode.value === 'openai') {
    return 'OpenAI 兼容 Chat Completions（与官方 SDK / curl 用法一致）'
  }
  return 'zs-rag 原生接入：对话级自动建会话 + 会话级多轮（共 2 个接口）'
})

const zsRagChatLevelPath = computed(() => {
  const base = chatApiAccessCtx.value.apiBaseUrl.replace(/\/$/, '')
  const chatId = chatApiAccessCtx.value.chatId.trim() || '<chat_id>'
  return `${base}/api/v1/chats/${chatId}/stream`
})

const zsRagSessionApiPath = computed(() => {
  const base = chatApiAccessCtx.value.apiBaseUrl.replace(/\/$/, '')
  const sid = chatApiAccessCtx.value.sessionId.trim() || '<session_id>'
  if (zsRagSessionStream.value) {
    return `${base}/api/v1/chats/sessions/${sid}/stream`
  }
  return `${base}/api/v1/chats/sessions/${sid}/complete`
})

const zsRagChatLevelCurl = computed(() => buildZsRagChatLevelCurl(chatApiAccessCtx.value))

const zsRagSessionCurlExample = computed(() => {
  const ctx = chatApiAccessCtx.value
  if (zsRagSessionStream.value) {
    return buildZsRagSessionStreamCurl(ctx)
  }
  return buildZsRagSessionCompletionCurl(ctx)
})

const zsRagChatLevelResponseExample = computed(() =>
  buildZsRagSseResponseExample(chatApiAccessCtx.value, { newSession: true }),
)

const zsRagSessionResponseExample = computed(() => {
  const ctx = chatApiAccessCtx.value
  if (zsRagSessionStream.value) {
    return buildZsRagSseResponseExample(ctx)
  }
  return buildZsRagCompleteResponseExample(ctx)
})

const openAiBaseUrlDisplay = computed(() =>
  buildOpenAiChatCompletionsBaseUrl(chatApiAccessCtx.value.apiBaseUrl, chatApiAccessCtx.value.chatId),
)

const openAiParamChatId = computed(() => chatApiAccessCtx.value.chatId.trim() || '<chat_id>')
const openAiParamSessionId = computed(() => chatApiAccessCtx.value.sessionId.trim() || '<session_id>')

const openAiApiKeyDisplay = computed(() => {
  const key = embedApiKeyPlaintext.value?.trim()
  if (key) return key
  if (embedKeyEnsureLoading.value) return '正在准备 API Key…'
  return '<API Key>'
})

const openAiCodeExample = computed(() => {
  const ctx = chatApiAccessCtx.value
  const stream = openAiCurlStream.value
  if (openAiClientLang.value === 'python') {
    return buildOpenAiAccessPython(ctx, { stream })
  }
  return buildOpenAiAccessCurl(ctx, { stream })
})

const openAiResponseExample = computed(() => {
  const ctx = chatApiAccessCtx.value
  return openAiCurlStream.value
    ? buildOpenAiStreamResponseExample(ctx)
    : buildOpenAiNonStreamResponseExample(ctx)
})

function closeApiAccessDropdowns() {
  apiAccessModeMenuOpen.value = false
  openAiClientLangMenuOpen.value = false
}

function toggleOpenAiClientLangMenu() {
  openAiClientLangMenuOpen.value = !openAiClientLangMenuOpen.value
}

function pickOpenAiClientLang(lang: OpenAiClientLang) {
  openAiClientLang.value = lang
  openAiClientLangMenuOpen.value = false
}

function toggleApiAccessModeMenu() {
  apiAccessModeMenuOpen.value = !apiAccessModeMenuOpen.value
}

function pickApiAccessMode(mode: ApiAccessMode) {
  apiAccessMode.value = mode
  apiAccessModeMenuOpen.value = false
  if (mode === 'openai' && showAccessModal.value) {
    void ensureEmbedApiKey()
  }
}

function openApiAccessModal() {
  apiAccessMode.value = 'zs-rag'
  apiAccessModeMenuOpen.value = false
  openAiClientLang.value = 'http'
  openAiClientLangMenuOpen.value = false
  zsRagSessionStream.value = true
  showAccessModal.value = true
}

watch(showAccessModal, (open) => {
  if (!open) {
    apiAccessModeMenuOpen.value = false
    openAiClientLangMenuOpen.value = false
    return
  }
  void ensureEmbedApiKey()
})

async function copyText(text: string) {
  if (!text) return
  const ok = await copyToClipboard(text)
  if (!ok) {
    alert('复制失败，请手动选择文本')
  }
}

function copyEmbedChatId() {
  if (!embedConversationId.value) return
  copyText(embedConversationId.value)
}

async function onDownloadChatApiDoc() {
  if (chatApiDocDownloading.value) return
  chatApiDocDownloading.value = true
  try {
    await downloadChatApiDoc(chatApiAccessCtx.value)
  } catch (e) {
    alert(e instanceof Error ? e.message : '下载失败')
  } finally {
    chatApiDocDownloading.value = false
  }
}

async function onDownloadOpenAiExampleDoc() {
  if (chatApiDocDownloading.value) return
  chatApiDocDownloading.value = true
  try {
    await downloadOpenAiExampleDoc()
  } catch (e) {
    alert(e instanceof Error ? e.message : '下载失败')
  } finally {
    chatApiDocDownloading.value = false
  }
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

async function onDeleteSessionFromMenu(session: ChatSession) {
  sessionMenuOpenId.value = null
  if (isDeleting.value) return
  isDeleting.value = true
  try {
    await chatStore.deleteSession(session.id)
  } catch (e) {
    console.error('Delete session failed', e)
  } finally {
    isDeleting.value = false
  }
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
  const q = route.query.conversation_id
  const cid = typeof q === 'string' ? q : Array.isArray(q) && typeof q[0] === 'string' ? q[0] : ''
  if (cid) {
    const exists = chatStore.conversations.some((c) => c.id === cid)
    if (exists) {
      await chatStore.selectConversation(cid)
    }
    const nextQuery: Record<string, string> = {}
    const ep = route.query.embed_panel
    if (ep === '1' || ep === 'true') {
      nextQuery.embed_panel = '1'
    }
    await router.replace({ path: '/chat', query: nextQuery })
  }
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
  clearPageContext()
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
  suggestedQuestions.value = []
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
  suggestedQuestions.value = []

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
    chatStore.setGenerating(false)
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

const updateConfig = async (key: string, value: any) => {
  if (activeConfig.value) {
    if (key === 'model_name') {
      let selected: ModelItem | undefined
      if (value != null && typeof value === 'object' && 'provider_code' in value && 'model_name' in value) {
        selected = value as ModelItem
      } else if (typeof value === 'string') {
        selected = parseModelOptionValue(value)
      }
      if (selected) {
        await chatStore.updateConfiguration({
          model_id: selected.id,
          model_name: selected.model_name,
          model_provider: selected.provider_code,
        })
      }
    } else {
      await chatStore.updateConfiguration({ [key]: value })
    }
  }
}

function onChatChunkTopKCommit() {
  if (!activeConfig.value) return
  const raw = chatChunkTopK.value
  const next =
    typeof raw === 'number' && Number.isFinite(raw) && raw > 0
      ? Math.min(100, Math.max(1, Math.round(raw)))
      : null
  chatChunkTopK.value = next
  const prev =
    typeof activeConfig.value.lightrag_chunk_top_k === 'number' && activeConfig.value.lightrag_chunk_top_k > 0
      ? activeConfig.value.lightrag_chunk_top_k
      : null
  if (next === prev) {
    return
  }
  void updateConfig('lightrag_chunk_top_k', next)
}

function onChatTopKCommit() {
  if (!activeConfig.value) return
  const v = clampChatRetrievalTopK(chatTopK.value)
  chatTopK.value = v
  const prev = clampChatRetrievalTopK(activeConfig.value.retrieval_top_k ?? DEFAULT_CHAT_TOP_K)
  if (v === prev) {
    return
  }
  void (async () => {
    await updateConfig('retrieval_top_k', v)
    const ids = activeConfig.value?.knowledge_base_ids ?? []
    if (ids.length > 0 && kbs.value.length > 0) {
      const refreshed = await syncTopKToKnowledgeBases(ids, v, kbs.value)
      for (const kb of refreshed) {
        const i = kbs.value.findIndex((k) => k.id === kb.id)
        if (i >= 0) {
          kbs.value[i] = kb
        }
      }
    }
  })()
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
  background: var(--brand-primary);
  color: #ffffff;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}

.btn-embed-site:hover {
  background: var(--brand-primary-hover);
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

.modal-embed {
  max-width: 820px;
}

.embed-modal-lead {
  margin: 6px 0 0;
  font-size: 0.88rem;
  color: var(--text-secondary);
  line-height: 1.45;
}

.embed-security-warning {
  margin: 0 0 18px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(245, 158, 11, 0.45);
  background: rgba(245, 158, 11, 0.08);
  font-size: 0.86rem;
  line-height: 1.55;
  color: var(--text-primary);
}

.embed-security-warning strong {
  color: var(--danger-color, #b91c1c);
}

.embed-security-warning code {
  font-size: 0.82rem;
}

.embed-method-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin: 0 0 20px;
}

.embed-method-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 14px 16px;
  border: 2px solid var(--border-color);
  border-radius: 16px;
  background: linear-gradient(165deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.embed-method-card:hover {
  border-color: rgba(28, 100, 242, 0.35);
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.07);
}

.embed-method-card--active {
  border-color: var(--brand-primary);
  box-shadow:
    0 0 0 3px var(--brand-primary-light),
    0 14px 32px rgba(28, 100, 242, 0.14);
}

.embed-method-selected-mark {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 999px;
  background: var(--brand-primary);
  color: #fff;
  box-shadow: 0 2px 10px rgba(28, 100, 242, 0.35);
}

.embed-method-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-primary);
  padding-right: 30px;
}

.embed-method-desc {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.45;
}

.embed-method-thumb {
  position: relative;
  height: 100px;
  margin-bottom: 2px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: linear-gradient(180deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.45);
}

.emb-browser-chrome {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 18px;
  padding: 0 8px;
  background: rgba(0, 0, 0, 0.05);
  border-bottom: 1px solid var(--border-color);
}

.emb-browser-chrome--mini {
  height: 14px;
}

.emb-dot {
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.14);
}

.embed-method-thumb--iframe .emb-browser-body {
  display: flex;
  height: calc(100% - 18px);
  padding: 8px;
  gap: 8px;
}

.emb-sidebar {
  width: 18%;
  flex-shrink: 0;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.06);
}

.emb-chat-pane {
  flex: 1;
  border-radius: 10px;
  border: 1px solid rgba(28, 100, 242, 0.22);
  background: linear-gradient(165deg, #e8f1fe 0%, #cfe2fd 50%, #dbeafe 100%);
  box-shadow: 0 2px 10px rgba(28, 100, 242, 0.1);
}

.embed-method-thumb--bubble .emb-page-canvas {
  position: absolute;
  left: 8px;
  right: 8px;
  top: 22px;
  bottom: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 10px 40px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.4);
}

.emb-line {
  height: 5px;
  width: 100%;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.07);
}

.emb-line--short {
  width: 62%;
}

.emb-bubble-fab {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 3;
  width: 36px;
  height: 36px;
  border-radius: 999px;
  background: linear-gradient(145deg, #3b82f6, #1c64f2);
  box-shadow:
    0 4px 16px rgba(28, 100, 242, 0.42),
    0 0 0 3px rgba(255, 255, 255, 0.9);
}

.embed-key-panel {
  margin-bottom: 20px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.embed-field-hint {
  margin: 8px 0 0;
  font-size: 0.78rem;
  line-height: 1.45;
  color: var(--text-secondary);
}

.embed-field-hint--error {
  color: var(--danger-color);
}

.embed-field-hint code {
  font-size: 0.76rem;
}

.embed-key-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}

.embed-key-meta {
  margin: 0 0 10px;
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.45;
}

.embed-key-meta--inline {
  margin-bottom: 8px;
}

.embed-key-meta--error {
  margin-bottom: 10px;
  color: var(--danger-color);
}

.embed-key-hint {
  flex: 1;
  min-width: 180px;
  font-size: 0.8rem;
  line-height: 1.45;
  color: var(--text-secondary);
}

.embed-key-block {
  margin-bottom: 0;
}

.embed-snippet-hint {
  margin: 0 0 8px;
  font-size: 0.84rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.embed-snippet-hint code {
  font-size: 0.8rem;
}

.embed-snippet-pre {
  max-height: min(280px, 38vh);
  overflow: auto;
}

.embed-snippet-block {
  margin-bottom: 16px;
}

@media (max-width: 560px) {
  .embed-method-grid {
    grid-template-columns: 1fr;
  }
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

.openai-access-id-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.openai-access-id-panel .access-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.openai-field-tag {
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--danger-color, #dc2626);
}

.openai-field-tag--optional {
  color: var(--text-secondary);
}

.openai-access-id-panel .embed-key-block {
  margin-bottom: 0;
}

.openai-access-example {
  margin-bottom: 18px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  background: var(--bg-secondary);
}

.openai-access-example-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.openai-access-example-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-primary);
}

.openai-access-example-icon {
  flex-shrink: 0;
  color: var(--text-tertiary);
}

.openai-access-example-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.openai-access-tabs {
  display: inline-flex;
  padding: 2px;
  border-radius: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
}

.openai-access-tab {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.78rem;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.openai-access-tab.is-active {
  background: var(--bg-primary, #fff);
  color: var(--text-primary);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.openai-access-example .access-pre--code {
  border: none;
  border-radius: 0;
  background: transparent;
}

.api-access-response-section {
  border-top: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.api-access-response-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--border-color);
}

.api-access-response-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}

.api-access-response-meta {
  font-size: 0.75rem;
  color: var(--text-secondary);
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
}

.api-access-response-head .openai-access-copy-btn {
  margin-left: auto;
}

.api-access-response-body {
  margin: 0;
  max-height: min(260px, 34vh);
  overflow: auto;
}

.openai-access-code {
  max-height: min(320px, 42vh);
  overflow: auto;
}

.openai-access-lang-picker {
  position: relative;
  flex-shrink: 0;
}

.openai-access-lang-picker--open {
  z-index: 30;
}

.openai-access-lang-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  margin: 0;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--text-primary);
  font: inherit;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.openai-access-lang-trigger:hover {
  background: var(--bg-primary);
}

.openai-access-lang-trigger-label {
  min-width: 3.2rem;
  text-align: left;
}

.openai-access-lang-chevron {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform 0.15s ease;
}

.openai-access-lang-chevron.is-open {
  transform: rotate(180deg);
}

.openai-access-lang-dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  z-index: 50;
  min-width: 120px;
}

.openai-access-lang-list {
  padding: 4px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary, #f8fafc);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
}

.openai-access-lang-option {
  display: block;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-primary);
  font: inherit;
  font-size: 0.82rem;
  text-align: left;
  cursor: pointer;
}

.openai-access-lang-option:hover {
  background: var(--bg-tertiary);
}

.openai-access-lang-option.is-current {
  background: var(--bg-primary);
  font-weight: 600;
}

.openai-access-copy-btn {
  padding: 4px 6px !important;
  min-width: 32px;
}

.openai-access-notes {
  margin: 0;
  padding-left: 1.2rem;
  color: var(--text-secondary);
  font-size: 0.84rem;
  line-height: 1.55;
}

.openai-access-notes li + li {
  margin-top: 6px;
}

.openai-access-doc-link {
  margin: 12px 0 0;
  font-size: 0.84rem;
  color: var(--text-secondary);
}

.btn-link-inline {
  padding: 0 !important;
  font-size: inherit;
  vertical-align: baseline;
}

.zs-rag-access-api {
  margin-bottom: 20px;
}

.zs-rag-access-api .access-section-title {
  margin-top: 0;
}

.zs-rag-access-path {
  font-size: 0.78rem;
  word-break: break-all;
}

.openai-access-example-title .api-method {
  margin-right: 8px;
}

.openai-access-link {
  color: var(--brand-primary);
  text-decoration: none;
}

.openai-access-link:hover {
  text-decoration: underline;
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

.modal-api-access .modal-header {
  align-items: flex-start;
}

.modal-api-access .modal-header > div:first-child {
  min-width: 0;
  flex: 1;
}

.modal-header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.btn-download-doc {
  white-space: nowrap;
}

.modal-subtitle {
  margin: 4px 0 0;
  font-size: 0.82rem;
  font-weight: 400;
  color: var(--text-secondary);
}

.api-access-mode-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.api-access-mode-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}

.api-access-mode-picker {
  position: relative;
  width: 100%;
  max-width: 360px;
}

.api-access-mode-picker--open {
  z-index: 20;
}

.api-access-mode-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 14px;
  margin: 0;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  color: var(--text-primary);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
  box-sizing: border-box;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.api-access-mode-trigger:hover {
  border-color: rgba(100, 116, 139, 0.45);
  background: var(--bg-secondary);
}

.api-access-mode-trigger-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.api-access-mode-chevron {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform 0.15s ease;
}

.api-access-mode-chevron.is-open {
  transform: rotate(180deg);
}

.api-access-mode-dropdown {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 6px);
  z-index: 50;
}

.api-access-mode-list {
  width: 100%;
  max-height: 240px;
  overflow-y: auto;
  padding: 8px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary, #f8fafc);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.65),
    0 10px 28px rgba(15, 23, 42, 0.12);
}

.api-access-mode-option {
  display: flex;
  align-items: center;
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

.api-access-mode-option:hover {
  background: var(--brand-primary-light, rgba(37, 99, 235, 0.08));
}

.api-access-mode-option.is-current {
  background: rgba(37, 99, 235, 0.12);
}

.api-access-mode-option-name {
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.3;
}

.access-muted-tight {
  margin-top: 6px;
  margin-bottom: 0;
}

.api-access-group {
  margin-bottom: 8px;
}

.api-access-endpoint {
  margin: 0 0 14px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.api-access-endpoint-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 10px;
  margin-bottom: 6px;
}

.api-method {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 0.72rem;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  letter-spacing: 0.02em;
}

.api-method--get {
  background: rgba(34, 197, 94, 0.15);
  color: #16a34a;
}

.api-method--post {
  background: rgba(59, 130, 246, 0.15);
  color: #2563eb;
}

.api-method--put {
  background: rgba(234, 179, 8, 0.18);
  color: #ca8a04;
}

.api-method--delete {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
}

.api-access-path {
  flex: 1;
  min-width: 0;
  font-size: 0.76rem;
  word-break: break-all;
}

.api-access-endpoint-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-left: auto;
}

.api-access-summary {
  margin: 0;
  font-size: 0.84rem;
  color: var(--text-primary);
  line-height: 1.5;
}

.api-access-body {
  margin-top: 10px;
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

.page-shell.chat-view.page-shell--embed-panel {
  gap: 0;
}

.chat-layout.chat-layout--embed-panel:not(.chat-layout--settings-open) {
  grid-template-columns: minmax(0, 1fr);
}

.chat-layout.chat-layout--embed-panel.chat-layout--settings-open {
  grid-template-columns: minmax(0, 1fr) minmax(300px, 380px);
}

.chat-embed-panel-fallback {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
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

.chat-memory-hint {
  flex-shrink: 0;
  margin: 0 4px 8px;
  padding: 8px 12px;
  border-radius: 10px;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.35);
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.45;
}

.section-subtext {
  margin: 4px 0 0;
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.4;
  font-weight: 400;
}

.chat-suggest-questions {
  flex-shrink: 0;
  padding: 4px 4px 10px;
}

.chat-suggest-questions-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.chat-suggest-questions-divider::before,
.chat-suggest-questions-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-color);
}

.chat-suggest-questions-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.chat-suggest-question-chip {
  padding: 8px 14px;
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 999px;
  background: #fff;
  color: var(--brand-primary, #2563eb);
  font-size: 0.88rem;
  line-height: 1.3;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.chat-suggest-question-chip:hover {
  background: var(--brand-primary-light, rgba(37, 99, 235, 0.08));
  border-color: rgba(59, 130, 246, 0.45);
}

.chat-suggest-settings-card {
  padding: 12px 14px;
}

.chat-suggest-setting-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 36px;
}

.chat-suggest-setting-icon {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--brand-primary, #2563eb);
  color: #fff;
}

.chat-suggest-setting-text {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
}

.chat-suggest-setting-title {
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
}

.chat-suggest-setting-gear {
  flex-shrink: 0;
  padding: 6px;
}

.chat-suggest-setting-switch {
  flex-shrink: 0;
}

.chat-model-params {
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow: visible;
}

.chat-model-params-heading {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-primary);
}

.chat-model-param-row {
  display: grid;
  grid-template-columns: auto minmax(52px, max-content) minmax(0, 1fr) 80px;
  align-items: center;
  gap: 8px 8px;
  overflow: visible;
}

.chat-model-param-switch {
  flex-shrink: 0;
}

.chat-model-param-switch .chat-switch-track {
  width: 32px;
  height: 18px;
}

.chat-model-param-switch .chat-switch-track::after {
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
}

.chat-model-param-switch .chat-switch input:checked + .chat-switch-track::after {
  transform: translateX(14px);
}

.chat-model-param-label {
  font-size: 0.86rem;
  font-weight: 500;
  white-space: nowrap;
}

.chat-model-param-label.chat-field-label-block {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: auto;
  max-width: none;
  margin-bottom: 0;
}

.chat-model-param-label .chat-field-hint-wrap {
  position: relative;
}

.chat-model-param-label .chat-field-hint-tooltip {
  left: 50%;
  right: auto;
  width: min(268px, calc(100vw - 48px));
  max-width: min(268px, calc(100vw - 48px));
  transform: translateX(-50%) translateY(4px);
}

.chat-model-param-label .chat-field-hint-tooltip::after {
  left: 50%;
  right: auto;
  margin-left: -5px;
  background: #fff;
  border: 1px solid var(--border-color, #e5e7eb);
  border-bottom: none;
  border-right: none;
}

.chat-model-param-label.chat-field-label-block:hover .chat-field-hint-tooltip,
.chat-model-param-label.chat-field-label-block:focus-within .chat-field-hint-tooltip {
  transform: translateX(-50%) translateY(0);
}

.chat-model-param-range {
  --progress: 0%;
  --progress-color: var(--brand-primary, #3b82f6);
  --progress-track: rgba(59, 130, 246, 0.12);
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
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

.chat-model-param-range:disabled {
  cursor: not-allowed;
}

.chat-model-param-range::-webkit-slider-runnable-track {
  height: 6px;
  border-radius: 999px;
  background: transparent;
}

.chat-model-param-range::-moz-range-track {
  height: 6px;
  border-radius: 999px;
  background: transparent;
}

.chat-model-param-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 8px;
  height: 18px;
  margin-top: -6px;
  border-radius: 4px;
  background: #ffffff;
  border: 1px solid var(--border-strong, #d1d5db);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.15);
  cursor: pointer;
}

.chat-model-param-range::-moz-range-thumb {
  width: 8px;
  height: 18px;
  border-radius: 4px;
  background: #ffffff;
  border: 1px solid var(--border-strong, #d1d5db);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.15);
  cursor: pointer;
}

.chat-model-param-number {
  width: 80px;
  min-width: 0;
  padding: 6px 6px;
  text-align: center;
  background: var(--bg-secondary, #f3f4f6);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 0.84rem;
}

.chat-model-param-number:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.chat-model-param-row.is-disabled .chat-model-param-range {
  opacity: 0.45;
  cursor: not-allowed;
}

.chat-system-prompt-card h4.chat-field-label-block,
.chat-suggest-setting-title.chat-field-label-block {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  width: auto;
  max-width: none;
  margin-bottom: 0;
}

.chat-suggest-setting-title .chat-field-hint-wrap {
  position: relative;
}

.chat-suggest-setting-title .chat-field-hint-tooltip {
  left: 0;
  right: auto;
  width: min(268px, calc(100vw - 48px));
  max-width: min(268px, calc(100vw - 48px));
}

.modal-content.chat-suggest-modal {
  max-width: 520px;
  width: min(calc(100vw - 32px), 520px);
  max-height: min(88vh, 620px);
  padding: 20px;
}

.modal-content.chat-suggest-modal .modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.chat-suggest-modal-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  flex: 1 1 auto;
  min-height: 0;
}

.chat-suggest-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.chat-suggest-prompt-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-suggest-prompt-card {
  display: block;
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-primary);
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.chat-suggest-prompt-card.is-selected {
  border-color: var(--brand-primary, #2563eb);
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.15);
}

.chat-suggest-prompt-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.chat-suggest-prompt-card-title {
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--text-primary);
}

.chat-suggest-prompt-card-radio {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--border-color);
  flex-shrink: 0;
}

.chat-suggest-prompt-card.is-selected .chat-suggest-prompt-card-radio {
  border-color: var(--brand-primary, #2563eb);
  box-shadow: inset 0 0 0 3px var(--brand-primary, #2563eb);
}

.chat-suggest-prompt-card-desc {
  margin: 0 0 10px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.45;
}

.chat-suggest-prompt-preview {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary, #f9fafb);
  color: var(--text-primary);
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 400;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-suggest-prompt-custom {
  width: 100%;
  box-sizing: border-box;
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

/* 下拉浮层已 Teleport 到 body（fixed 定位），不再需要放开容器 overflow，
   否则会把可滚动的设置面板内容整段铺开。保持 overflow-y:auto 即可。 */
.chat-settings-panel.chat-settings-panel--kb-open {
  z-index: 12;
}

.chat-settings-panel:has(.kb-select--open) {
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
  display: block;
  width: 100%;
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
  color: var(--text-secondary);
  background: #fff;
  border: 1px solid var(--border-color);
  cursor: help;
  vertical-align: middle;
}

.chat-field-hint-wrap:hover .chat-topk-help,
.chat-field-hint-wrap:focus .chat-topk-help {
  color: var(--text-primary);
  border-color: rgba(59, 130, 246, 0.35);
}

.chat-field-label-block {
  position: relative;
  display: block;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  margin-bottom: 8px;
}

.chat-field-hint-wrap {
  display: inline-flex;
  vertical-align: middle;
  margin-left: 4px;
}

.chat-field-hint-tooltip {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: 200;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff;
  color: var(--text-primary, #111827);
  border: 1px solid var(--border-color, #e5e7eb);
  font-size: 0.78rem;
  font-weight: 400;
  line-height: 1.55;
  box-shadow:
    0 4px 16px rgba(15, 23, 42, 0.08),
    0 1px 3px rgba(15, 23, 42, 0.06);
  white-space: normal;
  word-break: break-word;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transform: translateY(4px);
  transition:
    opacity 0.16s ease,
    transform 0.16s ease,
    visibility 0.16s ease;
}

.chat-field-hint-tooltip::after {
  content: '';
  position: absolute;
  top: -5px;
  left: auto;
  right: 12px;
  width: 10px;
  height: 10px;
  background: #fff;
  border: 1px solid var(--border-color, #e5e7eb);
  border-bottom: none;
  border-right: none;
  transform: rotate(45deg);
}

.chat-field-label-block:hover .chat-field-hint-tooltip,
.chat-field-label-block:focus-within .chat-field-hint-tooltip {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
  transform: translateY(0);
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
  display: block;
  width: 100%;
  margin-bottom: 8px;
}

.chat-citation-toggle-head .field-label,
.chat-citation-toggle-head .chat-field-label-block {
  margin-bottom: 0;
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

.msg-citation-graph-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  line-height: 1.5;
  color: #7c3aed;
  background: rgba(168, 85, 247, 0.12);
  border: 1px solid rgba(168, 85, 247, 0.32);
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

  .chat-layout.chat-layout--embed-panel:not(.chat-layout--settings-open) {
    grid-template-columns: minmax(0, 1fr);
  }

  .chat-layout.chat-layout--embed-panel.chat-layout--settings-open {
    grid-template-columns: minmax(0, 1fr) minmax(280px, 340px);
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

.modal-header--embed {
  align-items: flex-start;
}

.modal-header--embed .btn {
  margin-top: 2px;
}

.modal-content > .modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
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