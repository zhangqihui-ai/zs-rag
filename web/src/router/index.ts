import { createRouter, createWebHistory } from 'vue-router'

import ChatEmbedBootstrap from '../views/ChatEmbedBootstrap.vue'
import ChatView from '../views/ChatView.vue'
import HealthView from '../views/HealthView.vue'
import HomeView from '../views/HomeView.vue'
import KnowledgeBaseDetailView from '../views/KnowledgeBaseDetailView.vue'
import KnowledgeBasesView from '../views/KnowledgeBasesView.vue'
import KnowledgeDocumentDetailView from '../views/KnowledgeDocumentDetailView.vue'
import LoginView from '../views/LoginView.vue'
import ProvidersView from '../views/ProvidersView.vue'
import RetrievalView from '../views/RetrievalView.vue'
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: {
        public: true,
        title: '登录',
        description: '进入 ZS-RAG 企业级知识平台。',
      },
    },
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: {
        title: '首页仪表盘',
        description: '查看知识资产、模型供给与平台健康概况。',
      },
    },
    {
      path: '/health',
      name: 'health',
      component: HealthView,
      meta: {
        title: '系统健康',
        description: '关注接口、数据库与服务依赖状态。',
      },
    },
    {
      path: '/knowledge-bases',
      name: 'knowledge-bases',
      component: KnowledgeBasesView,
      meta: {
        title: '知识库管理',
        description: '查看知识库列表。',
      },
    },
    {
      path: '/knowledge-bases/:id',
      name: 'knowledge-base-detail',
      component: KnowledgeBaseDetailView,
      meta: {
        title: '知识库详情',
        description: '查看知识库文档并上传新文档。',
      },
    },
    {
      path: '/knowledge-bases/:kbId/documents/:docId',
      name: 'knowledge-document-detail',
      component: KnowledgeDocumentDetailView,
      meta: {
        title: '文档原文与切片',
        description: '对照原文与分块切片，用于嵌入与召回校验。',
      },
    },
    {
      path: '/retrieval',
      name: 'retrieval',
      component: RetrievalView,
      meta: {
        title: '知识检索',
        description: '验证召回效果、筛选策略与结果质量。',
      },
    },
    {
      path: '/chat/embed',
      name: 'chat-embed',
      component: ChatEmbedBootstrap,
      meta: {
        public: true,
        title: '嵌入对话',
        description: '第三方站点 iframe / 脚本嵌入入口。',
      },
    },
    {
      path: '/chat',
      name: 'chat',
      component: ChatView,
      meta: {
        title: '对话',
        description: '面向企业知识助手的 RAG 对话工作台。',
      },
    },
    {
      path: '/providers',
      name: 'providers',
      component: ProvidersView,
      meta: {
        title: '模型管理',
        description: '统一配置厂商、模型同步与默认模型编排。',
      },
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView,
      meta: {
        title: '系统设置',
        description: '管理主题偏好、工作台策略与系统默认项。',
      },
    },
  ],
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('auth_token')
  const isLoginPage = to.path === '/login'
  const isPublic = Boolean(to.meta.public)

  if (!token && !isLoginPage && !isPublic) {
    next('/login')
  } else if (token && isLoginPage) {
    next('/')
  } else {
    next()
  }
})

export default router
