<template>
  <Layout>
    <div class="page-shell chat-view">
      <PageHeader
        eyebrow="RAG Assistant"
        title="企业知识对话工作台"
        description="以企业级知识助手的形式展示会话管理、答案生成与引用来源，让问答体验更接近正式后台产品，而非消费级聊天软件。"
      >
        <template #meta>
          <span class="chip chip-brand">知识助手</span>
          <span class="chip">{{ conversations.length }} 个会话</span>
          <span class="chip">引用可追溯</span>
        </template>
        <template #actions>
          <button class="btn btn-primary" type="button" @click="createConversation">
            <AppIcon name="plus" :size="16" />
            新建对话
          </button>
        </template>
      </PageHeader>

      <div class="chat-layout">
        <aside class="surface-card conversation-rail">
          <div class="section-heading compact-heading">
            <div>
              <h3>会话列表</h3>
              <p>按业务主题组织企业知识助手对话。</p>
            </div>
          </div>

          <div class="conversation-list">
            <button
              v-for="conversation in conversations"
              :key="conversation.id"
              class="conversation-item"
              :class="{ active: conversation.id === activeConversationId }"
              type="button"
              @click="activeConversationId = conversation.id"
            >
              <div class="conversation-item-top">
                <strong>{{ conversation.title }}</strong>
                <span class="status-pill" :class="conversation.id === activeConversationId ? 'info' : 'success'">
                  {{ conversation.status }}
                </span>
              </div>
              <p>{{ conversation.summary }}</p>
              <span class="conversation-time">{{ conversation.updatedAt }}</span>
            </button>
          </div>
        </aside>

        <section class="surface-card chat-main">
          <div class="chat-main-header">
            <div>
              <h3>{{ activeConversation?.title }}</h3>
              <p>{{ activeConversation?.summary }}</p>
            </div>
            <div class="chat-header-meta">
              <span class="chip chip-brand">
                <AppIcon name="models" :size="14" />
                默认 LLM 已接入
              </span>
              <span class="chip">
                <AppIcon name="knowledge" :size="14" />
                引用来源 {{ latestCitations.length }} 条
              </span>
            </div>
          </div>

          <div class="message-list">
            <article v-for="message in activeMessages" :key="message.id" class="message-card" :class="message.role">
              <div class="message-meta">
                <span class="message-role">{{ message.role === 'assistant' ? '知识助手' : '提问者' }}</span>
                <span>{{ message.timestamp }}</span>
              </div>
              <p class="message-content">{{ message.content }}</p>

              <div v-if="message.citations?.length" class="citation-list">
                <div v-for="citation in message.citations" :key="citation.title + citation.section" class="citation-card">
                  <strong>{{ citation.title }}</strong>
                  <p>{{ citation.knowledgeBase }} · {{ citation.section }}</p>
                </div>
              </div>
            </article>
          </div>

          <form class="composer" @submit.prevent="handleSend">
            <label class="field composer-field">
              <span class="field-label">输入问题</span>
              <textarea
                v-model="draftMessage"
                class="textarea"
                rows="4"
                placeholder="请输入你希望知识助手回答的问题，例如：默认模型配置完成后，如何开展知识库与检索链路的联调？"
              />
            </label>
            <div class="composer-actions">
              <span class="helper-text">回答将附带知识来源，适合企业内部审阅与验收。</span>
              <button class="btn btn-primary" type="submit" :disabled="!draftMessage.trim()">
                <AppIcon name="send" :size="16" />
                发送问题
              </button>
            </div>
          </form>
        </section>

        <aside class="side-panel">
          <section class="surface-card">
            <div class="section-heading compact-heading">
              <div>
                <h4>当前引用来源</h4>
                <p>最近一条助手回复使用到的知识片段。</p>
              </div>
            </div>
            <EmptyState
              v-if="latestCitations.length === 0"
              title="尚未产生引用"
              description="发送问题后，系统会在此展示答案关联的知识来源。"
              compact
            />
            <div v-else class="reference-list">
              <div v-for="citation in latestCitations" :key="citation.title + citation.section" class="reference-item">
                <span class="reference-icon">
                  <AppIcon name="knowledge" :size="16" />
                </span>
                <div>
                  <strong>{{ citation.title }}</strong>
                  <p>{{ citation.knowledgeBase }} · {{ citation.section }}</p>
                </div>
              </div>
            </div>
          </section>

          <section class="surface-card">
            <div class="section-heading compact-heading">
              <div>
                <h4>对话规范</h4>
                <p>企业级知识助手建议遵循的输出准则。</p>
              </div>
            </div>
            <div class="guideline-list">
              <div class="guideline-item">
                <AppIcon name="shield" :size="16" />
                <span>优先提供基于知识库的可验证结论，并保留引用来源。</span>
              </div>
              <div class="guideline-item">
                <AppIcon name="status" :size="16" />
                <span>当知识不足时，应明确标记为待确认，不应伪造业务答案。</span>
              </div>
              <div class="guideline-item">
                <AppIcon name="spark" :size="16" />
                <span>问题可继续追问，适合做方案澄清、流程说明与跨系统信息整合。</span>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  </Layout>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import Layout from '../components/Layout.vue'
