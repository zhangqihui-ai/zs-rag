<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1>ZS-RAG</h1>
        <p class="subtitle">企业空间 RAG 管理平台</p>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="username"
            type="text"
            placeholder="请输入用户名"
            required
            autocomplete="username"
          />
        </div>

        <div class="form-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="请输入密码"
            required
            autocomplete="current-password"
          />
        </div>

        <button type="submit" class="login-button" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>

    <div v-if="showErrorModal" class="modal-overlay" @click.self="closeErrorModal">
      <div class="modal-card login-error-modal" role="alertdialog" aria-labelledby="login-error-title" aria-modal="true">
        <div class="login-error-modal-header">
          <h3 id="login-error-title">登录失败</h3>
        </div>
        <p class="login-error-modal-message">{{ errorMessage }}</p>
        <div class="login-error-modal-actions">
          <button type="button" class="login-button" @click="closeErrorModal">知道了</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { getApiErrorMessage } from '../lib/apiError'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const showErrorModal = ref(false)
const errorMessage = ref('')

const showLoginError = (message: string) => {
  errorMessage.value = message
  showErrorModal.value = true
}

const closeErrorModal = () => {
  showErrorModal.value = false
}

const handleLogin = async () => {
  if (!username.value || !password.value) {
    showLoginError('请输入用户名和密码')
    return
  }

  loading.value = true
  showErrorModal.value = false

  try {
    await authStore.login({
      username: username.value,
      password: password.value,
    })
    router.push(authStore.postLoginRoute())
  } catch (err) {
    showLoginError(getApiErrorMessage(err, '用户名或密码错误，请检查后重试'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  padding: 20px;
}

.login-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 48px;
  width: 100%;
  max-width: 420px;
  box-shadow: var(--card-shadow);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  color: var(--brand-primary);
  font-size: 2.5rem;
  margin: 0 0 8px;
  font-weight: 700;
}

.subtitle {
  color: var(--text-secondary);
  margin: 0;
  font-size: 0.95rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 500;
}

.form-group input {
  padding: 12px 16px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-size: 1rem;
  transition: all 0.2s;
}

.form-group input:focus {
  outline: none;
  border-color: var(--brand-primary);
  background: var(--bg-secondary);
}

.form-group input::placeholder {
  color: var(--text-tertiary);
}

.login-error-modal {
  width: min(400px, 100%);
  padding: 28px 28px 24px;
  text-align: center;
}

.login-error-modal-header h3 {
  margin: 0 0 12px;
  color: #f87171;
  font-size: 1.15rem;
}

.login-error-modal-message {
  margin: 0 0 24px;
  color: var(--text-primary);
  font-size: 0.95rem;
  line-height: 1.6;
}

.login-error-modal-actions {
  display: flex;
  justify-content: center;
}

.login-error-modal-actions .login-button {
  min-width: 120px;
}

.login-button {
  padding: 14px 24px;
  background: var(--brand-primary);
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.login-button:hover:not(:disabled) {
  background: var(--brand-primary-hover);
  transform: translateY(-2px);
  box-shadow: 0 10px 20px -10px var(--brand-primary-light);
}

.login-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
