import axios from 'axios'

import { http } from '../lib/http'

export type ModelType = 'llm' | 'embedding' | 'rerank' | 'tts' | 'asr' | 'vlm' | 'moderation' | 'ocr'
export type DeploymentType = 'public' | 'private'
export type SyncStatus = 'pending' | 'success' | 'failed'

export const MODEL_TYPE_ORDER: ModelType[] = [
  'llm',
  'embedding',
  'vlm',
  'asr',
  'rerank',
  'tts',
  'moderation',
  'ocr',
]

export const MODEL_TYPE_LABEL_MAP: Record<ModelType, string> = {
  llm: 'LLM',
  embedding: 'Embedding',
  rerank: 'Rerank',
  tts: 'TTS',
  asr: 'ASR',
  vlm: 'VLM',
  moderation: 'Moderation',
  ocr: 'OCR',
}

export interface AuthField {
  key: string
  label: string
  type: string
  required: boolean
}

export interface ProviderTemplate {
  provider_code: string
  provider_name: string
  deployment_type: DeploymentType
  default_base_url: string
  supported_types: ModelType[]
  auth_type: string
  auth_fields: AuthField[]
}

export interface ProviderSummary {
  id: number
  provider_code: string
  provider_name: string
  deployment_type: DeploymentType
  base_url: string
  supported_types: ModelType[]
  sync_status: SyncStatus
  last_sync_at: string | null
  last_sync_error: string | null
  model_total: number
  enabled_model_total: number
  remark: string | null
  created_at: string
  updated_at: string
}

export interface ProviderDetail extends ProviderSummary {
  auth_type: string
  auth_fields: AuthField[]
  has_auth_config: boolean
}

export interface ProviderCreatePayload {
  provider_code: string
  provider_name: string
  deployment_type: DeploymentType
  base_url: string
  auth_type: string
  auth_config: Record<string, string>
  remark?: string
  auto_sync_models?: boolean
}

export type ProviderUpdatePayload = Partial<ProviderCreatePayload>

export interface ProviderCreateResult {
  provider_id: number
  provider_name: string
  sync_status: SyncStatus
  model_count: number
}

export interface ProviderSyncResult {
  provider_id: number
  added: number
  updated: number
  disabled: number
  sync_status: SyncStatus
  model_count: number
}

export interface ProviderTestResult {
  success: boolean
  message: string
  response_time_ms?: number | null
  model_name?: string | null
  model_count?: number | null
}

export interface ModelItem {
  id: number
  provider_id: number
  provider_name: string
  provider_code: string
  model_code: string
  model_name: string
  model_type: ModelType
  is_enabled: boolean
  capabilities: string[]
  context_window: number | null
  max_output_tokens: number | null
  is_default: boolean
  raw_payload?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ProviderModelsGroup {
  provider_id: number
  provider_name: string
  provider_code: string
  deployment_type: DeploymentType
  supported_types: ModelType[]
  sync_status: SyncStatus
  last_sync_at: string | null
  last_sync_error: string | null
  model_total: number
  enabled_model_total: number
  models: ModelItem[]
}

export interface DefaultModelOption {
  model_id: number
  model_name: string
  provider_name: string
}

export type DefaultsData = Record<ModelType, DefaultModelOption | null>

interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
}

const isEnvelope = <T>(value: unknown): value is ApiEnvelope<T> => {
  return Boolean(value) && typeof value === 'object' && 'code' in (value as Record<string, unknown>) && 'data' in (value as Record<string, unknown>)
}

const unwrap = async <T>(request: Promise<{ data: T | ApiEnvelope<T> }>): Promise<T> => {
  const response = await request
  return isEnvelope<T>(response.data) ? response.data.data : (response.data as T)
}

export const getErrorMessage = (error: unknown, fallback = '操作失败') => {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined
    const message = data?.message || data?.detail
    if (typeof message === 'string' && message.trim()) {
      return message
    }
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  return fallback
}

export const providerApi = {
  getProviderTemplates(params?: { model_type?: ModelType; keyword?: string }) {
    return unwrap<ProviderTemplate[]>(http.get('/api/v1/ai-models/provider-templates', { params }))
  },
  getProviders(params?: { keyword?: string; deployment_type?: DeploymentType }) {
    return unwrap<ProviderSummary[]>(http.get('/api/v1/ai-models/providers', { params }))
  },
  createProvider(payload: ProviderCreatePayload) {
    return unwrap<ProviderCreateResult>(http.post('/api/v1/ai-models/providers', payload))
  },
  getProviderDetail(providerId: number) {
    return unwrap<ProviderDetail>(http.get(`/api/v1/ai-models/providers/${providerId}`))
  },
  updateProvider(providerId: number, payload: ProviderUpdatePayload) {
    return unwrap<ProviderDetail>(http.put(`/api/v1/ai-models/providers/${providerId}`, payload))
  },
  deleteProvider(providerId: number) {
    return unwrap<boolean>(http.delete(`/api/v1/ai-models/providers/${providerId}`))
  },
  syncProviderModels(providerId: number) {
    return unwrap<ProviderSyncResult>(http.post(`/api/v1/ai-models/providers/${providerId}/sync`))
  },
  testProvider(providerId: number) {
    return unwrap<ProviderTestResult>(http.post(`/api/v1/ai-models/providers/${providerId}/test`))
  },
  testProviderConnection(payload: ProviderCreatePayload) {
    return unwrap<ProviderTestResult>(http.post('/api/v1/ai-models/providers/test-connection', payload))
  },
}

export const modelApi = {
  getModels(params?: {
    provider_id?: number
    model_type?: ModelType
    is_enabled?: boolean
    keyword?: string
    view?: 'grouped' | 'flat'
  }) {
    return unwrap<ModelItem[] | ProviderModelsGroup[]>(http.get('/api/v1/ai-models/models', { params }))
  },
  getModelDetail(modelId: number) {
    return unwrap<ModelItem>(http.get(`/api/v1/ai-models/models/${modelId}`))
  },
  toggleModelEnabled(modelId: number, payload: { is_enabled: boolean }) {
    return unwrap<{ id: number; is_enabled: boolean }>(http.patch(`/api/v1/ai-models/models/${modelId}/enabled`, payload))
  },
}

export const defaultModelApi = {
  getDefaults() {
    return unwrap<DefaultsData>(http.get('/api/v1/ai-models/defaults'))
  },
  saveDefaults(payload: Record<ModelType, number | null>) {
    return unwrap<boolean>(http.put('/api/v1/ai-models/defaults', payload))
  },
  saveSingleDefault(modelType: ModelType, payload: { model_id: number | null }) {
    return unwrap<{ model_type: ModelType; model_id: number | null }>(http.put(`/api/v1/ai-models/defaults/${modelType}`, payload))
  },
}
