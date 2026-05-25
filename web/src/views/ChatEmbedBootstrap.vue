<template>
  <div class="chat-embed-bootstrap">
    <template v-if="phase === 'loading'">
      <div class="ceb-inner">
        <p class="ceb-title">正在进入对话…</p>
      </div>
    </template>
    <template v-else-if="phase === 'error'">
      <div class="ceb-inner">
        <p class="ceb-title">无法完成嵌入登录</p>
        <p class="ceb-desc">{{ errorMessage }}</p>
        <a class="ceb-link" href="/login" target="_blank" rel="noopener noreferrer">在新标签打开登录页</a>
      </div>
    </template>
    <template v-else>
      <div class="ceb-inner">
        <p class="ceb-title">嵌入对话需要登录态</p>
        <p class="ceb-desc">
          跨域名嵌入时，iframe 与主站<strong>不共享</strong>浏览器登录缓存，直接打开会出现登录页。请任选其一：
        </p>
        <ul class="ceb-list">
          <li>
            推荐：使用后台「嵌入到网站中」按<strong>当前对话</strong>签发的<strong>嵌入 API Key</strong>：
            <code class="ceb-code">/chat/embed?api_key=&lt;密钥&gt;&amp;space=&lt;slug&gt;&amp;conversation_id=&lt;可选·UUID&gt;</code>（进入后为<strong>精简对话面板</strong>：无平台侧栏与「会话」列表；请求头
            <code class="ceb-code">Authorization: Bearer</code> 与密钥一致；带 <code class="ceb-code">conversation_id</code> 时进入后会自动打开该对话）。
          </li>
          <li>
            或附带登录 JWT：<code class="ceb-code">/chat/embed?access_token=&lt;token&gt;</code>（可选 <code class="ceb-code">space=…</code>）。
          </li>
          <li>
            宿主页与本平台<strong>同源</strong>时，可先登录主站，再在同一源下嵌入 <code class="ceb-code">/chat/embed</code>。
          </li>
        </ul>
        <a class="ceb-link" href="/login" target="_blank" rel="noopener noreferrer">在新标签打开登录页</a>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

type Phase = 'loading' | 'gate' | 'error'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const phase = ref<Phase>('loading')
const errorMessage = ref('')

function querySingle(key: string): string {
  const raw = route.query[key]
  if (typeof raw === 'string') return raw
  if (Array.isArray(raw) && typeof raw[0] === 'string') return raw[0]
  return ''
}

onMounted(async () => {
  const apiKeyFromQuery = querySingle('api_key')
  const tokenFromQuery = querySingle('access_token')
  const spaceFromQuery = querySingle('space')
  const conversationIdFromQuery = querySingle('conversation_id')

  const embedRedirectQuery: Record<string, string> = { embed_panel: '1' }
  if (conversationIdFromQuery) {
    embedRedirectQuery.conversation_id = conversationIdFromQuery
  }

  const applyTokenAndRedirect = async (token: string) => {
    localStorage.setItem('auth_token', token)
    authStore.token = token
    if (spaceFromQuery) {
      localStorage.setItem('current_enterprise_space', spaceFromQuery)
      authStore.currentSpaceSlug = spaceFromQuery
    }
    try {
      await authStore.init()
    } catch {
      authStore.logout()
      phase.value = 'error'
      errorMessage.value =
        '凭证无效、已吊销或网络异常。嵌入场景请检查 api_key 与企业空间 slug；JWT 场景请重新登录后复制 access_token。'
      return
    }
    if (!authStore.isAuthenticated || !authStore.user) {
      phase.value = 'error'
      errorMessage.value = '无法校验登录状态，请检查 api_key / access_token 及 space 是否正确。'
      return
    }
    await router.replace({ path: '/chat', query: embedRedirectQuery })
  }

  if (apiKeyFromQuery) {
    await applyTokenAndRedirect(apiKeyFromQuery)
    return
  }

  if (tokenFromQuery) {
    await applyTokenAndRedirect(tokenFromQuery)
    return
  }

  const existing = localStorage.getItem('auth_token')
  if (existing) {
    authStore.token = existing
    try {
      await authStore.init()
    } catch {
      authStore.logout()
      phase.value = 'gate'
      return
    }
    if (authStore.isAuthenticated && authStore.user) {
      await router.replace({ path: '/chat', query: embedRedirectQuery })
      return
    }
  }

  phase.value = 'gate'
})
</script>

<style scoped>
.chat-embed-bootstrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 20px;
  background: var(--bg-secondary, #f4f6fb);
  color: var(--text-primary, #1a2233);
  font-family:
    system-ui,
    -apple-system,
    'Segoe UI',
    Roboto,
    'PingFang SC',
    'Microsoft YaHei',
    sans-serif;
}

.ceb-inner {
  max-width: 520px;
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  padding: 28px 28px 24px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
  border: 1px solid var(--border-default, #e3e8f0);
}

.ceb-title {
  margin: 0 0 12px;
  font-size: 1.15rem;
  font-weight: 600;
}

.ceb-desc {
  margin: 0 0 16px;
  font-size: 0.95rem;
  line-height: 1.6;
  color: var(--text-secondary, #5c6b8a);
}

.ceb-list {
  margin: 0 0 20px;
  padding-left: 1.25rem;
  font-size: 0.92rem;
  line-height: 1.65;
  color: var(--text-secondary, #5c6b8a);
}

.ceb-list li {
  margin-bottom: 10px;
}

.ceb-code {
  font-size: 0.82rem;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(28, 100, 242, 0.08);
  word-break: break-all;
}

.ceb-link {
  display: inline-block;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--brand-primary, #1c64f2);
  text-decoration: none;
}

.ceb-link:hover {
  text-decoration: underline;
}
</style>