import PageHeader from '../components/PageHeader.vue'

type Citation = {
  title: string
  knowledgeBase: string
  section: string
}

type Message = {
  id: number
  role: 'assistant' | 'user'
  content: string
  timestamp: string
  citations?: Citation[]
}

type Conversation = {
  id: string
  title: string
  summary: string
  status: string
  updatedAt: string
}

const conversations = ref<Conversation[]>([
  {
    id: 'ops',
    title: '平台运维问答',
    summary: '聚焦默认模型、知识库连接与系统健康相关问题。',
    status: '进行中',
    updatedAt: '刚刚更新',
  },
  {
    id: 'kb',
    title: '知识库建设咨询',
    summary: '用于梳理知识库分层与双库架构最佳实践。',
    status: '稳定',
    updatedAt: '15 分钟前',
  },
  {
    id: 'security',
    title: '权限与审计讨论',
    summary: '面向企业空间隔离、登录与审计策略的问题澄清。',
    status: '待跟进',
    updatedAt: '1 小时前',
  },
])

const messageStore = reactive<Record<string, Message[]>>({
  ops: [
    {
      id: 1,
      role: 'assistant',
      content: '建议优先完成默认模型配置，再逐步接入知识库与检索评估流程，这样可以确保后续问答链路具备稳定的模型基础。',
      timestamp: '09:20',
      citations: [
        { title: '默认模型编排与检索链路依赖', knowledgeBase: '模型管理操作指南', section: '默认模型 / 01' },
      ],
    },
    {
      id: 2,
      role: 'user',
      content: '如果我要按企业空间隔离知识库，应该先从哪里开始？',
      timestamp: '09:22',
    },
    {
      id: 3,
      role: 'assistant',
      content: '建议先确认企业空间列表与切换逻辑是否稳定，再为每个空间建立独立知识库配置，并确保接口请求统一透传企业空间上下文。',
      timestamp: '09:23',
      citations: [
        { title: '企业空间与知识库隔离策略', knowledgeBase: '平台治理手册', section: '空间治理 / 03' },
        { title: '知识库双库模式最佳实践', knowledgeBase: '知识资产建设方案', section: '架构设计 / 05' },
      ],
    },
  ],
  kb: [
    {
      id: 4,
      role: 'assistant',
      content: '知识库建设建议采用“知识治理、连接配置、检索验收”三步法，以便逐步完成资产清理、连接接入和效果验证。',
      timestamp: '昨天',
    },
  ],
  security: [
    {
      id: 5,
      role: 'assistant',
      content: '对于企业级场景，应优先明确空间隔离策略、敏感配置项保护和高风险操作确认机制。',
      timestamp: '昨天',
    },
  ],
})

const activeConversationId = ref('ops')
const draftMessage = ref('请总结默认模型配置完成后，下一步如何进行知识库与检索链路联调。')

const activeConversation = computed(() => conversations.value.find((item) => item.id === activeConversationId.value) || conversations.value[0])
const activeMessages = computed(() => messageStore[activeConversationId.value] || [])
const latestAssistantMessage = computed(() => [...activeMessages.value].reverse().find((item) => item.role === 'assistant'))
const latestCitations = computed(() => latestAssistantMessage.value?.citations || [])

