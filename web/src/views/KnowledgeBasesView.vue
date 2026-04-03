<template>
  <Layout>
    <div class="page-header">
      <h1>知识库管理</h1>
      <button @click="showCreateModal = true" class="btn-primary">
        + 新建知识库
      </button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else class="kb-grid">
      <div v-for="kb in knowledgeBases" :key="kb.id" class="kb-card">
        <div class="kb-header">
          <h3>{{ kb.name }}</h3>
          <span :class="['status-badge', kb.status]">
            {{ kb.status === 'active' ? '活跃' : '未激活' }}
          </span>
        </div>

        <div v-if="kb.description" class="kb-description">{{ kb.description }}</div>

        <div class="kb-badges">
          <span v-if="kb.vector_db_enabled" class="badge">向量数据库</span>
          <span v-if="kb.graph_db_enabled" class="badge">图数据库</span>
        </div>

        <div class="kb-section">
          <div class="kb-section-title">
            <span>Milvus 连接</span>
            <button
              v-if="!kb.vector_db_enabled"
              @click="showMilvusModal(kb)"
              class="btn-link"
            >
              配置
            </button>
            <button
              v-else-if="!milvusConnections[kb.id]"
              @click="showMilvusModal(kb)"
              class="btn-link"
            >
              配置
            </button>
          </div>
          <div v-if="milvusConnections[kb.id]" class="connection-info">
            <div class="info-row">
              <span class="label">主机:</span>
              <span>{{ milvusConnections[kb.id].host }}:{{ milvusConnections[kb.id].port }}</span>
            </div>
            <div class="connection-actions">
              <button @click="testMilvus(kb.id)" class="btn-sm" :disabled="testing">
                {{ testing ? '测试中...' : '测试' }}
              </button>
              <button @click="deleteMilvusConnection(kb.id)" class="btn-sm btn-danger">删除</button>
            </div>
            <div v-if="testResults[kb.id]" :class="['test-result', testResults[kb.id].success ? 'success' : 'error']">
              {{ testResults[kb.id].message }}
            </div>
          </div>
        </div>

        <div class="kb-section">
          <div class="kb-section-title">
            <span>Neo4j 连接</span>
            <button
              v-if="!kb.graph_db_enabled"
              @click="showNeo4jModal(kb)"
              class="btn-link"
            >
              配置
            </button>
            <button
              v-else-if="!neo4jConnections[kb.id]"
              @click="showNeo4jModal(kb)"
              class="btn-link"
            >
              配置
            </button>
          </div>
          <div v-if="neo4jConnections[kb.id]" class="connection-info">
            <div class="info-row">
              <span class="label">URI:</span>
              <span>{{ neo4jConnections[kb.id].uri }}</span>
            </div>
            <div class="connection-actions">
              <button @click="testNeo4j(kb.id)" class="btn-sm" :disabled="testing">
                {{ testing ? '测试中...' : '测试' }}
              </button>
              <button @click="deleteNeo4jConnection(kb.id)" class="btn-sm btn-danger">删除</button>
            </div>
            <div v-if="testResults[kb.id + '-neo4j']" :class="['test-result', testResults[kb.id + '-neo4j'].success ? 'success' : 'error']">
              {{ testResults[kb.id + '-neo4j'].message }}
            </div>
          </div>
        </div>

        <div class="kb-actions">
          <button @click="deleteKnowledgeBase(kb.id)" class="btn-danger">删除</button>
        </div>
      </div>

      <div v-if="knowledgeBases.length === 0" class="empty-state">
        <p>暂无知识库，点击右上角创建</p>
      </div>
    </div>

    <!-- Create KB Modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click="showCreateModal = false">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h2>新建知识库</h2>
          <button @click="showCreateModal = false" class="close-btn">×</button>
        </div>

        <form @submit.prevent="createKnowledgeBase" class="modal-body">
          <div class="form-group">
            <label>名称</label>
            <input v-model="formData.name" type="text" required placeholder="知识库名称" />
          </div>

          <div class="form-group">
            <label>描述</label>
            <textarea v-model="formData.description" rows="3" placeholder="可选描述"></textarea>
          </div>

          <div class="form-group">
            <label class="checkbox-label">
              <input v-model="formData.vector_db_enabled" type="checkbox" />
              启用向量数据库 (Milvus)
            </label>
          </div>

          <div class="form-group">
            <label class="checkbox-label">
              <input v-model="formData.graph_db_enabled" type="checkbox" />
              启用图数据库 (Neo4j)
            </label>
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

    <!-- Milvus Config Modal -->
    <div v-if="showMilvusModalFlag" class="modal-overlay" @click="closeMilvusModal">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h2>配置 Milvus 连接</h2>
          <button @click="closeMilvusModal" class="close-btn">×</button>
        </div>

        <form @submit.prevent="saveMilvusConnection" class="modal-body">
          <div class="form-group">
            <label>主机地址</label>
            <input v-model="milvusFormData.host" type="text" required placeholder="localhost" />
          </div>

          <div class="form-group">
            <label>端口</label>
            <input v-model.number="milvusFormData.port" type="number" value="19530" />
          </div>

          <div class="form-group">
            <label>用户名 (可选)</label>
            <input v-model="milvusFormData.username" type="text" placeholder="可选" />
          </div>

          <div class="form-group">
            <label>密码 (可选)</label>
            <input v-model="milvusFormData.password" type="password" placeholder="可选" />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>向量维度</label>
              <input v-model.number="milvusFormData.dimension" type="number" value="1536" />
            </div>

            <div class="form-group">
              <label>距离度量</label>
              <select v-model="milvusFormData.metric_type">
                <option value="COSINE">COSINE</option>
                <option value="L2">L2</option>
                <option value="IP">IP</option>
              </select>
            </div>
          </div>

          <div v-if="milvusError" class="error-message">{{ milvusError }}</div>

          <div class="modal-footer">
            <button type="button" @click="closeMilvusModal" class="btn-secondary">取消</button>
            <button type="submit" class="btn-primary" :disabled="saving">
              {{ saving ? '保存中...' : '保存' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Neo4j Config Modal -->
    <div v-if="showNeo4jModalFlag" class="modal-overlay" @click="closeNeo4jModal">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h2>配置 Neo4j 连接</h2>
          <button @click="closeNeo4jModal" class="close-btn">×</button>
        </div>

        <form @submit.prevent="saveNeo4jConnection" class="modal-body">
          <div class="form-group">
            <label>URI</label>
            <input v-model="neo4jFormData.uri" type="text" required placeholder="bolt://localhost:7687" />
          </div>

          <div class="form-group">
            <label>用户名</label>
            <input v-model="neo4jFormData.username" type="text" required placeholder="neo4j" />
          </div>

          <div class="form-group">
            <label>密码</label>
            <input v-model="neo4jFormData.password" type="password" placeholder="密码" />
          </div>

          <div class="form-group">
            <label>数据库名 (可选)</label>
            <input v-model="neo4jFormData.database" type="text" placeholder="neo4j" />
          </div>

          <div v-if="neo4jError" class="error-message">{{ neo4jError }}</div>

          <div class="modal-footer">
            <button type="button" @click="closeNeo4jModal" class="btn-secondary">取消</button>
            <button type="submit" class="btn-primary" :disabled="saving">
              {{ saving ? '保存中...' : '保存' }}
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

interface KnowledgeBase {
  id: number
  name: string
  description?: string
  status: string
  vector_db_enabled: boolean
  graph_db_enabled: boolean
}

interface MilvusConnection {
  id: number
  host: string
  port: number
  username?: string
  collection_name?: string
}

interface Neo4jConnection {
  id: number
  uri: string
  username: string
  database?: string
}

interface TestResult {
  success: boolean
  message: string
}

const knowledgeBases = ref<KnowledgeBase[]>([])
const milvusConnections = ref<Record<number, MilvusConnection>>({})
const neo4jConnections = ref<Record<number, Neo4jConnection>>({})
const loading = ref(true)
const error = ref('')
const showCreateModal = ref(false)
const creating = ref(false)
const createError = ref('')
const testing = ref(false)
const saving = ref(false)
const testResults = ref<Record<string, TestResult>>({})

const formData = ref({
  name: '',
  description: '',
  vector_db_enabled: true,
  graph_db_enabled: false,
})

const milvusFormData = ref({
  host: 'localhost',
  port: 19530,
  username: '',
  password: '',
  dimension: 1536,
  metric_type: 'COSINE',
})

const neo4jFormData = ref({
  uri: 'bolt://localhost:7687',
  username: 'neo4j',
  password: '',
  database: 'neo4j',
})

const showMilvusModalFlag = ref(false)
const showNeo4jModalFlag = ref(false)
const currentKbId = ref<number | null>(null)
const milvusError = ref('')
const neo4jError = ref('')

const fetchKnowledgeBases = async () => {
  loading.value = true
  error.value = ''
  try {
    const { data } = await http.get<KnowledgeBase[]>('/knowledge-bases')
    knowledgeBases.value = data
    data.forEach((kb) => {
      fetchMilvusConnection(kb.id)
      fetchNeo4jConnection(kb.id)
    })
  } catch (err) {
    error.value = '加载知识库列表失败'
  } finally {
    loading.value = false
  }
}

const fetchMilvusConnection = async (kbId: number) => {
  try {
    const { data } = await http.get<MilvusConnection>(`/knowledge-bases/${kbId}/milvus-connection`)
    milvusConnections.value[kbId] = data
  } catch (err) {
    // 404 means no connection configured, ignore
  }
}

const fetchNeo4jConnection = async (kbId: number) => {
  try {
    const { data } = await http.get<Neo4jConnection>(`/knowledge-bases/${kbId}/neo4j-connection`)
    neo4jConnections.value[kbId] = data
  } catch (err) {
    // 404 means no connection configured, ignore
  }
}

const createKnowledgeBase = async () => {
  creating.value = true
  createError.value = ''
  try {
    const { data } = await http.post<KnowledgeBase>('/knowledge-bases', formData.value)
    showCreateModal.value = false
    formData.value = { name: '', description: '', vector_db_enabled: true, graph_db_enabled: false }
    knowledgeBases.value.push(data)
  } catch (err: any) {
    createError.value = err.response?.data?.detail || '创建失败'
  } finally {
    creating.value = false
  }
}

const deleteKnowledgeBase = async (kbId: number) => {
  if (!confirm('确定要删除此知识库吗？')) return
  try {
    await http.delete(`/knowledge-bases/${kbId}`)
    await fetchKnowledgeBases()
  } catch (err) {
    alert('删除失败')
  }
}

const showMilvusModal = (kb: KnowledgeBase) => {
  currentKbId.value = kb.id
  showMilvusModalFlag.value = true
  milvusError.value = ''
}

const closeMilvusModal = () => {
  showMilvusModalFlag.value = false
  currentKbId.value = null
  milvusFormData.value = {
    host: 'localhost',
    port: 19530,
    username: '',
    password: '',
    dimension: 1536,
    metric_type: 'COSINE',
  }
}

const saveMilvusConnection = async () => {
  saving.value = true
  milvusError.value = ''
  try {
    if (!currentKbId.value) return
    const { data } = await http.post<MilvusConnection>(
      `/knowledge-bases/${currentKbId.value}/milvus-connection`,
      milvusFormData.value
    )
    milvusConnections.value[currentKbId.value] = data
    closeMilvusModal()
  } catch (err: any) {
    milvusError.value = err.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

const deleteMilvusConnection = async (kbId: number) => {
  if (!confirm('确定要删除 Milvus 连接配置吗？')) return
  try {
    await http.delete(`/knowledge-bases/${kbId}/milvus-connection`)
    delete milvusConnections.value[kbId]
  } catch (err) {
    alert('删除失败')
  }
}

const testMilvus = async (kbId: number) => {
  testing.value = true
  try {
    const { data } = await http.post<TestResult>(`/knowledge-bases/${kbId}/milvus-connection/test`)
    testResults.value[kbId] = data
  } catch (err: any) {
    testResults.value[kbId] = {
      success: false,
      message: err.response?.data?.detail || '测试失败',
    }
  } finally {
    testing.value = false
  }
}

const showNeo4jModal = (kb: KnowledgeBase) => {
  currentKbId.value = kb.id
  showNeo4jModalFlag.value = true
  neo4jError.value = ''
}

const closeNeo4jModal = () => {
  showNeo4jModalFlag.value = false
  currentKbId.value = null
  neo4jFormData.value = {
    uri: 'bolt://localhost:7687',
    username: 'neo4j',
    password: '',
    database: 'neo4j',
  }
}

const saveNeo4jConnection = async () => {
  saving.value = true
  neo4jError.value = ''
  try {
    if (!currentKbId.value) return
    const { data } = await http.post<Neo4jConnection>(
      `/knowledge-bases/${currentKbId.value}/neo4j-connection`,
      neo4jFormData.value
    )
    neo4jConnections.value[currentKbId.value] = data
    closeNeo4jModal()
  } catch (err: any) {
    neo4jError.value = err.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

const deleteNeo4jConnection = async (kbId: number) => {
  if (!confirm('确定要删除 Neo4j 连接配置吗？')) return
  try {
    await http.delete(`/knowledge-bases/${kbId}/neo4j-connection`)
    delete neo4jConnections.value[kbId]
  } catch (err) {
    alert('删除失败')
  }
}

const testNeo4j = async (kbId: number) => {
  testing.value = true
  try {
    const { data } = await http.post<TestResult>(`/knowledge-bases/${kbId}/neo4j-connection/test`)
    testResults.value[kbId + '-neo4j'] = data
  } catch (err: any) {
    testResults.value[kbId + '-neo4j'] = {
      success: false,
      message: err.response?.data?.detail || '测试失败',
    }
  } finally {
    testing.value = false
  }
}

onMounted(fetchKnowledgeBases)
</script>

<style scoped>
/* Reuse similar styles from ProvidersView */
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

.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 20px;
}

.kb-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 20px;
}

.kb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.kb-header h3 {
  margin: 0;
  color: #e2e8f0;
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

.kb-description {
  color: #94a3b8;
  font-size: 0.9rem;
  margin-bottom: 12px;
}

.kb-badges {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.badge {
  background: rgba(124, 211, 252, 0.1);
  color: #7dd3fc;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
}

.kb-section {
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.kb-section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #cbd5e1;
  font-size: 0.9rem;
  margin-bottom: 8px;
}

.btn-link {
  background: none;
  border: none;
  color: #7dd3fc;
  cursor: pointer;
  font-size: 0.85rem;
}

.connection-info {
  font-size: 0.85rem;
}

.info-row {
  display: flex;
  gap: 8px;
  color: #94a3b8;
  margin-bottom: 8px;
}

.info-row .label {
  min-width: 50px;
}

.connection-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 0.8rem;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.05);
  color: #e2e8f0;
  cursor: pointer;
}

.btn-sm.btn-danger {
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
  border-color: rgba(248, 113, 113, 0.3);
}

.test-result {
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 0.8rem;
}

.test-result.success {
  background: rgba(34, 197, 94, 0.1);
  color: #4ade80;
}

.test-result.error {
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
}

.kb-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-primary,
.btn-secondary,
.btn-danger {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 0.9rem;
  cursor: pointer;
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

.empty-state,
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

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: auto;
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
