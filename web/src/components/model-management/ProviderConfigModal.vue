<template>
  <div v-if="open && template" class="modal-overlay" @click.self="emit('close')">
    <div class="modal-card provider-config-modal">
      <div class="modal-header">
        <div>
          <h2>{{ mode === 'create' ? `接入 ${template.provider_name}` : `编辑 ${template.provider_name}` }}</h2>
          <p>{{ mode === 'create' ? '填写地址与认证信息后即可同步模型' : '更新配置后可选择重新同步模型' }}</p>
        </div>
        <button class="icon-btn" type="button" @click="emit('close')">
          <AppIcon name="close" :size="18" />
        </button>
      </div>

      <div class="template-meta">
        <span class="tag">{{ isPublicCloud ? '公有云' : '私有化' }}</span>
        <span v-for="item in template.supported_types" :key="item" class="tag subtle-tag">
          {{ MODEL_TYPE_LABEL_MAP[item] }}
        </span>
      </div>

      <form class="modal-form" @submit.prevent="handleSubmit">
        <label class="form-item">
          <span>厂商名称</span>
          <input v-model.trim="form.provider_name" type="text" required />
        </label>

        <div v-if="!isPublicCloud" class="grid-two">
          <label class="form-item">
            <span>部署类型</span>
            <select v-model="form.deployment_type">
              <option value="public">公有云</option>
              <option value="private">私有化</option>
            </select>
          </label>

          <label class="form-item">
            <span>认证方式</span>
            <input :value="form.auth_type" type="text" disabled />
          </label>
        </div>

        <label class="form-item">
          <span>Base URL</span>
          <input v-model.trim="form.base_url" type="url" required />
        </label>

        <label v-for="field in template.auth_fields" :key="field.key" class="form-item">
          <span>{{ field.label }} <em v-if="field.required">*</em></span>
          <input
            v-model.trim="form.auth_config[field.key]"
            :type="field.type === 'password' ? 'password' : 'text'"
            :required="field.required && mode === 'create'"
            :placeholder="mode === 'edit' && initialValue?.has_auth_config ? '已配置，留空则保持不变' : ''"
          />
        </label>

        <div v-if="showConnectionTest" class="test-panel">
          <div class="test-actions">
            <button
              type="button"
              class="btn btn-secondary"
              :disabled="!canRunConnectionTest || testStatus === 'loading'"
              @click="handleTestConnection"
            >
              <AppIcon name="status" :size="16" />
              {{ testStatus === 'loading' ? '测试中...' : '连接测试' }}
            </button>
            <span class="test-hint">请先完成连接测试，通过后再确认接入。</span>
          </div>
          <p v-if="testMessage" :class="['test-message', testStatus === 'success' ? 'success' : 'error']">
            {{ testMessage }}
          </p>
        </div>

        <label v-if="!isPublicCloud" class="form-item">
          <span>备注</span>
          <textarea v-model.trim="form.remark" rows="3" placeholder="可选"></textarea>
        </label>

        <label class="checkbox-row">
          <input v-model="form.auto_sync_models" type="checkbox" />
          <span>保存后自动同步模型列表</span>
        </label>

        <p v-if="error" class="error-text">{{ error }}</p>

        <div class="modal-footer">
          <button type="button" class="btn btn-ghost" @click="emit('close')">取消</button>
          <button type="submit" class="btn btn-primary" :disabled="!canSubmit">
            {{ submitting ? '提交中...' : mode === 'create' ? '确认接入' : '保存修改' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import {
  MODEL_TYPE_LABEL_MAP,
  getErrorMessage,
  providerApi,
  type DeploymentType,
  type ProviderCreatePayload,
  type ProviderDetail,
  type ProviderTemplate,
} from '../../api/model-management'
import AppIcon from '../AppIcon.vue'

const props = defineProps<{
  open: boolean
  mode: 'create' | 'edit'
  template: ProviderTemplate | null
  initialValue: ProviderDetail | null
  submitting: boolean
  error: string
}>()

const emit = defineEmits<{
  close: []
  submit: [payload: ProviderCreatePayload]
}>()

const emptyForm = (): ProviderCreatePayload => ({
  provider_code: props.template?.provider_code || '',
  provider_name: props.template?.provider_name || '',
  deployment_type: props.template?.deployment_type || 'public',
  base_url: props.template?.default_base_url || '',
  auth_type: props.template?.auth_type || 'bearer',
  auth_config: {},
  remark: '',
  auto_sync_models: true,
})

const form = reactive<ProviderCreatePayload>(emptyForm())
const testStatus = ref<'idle' | 'loading' | 'success' | 'error'>('idle')
const testMessage = ref('')
const passedTestSignature = ref('')

const isPublicCloud = computed(() => form.deployment_type === 'public')
const showConnectionTest = computed(() => props.mode === 'create' && isPublicCloud.value)

const normalizedAuthConfig = computed(() => {
  const result: Record<string, string> = {}
  const fieldOrder = props.template?.auth_fields.map((field) => field.key) || []
  fieldOrder.forEach((key) => {
    const value = form.auth_config[key]?.trim()
    if (value) {
      result[key] = value
    }
  })
  Object.entries(form.auth_config).forEach(([key, value]) => {
    const normalized = value?.trim()
    if (normalized && !(key in result)) {
      result[key] = normalized
    }
  })
  return result
})

const currentTestSignature = computed(() => JSON.stringify({
  provider_code: form.provider_code.trim(),
  provider_name: form.provider_name.trim(),
  deployment_type: form.deployment_type,
  base_url: form.base_url.trim(),
  auth_type: form.auth_type.trim(),
  auth_config: normalizedAuthConfig.value,
}))

const canRunConnectionTest = computed(() => {
  if (!showConnectionTest.value) {
    return false
  }
  if (!form.provider_name.trim() || !form.base_url.trim()) {
    return false
  }
  return (props.template?.auth_fields || []).every((field) => {
    if (!field.required) {
      return true
    }
    return Boolean(form.auth_config[field.key]?.trim())
  })
})

const canSubmit = computed(() => {
  if (props.submitting) {
    return false
  }
  if (!showConnectionTest.value) {
    return true
  }
  return testStatus.value === 'success' && passedTestSignature.value === currentTestSignature.value
})

const buildPayload = (): ProviderCreatePayload => ({
  provider_code: form.provider_code.trim(),
  provider_name: form.provider_name.trim(),
  deployment_type: form.deployment_type,
  base_url: form.base_url.trim(),
  auth_type: form.auth_type.trim(),
  auth_config: { ...normalizedAuthConfig.value },
  remark: isPublicCloud.value ? undefined : form.remark?.trim() || undefined,
  auto_sync_models: form.auto_sync_models,
})

const resetForm = () => {
  const next = emptyForm()
  if (props.initialValue) {
    next.provider_code = props.initialValue.provider_code
    next.provider_name = props.initialValue.provider_name
    next.deployment_type = props.initialValue.deployment_type as DeploymentType
    next.base_url = props.initialValue.base_url
    next.auth_type = props.initialValue.auth_type
    next.remark = props.initialValue.remark || ''
    next.auto_sync_models = false
  }

  form.provider_code = next.provider_code
  form.provider_name = next.provider_name
  form.deployment_type = next.deployment_type
  form.base_url = next.base_url
  form.auth_type = next.auth_type
  form.auth_config = {}
  form.remark = next.remark
  form.auto_sync_models = next.auto_sync_models
  testStatus.value = 'idle'
  testMessage.value = ''
  passedTestSignature.value = ''
}

watch(
  () => [props.open, props.template?.provider_code, props.initialValue?.id],
  () => {
    if (props.open) {
      resetForm()
    }
  },
  { immediate: true },
)

watch(currentTestSignature, (value) => {
  if (!showConnectionTest.value) {
    testStatus.value = 'idle'
    testMessage.value = ''
    passedTestSignature.value = ''
    return
  }
  if (passedTestSignature.value && passedTestSignature.value === value) {
    return
  }
  if (testStatus.value !== 'loading') {
    testStatus.value = 'idle'
    testMessage.value = ''
  }
})

const handleTestConnection = async () => {
  if (!canRunConnectionTest.value) {
    testStatus.value = 'error'
    testMessage.value = '请先填写完整的 Base URL 和认证信息'
    passedTestSignature.value = ''
    return
  }

  testStatus.value = 'loading'
  testMessage.value = ''
  passedTestSignature.value = ''

  try {
    const result = await providerApi.testProviderConnection(buildPayload())
    testStatus.value = result.success ? 'success' : 'error'
    testMessage.value = result.success
      ? `${result.message}${result.model_count ? `，发现 ${result.model_count} 个模型` : ''}`
      : result.message
    if (result.success) {
      passedTestSignature.value = currentTestSignature.value
    }
  } catch (error) {
    testStatus.value = 'error'
    testMessage.value = getErrorMessage(error, '连接测试失败')
  }
}

const handleSubmit = () => {
  if (!canSubmit.value) {
    testStatus.value = 'error'
    testMessage.value = '请先完成连接测试并通过后再确认接入'
    passedTestSignature.value = ''
    return
  }

  emit('submit', buildPayload())
}
</script>

<style scoped>
.provider-config-modal {
  padding: 24px;
  font-size: var(--model-font-body, 12px);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.modal-header h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--model-font-title, 14px);
  line-height: 1.5;
}

.modal-header p {
  margin: 6px 0 0;
  color: var(--text-tertiary);
  font-size: var(--model-font-body, 12px);
  line-height: 1.6;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  cursor: pointer;
}

.template-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
}

