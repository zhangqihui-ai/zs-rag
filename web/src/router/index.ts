import { createRouter, createWebHistory } from 'vue-router'

import LoginView from '../views/LoginView.vue'
import ProvidersView from '../views/ProvidersView.vue'
import KnowledgeBasesView from '../views/KnowledgeBasesView.vue'
import HealthView from '../views/HealthView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
    },
    {
      path: '/',
      name: 'home',
      component: HealthView,
    },
    {
      path: '/providers',
      name: 'providers',
      component: ProvidersView,
    },
    {
      path: '/knowledge-bases',
      name: 'knowledge-bases',
      component: KnowledgeBasesView,
    },
  ],
})

// 路由守卫 - 验证登录状态
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('auth_token')
  const isLoginPage = to.path === '/login'

  if (!token && !isLoginPage) {
    next('/login')
  } else if (token && isLoginPage) {
    next('/')
  } else {
    next()
  }
})

export default router