const createAssistantReply = (question: string): Message => {
  const normalized = question.toLowerCase()

  if (normalized.includes('模型')) {
    return {
      id: Date.now() + 1,
      role: 'assistant',
      timestamp: '刚刚',
      content: '建议先确认默认 LLM 与 Embedding 是否已配置，再检查模型同步状态和启用状态，最后在检索页验证召回效果与引用完整性。',
      citations: [
        { title: '默认模型编排与检索链路依赖', knowledgeBase: '模型管理操作指南', section: '默认模型 / 01' },
      ],
    }
  }

  if (normalized.includes('权限') || normalized.includes('空间')) {
    return {
      id: Date.now() + 1,
      role: 'assistant',
      timestamp: '刚刚',
      content: '建议以企业空间为最小隔离单元，统一通过请求头传递空间标识，同时在知识库与系统设置中明确高风险操作的确认流程。',
      citations: [
        { title: '企业空间与知识库隔离策略', knowledgeBase: '平台治理手册', section: '空间治理 / 03' },
      ],
    }
  }

  return {
    id: Date.now() + 1,
    role: 'assistant',
    timestamp: '刚刚',
    content: '建议从“默认模型 -> 知识库连接 -> 检索验证 -> 对话验收”四个步骤串联联调，并记录每一步的输入、输出与引用来源。',
    citations: [
      { title: '检索质量验收指标模板', knowledgeBase: '运营验收标准', section: '检索评估 / 02' },
      { title: '知识库双库模式最佳实践', knowledgeBase: '知识资产建设方案', section: '架构设计 / 05' },
    ],
  }
}

const createConversation = () => {
  const id = `session-${Date.now()}`
  conversations.value.unshift({
    id,
    title: '新建对话',
    summary: '用于继续澄清新的业务问题。',
    status: '草稿',
    updatedAt: '刚刚创建',
  })
  messageStore[id] = [
    {
      id: Date.now(),
      role: 'assistant',
      content: '新的企业知识助手会话已创建，你可以继续输入需要梳理的问题。',
      timestamp: '刚刚',
    },
  ]
  activeConversationId.value = id
}

const handleSend = () => {
  const content = draftMessage.value.trim()
  if (!content) {
    return
  }

  const nextUserMessage: Message = {
    id: Date.now(),
    role: 'user',
    content,
    timestamp: '刚刚',
  }

  messageStore[activeConversationId.value] = [
    ...activeMessages.value,
    nextUserMessage,
    createAssistantReply(content),
  ]

  const index = conversations.value.findIndex((item) => item.id === activeConversationId.value)
  if (index >= 0) {
    conversations.value[index] = {
      ...conversations.value[index],
      summary: content,
      status: '进行中',
      updatedAt: '刚刚更新',
    }
  }

  draftMessage.value = ''
}
</script>

<style scoped>
.chat-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr) 320px;
  gap: 24px;
  align-items: start;
}

.conversation-rail,
.chat-main,
.side-panel {
  display: grid;
  gap: 18px;
}

.conversation-list,
.message-list,
.reference-list,
.guideline-list {
  display: grid;
  gap: 14px;
}

.conversation-item,
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

.conversation-item:hover {
  transform: translateY(-1px);
  border-color: var(--brand-primary);
}

.conversation-item.active {
  border-color: var(--brand-primary);
  background: var(--bg-secondary);
  box-shadow: var(--card-shadow-xs);
}

.conversation-item-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.conversation-item strong,
.reference-item strong,
.chat-main-header h3 {
  color: var(--text-primary);
}

.conversation-item p,
.reference-item p,
.chat-main-header p,
.guideline-item span {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.65;
}

.conversation-time {
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.chat-main {
  min-height: 780px;
  grid-template-rows: auto 1fr auto;
}

.chat-main-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border-color);
}

.chat-header-meta {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 10px;
}

.message-list {
  align-content: start;
}

.message-card {
  display: grid;
  gap: 12px;
  padding: 18px;
  border: 1px solid var(--border-color);
  border-radius: 20px;
  background: var(--bg-tertiary);
}

.message-card.assistant {
  background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--surface-overlay) 100%);
}

.message-card.user {
  border-color: rgba(37, 99, 235, 0.18);
  background: var(--brand-primary-light);
}

.message-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.message-role {
  color: var(--text-primary);
  font-weight: 700;
}

.message-content {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.8;
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
  display: grid;
  gap: 14px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.compact-heading {
  margin-bottom: 12px;
}

@media (max-width: 1360px) {
  .chat-layout {
    grid-template-columns: 280px minmax(0, 1fr);
  }

  .side-panel {
    grid-column: 1 / -1;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .chat-layout,
  .side-panel {
    grid-template-columns: 1fr;
  }

  .chat-main-header,
  .composer-actions,
  .conversation-item-top,
  .message-meta {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
