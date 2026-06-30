import { createRouter, createWebHistory } from 'vue-router'

import AgenticRagView from '../views/AgenticRagView.vue'
import ChatEmbedBootstrap from '../views/ChatEmbedBootstrap.vue'
import ChatView from '../views/ChatView.vue'
import HealthView from '../views/HealthView.vue'
import HomeView from '../views/HomeView.vue'
import KnowledgeBaseDetailView from '../views/KnowledgeBaseDetailView.vue'
import KnowledgeBasesView from '../views/KnowledgeBasesView.vue'
import KnowledgeDocumentDetailView from '../views/KnowledgeDocumentDetailView.vue'
import KnowledgeRetrievalView from '../views/KnowledgeRetrievalView.vue'
import LoginView from '../views/LoginView.vue'
import NoSpaceAssignedView from '../views/NoSpaceAssignedView.vue'
import ProvidersView from '../views/ProvidersView.vue'
import RetrievalView from '../views/RetrievalView.vue'
import SettingsView from '../views/SettingsView.vue'
import UsersView from '../views/UsersView.vue'
import { useAuthStore } from '../stores/auth'

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
      path: '/no-space',
      name: 'no-space',
      component: NoSpaceAssignedView,
      meta: {
        noSpaceAllowed: true,
        title: '未分配企业空间',
        description: '请联系管理员分配企业空间。',
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
      component: KnowledgeRetrievalView,
      meta: {
        title: '知识检索',
        description: '普通检索验证召回效果，智能检索完成闭环问答。',
      },
      children: [
        {
          path: '',
          name: 'retrieval',
          component: RetrievalView,
        },
        {
          path: 'agentic',
          name: 'retrieval-agentic',
          component: AgenticRagView,
        },
      ],
    },
    {
      path: '/agentic-rag',
      redirect: { name: 'retrieval-agentic' },
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
      path: '/chat/:sessionId',
      name: 'chat-session',
      component: ChatView,
      meta: {
        title: '聊天助手',
        description: '面向企业智能对话的 RAG 工作台。',
      },
    },
    {
      path: '/chat',
      name: 'chat',
      component: ChatView,
      meta: {
        title: '聊天助手',
        description: '面向企业智能对话的 RAG 工作台。',
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
        requiresSystemAdmin: true,
        title: '系统设置',
        description: '查看平台依赖的服务组件运行状态与访问入口。',
      },
    },
    {
      path: '/admin/spaces',
      name: 'admin-spaces',
      redirect: { name: 'admin-users' },
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: UsersView,
      meta: {
        requiresSpaceAdmin: true,
        title: '用户管理',
        description: '创建与管理企业用户及空间分配。',
      },
    },
  ],
})

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()
  const token = localStorage.getItem('auth_token')
  const isLoginPage = to.path === '/login'
  const isPublic = Boolean(to.meta.public)

  if (token && !authStore.initialized) {
    await authStore.ensureInitialized()
  }

  if (!token && !isLoginPage && !isPublic) {
    next('/login')
    return
  }

  if (token && isLoginPage) {
    next(authStore.postLoginRoute())
    return
  }

  if (token && authStore.needsSpaceAssignment && !to.meta.noSpaceAllowed) {
    next('/no-space')
    return
  }

  if (to.meta.requiresSystemAdmin && !authStore.isSystemAdmin) {
    next('/')
    return
  }

  if (to.meta.requiresSpaceAdmin && !authStore.canManageUsers) {
    next('/')
    return
  }

  next()
})

export default router
