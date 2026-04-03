<template>
  <Layout>
    <div class="page-header">
      <h1>模型管理</h1>
      <button @click="showCreateModal = true" class="btn-primary">
        + 新建 Provider
      </button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else class="providers-grid">
      <div v-for="provider in providers" :key="provider.id" class="provider-card">
        <div class="provider-header">
          <div>
            <h3>{{ provider.name }}</h3>
            <span class="provider-type">{{ provider.provider_type }}</span>
          </div>
          <span :class="['status-badge', provider.is_active ? 'active' : 'inactive']">
            {{ provider.is_active ? '启用' : '禁用' }}
          </span>
        </div>

        <div class="provider-body">
          <div class="info-row">
            <span class="label">Base URL:</span>
            <span class="value">{{ provider.base_url }}</span>
          </div>
          <div class="info-row">
            <span class="label">超时时间:</span>
            <span class="value">{{ provider.timeout_seconds }}s</span>
          </div>
          <div class="info-row">
            <span class="label">最大重试:</span>
            <span class="value">{{ provider.max_retries }}</span>
          </div>
          <div v-if="provider.description" class="info-row">
            <span class="label">描述:</span>
            <span class="value">{{ provider.description }}</span>
          </div>
        </div>

        <div class="provider-actions">
          <button @click="testProvider(provider.id)" class="btn-secondary" :disabled="testing">
            {{ testing ? '测试中...' : '测试连接' }}
          </button>
          <button @click="deleteProvider(provider.id)" class="btn-danger">删除</button>
        </div>

        <div v-if="testResults[provider.id]" :class="['test-result', testResults[provider.id].success ? 'success' : 'error']">
          {{ testResults[provider.id].message }}
          <span v-if="testResults[provider.id].response_time_ms" class="response-time">
            ({{ Math.round(testResults[provider.id].response_time_ms!) }}ms)
          </span>
        </div>
      </div>

      <div v-if="providers.length === 0" class="empty-state">
        <p>暂无 Provider，点击右上角创建</p>
      </div>
    </div>

    <!-- Create Modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click="showCreateModal = false">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h2>新建 Provider</h2>
          <button @click="showCreateModal = false" class="close-btn">×</button>
        </div>

        <form @submit.prevent="createProvider" class="modal-body">
          <div class="form-group">
            <label>名称</label>
            <input v-model="formData.name" type="text" required placeholder="例如：OpenAI" />
          </div>

          <div class="form-group">
            <label>Provider 类型</label>
            <select v-model="formData.provider_type" required>
              <option value="openai-compatible">OpenAI Compatible</option>
              <option value="bailian">阿里云百炼</option>
              <option value="deepseek">深度求索</option>
              <option value="zhipu">智谱 AI</option>
              <option value="kimi">Kimi</option>
            </select>
          </div>

          <div class="form-group">
            <label>Base URL</label>
            <input v-model="formData.base_url" type="url" required placeholder="https://api.example.com/v1" />
          </div>

          <div class="form-group">
            <label>API Key</label>
            <input v-model="formData.api_key" type="password" required placeholder="sk-..." />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>超时时间 (秒)</label>
              <input v-model.number="formData.timeout_seconds" type="number" min="1" max="300" />
            </div>

            <div class="form-group">
              <label>最大重试次数</label>
              <input v-model.number="formData.max_retries" type="number" min="0" max="10" />
            </div>
          </div>

          <div class="form-group">
            <label>描述</label>
            <textarea v-model="formData.description" rows="3" placeholder="可选描述信息"></textarea>
          </div>

          <div v-if="createError" class="error-message">{{ createError }}</div>

          <div class="modal-footer">
            <button type="button" @click="showCreateModal = false" class="btn-secondary">取消</button>
            <button type="submit" class="btn-primary" :disabled="creating">
              {{ creating ? '创建中...' : '创建' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Layout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { http } from '../lib/http'
import Layout from '../components/Layout.vue'

interface Provider {
  id: number
  name: string
  provider_type: string
  base_url: string
  is_active: boolean
  timeout_seconds: number
  max_retries: number
  description?: string
}

interface TestResult {
  success: boolean
  message: string
  response_time_ms?: number
}

const providers = ref<Provider[]>([])
const loading = ref(true)
const error = ref('')
const showCreateModal = ref(false)
const creating = ref(false)
const createError = ref('')
const testing = ref(false)
const testResults = ref<Record<number, TestResult>>({})

const formData = ref({
  name: '',
  provider_type: 'openai-compatible',
  base_url: '',
  api_key: '',
  timeout_seconds: 30,
  max_retries: 3,
  description: '',
})

const fetchProviders = async () => {
  loading.value = true
  error.value = ''
  try {
    const { data } = await http.get<Provider[]>('/providers')
    providers.value = data
  } catch (err) {
    error.value = '加载 Provider 列表失败'
  } finally {
    loading.value = false
  }
}

const createProvider = async () => {
  creating.value = true
  createError.value = ''
  try {
    await http.post('/providers', formData.value)
    showCreateModal.value = false
    formData.value = {
      name: '',
      provider_type: 'openai-compatible',
      base_url: '',
      api_key: '',
      timeout_seconds: 30,
      max_retries: 3,
      description: '',
    }
    await fetchProviders()
  } catch (err: any) {
    createError.value = err.response?.data?.detail || '创建失败'
  } finally {
    creating.value = false
  }
}

const testProvider = async (providerId: number) => {
  testing.value = true
  try {
    const { data } = await http.post<TestResult>(`/providers/test?provider_id=${providerId}`)
    testResults.value[providerId] = data
  } catch (err: any) {
    testResults.value[providerId] = {
      success: false,
      message: err.response?.data?.detail || '测试失败',
    }
  } finally {
    testing.value = false
  }
}

const deleteProvider = async (providerId: number) => {
  if (!confirm('确定要删除此 Provider 吗？')) return

  try {
    await http.delete(`/providers/${providerId}`)
    await fetchProviders()
  } catch (err) {
    alert('删除失败')
  }
}

onMounted(fetchProviders)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0;
  font-size: 1.5rem;
  color: #e2e8f0;
}

.providers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
}