.tag {
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  background: var(--brand-primary-light);
  color: var(--brand-primary);
}

.subtle-tag {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

.modal-form {
  display: grid;
  gap: 14px;
}

.grid-two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.form-item {
  display: grid;
  gap: 8px;
}

.form-item span {
  color: var(--text-primary);
  font-size: var(--model-font-body, 12px);
  font-weight: 600;
  line-height: 1.5;
}

.form-item em {
  color: var(--danger-color);
  font-style: normal;
}

.form-item input,
.form-item select,
.form-item textarea {
  width: 100%;
  min-height: 44px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  padding: 12px 14px;
  font-size: var(--model-font-body, 12px);
}

.form-item input:disabled {
  background: var(--surface-overlay);
  color: var(--text-tertiary);
}

.form-item input:focus,
.form-item select:focus,
.form-item textarea:focus {
  outline: none;
  border-color: var(--brand-primary);
  background: var(--bg-secondary);
  box-shadow: 0 0 0 4px var(--brand-primary-light);
}

.test-panel {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 16px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
}

.test-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.test-hint {
  color: var(--text-tertiary);
  font-size: var(--model-font-meta, 11px);
  line-height: 1.5;
}

.test-message,
.error-text {
  margin: 0;
  padding: 12px 14px;
  border-radius: 14px;
}

.test-message.success {
  background: var(--success-soft);
  color: var(--success-color);
}

.test-message.error,
.error-text {
  background: var(--danger-soft);
  color: var(--danger-color);
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-primary);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 768px) {
  .provider-config-modal {
    padding: 18px;
  }

  .grid-two,
  .test-actions {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: stretch;
  }

  .modal-footer {
    flex-direction: column-reverse;
  }
}
</style>