.provider-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 20px;
  transition: all 0.2s;
}

.provider-card:hover {
  border-color: rgba(124, 211, 252, 0.3);
  background: rgba(255, 255, 255, 0.05);
}

.provider-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.provider-header h3 {
  margin: 0 0 4px;
  color: #e2e8f0;
  font-size: 1.1rem;
}

.provider-type {
  color: #7dd3fc;
  font-size: 0.85rem;
  background: rgba(124, 211, 252, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.status-badge {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
}

.status-badge.active {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.status-badge.inactive {
  background: rgba(148, 163, 184, 0.2);
  color: #94a3b8;
}

.provider-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.info-row {
  display: flex;
  gap: 8px;
  font-size: 0.9rem;
}

.info-row .label {
  color: #64748b;
  min-width: 70px;
}

.info-row .value {
  color: #cbd5e1;
}

.provider-actions {
  display: flex;
  gap: 8px;
}

.btn-primary,
.btn-secondary,
.btn-danger {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background: linear-gradient(135deg, #7dd3fc 0%, #38bdf8 100%);
  color: #0f172a;
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.btn-danger {
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
  border: 1px solid rgba(248, 113, 113, 0.3);
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
}

.btn-secondary:hover:not(:disabled),
.btn-danger:hover:not(:disabled) {
  filter: brightness(1.2);
}

.btn-primary:disabled,
.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.test-result {
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
}

.test-result.success {
  background: rgba(34, 197, 94, 0.1);
  color: #4ade80;
}

.test-result.error {
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
}

.response-time {
  opacity: 0.8;
}

.empty-state {
  text-align: center;
  padding: 48px;
  color: #64748b;
}

.loading,
.error {
  text-align: center;
  padding: 48px;
  color: #64748b;
}

.error {
  color: #f87171;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #1e293b;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.modal-header h2 {
  margin: 0;
  color: #e2e8f0;
  font-size: 1.25rem;
}

.close-btn {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 1.5rem;
  cursor: pointer;
}

.modal-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  color: #e2e8f0;
  font-size: 0.9rem;
  margin-bottom: 6px;
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  color: #e2e8f0;
  font-size: 0.9rem;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #7dd3fc;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.error-message {
  color: #f87171;
  background: rgba(248, 113, 113, 0.1);
  padding: 12px;
  border-radius: 6px;
  font-size: 0.85rem;
  margin-bottom: 16px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}
</style>
