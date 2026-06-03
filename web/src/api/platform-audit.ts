import { http } from '../lib/http'

export interface PlatformAuditEvent {
  id: number
  enterprise_space_id: number | null
  user_id: number | null
  username: string | null
  space_name: string | null
  action: string
  resource_type: string
  resource_id: string | null
  request_id: string | null
  ip_address: string | null
  detail: Record<string, unknown> | null
  message: string | null
  created_at: string
}

export interface PlatformAuditListResponse {
  items: PlatformAuditEvent[]
  total: number
  skip: number
  limit: number
}

export interface PlatformAuditListParams {
  enterprise_space_id?: number
  user_id?: number
  action?: string
  resource_type?: string
  created_from?: string
  created_to?: string
  skip?: number
  limit?: number
}

export async function listPlatformAuditEvents(params?: PlatformAuditListParams) {
  return http.get<PlatformAuditListResponse>('/platform-audit/events', { params })
}

export const PLATFORM_AUDIT_ACTION_LABELS: Record<string, string> = {
  'auth.login': '用户登录',
  'admin.user.create': '创建用户',
  'admin.user.update': '更新用户',
  'admin.user.delete': '删除用户',
  'admin.user.memberships.update': '更新用户空间分配',
  'knowledge_base.create': '创建知识库',
  'knowledge_base.update': '更新知识库',
  'knowledge_base.delete': '删除知识库',
  'model.provider.create': '创建模型 Provider',
  'model.provider.update': '更新模型 Provider',
  'model.provider.delete': '删除模型 Provider',
  'model.enabled.update': '更新启用模型',
  'model.defaults.update': '更新默认模型',
  'chat.session.delete': '删除对话会话',
  'chat.conversation.delete': '删除对话记录',
  'audit.test': '审计测试',
}

export const PLATFORM_AUDIT_RESOURCE_TYPE_LABELS: Record<string, string> = {
  user: '用户',
  knowledge_base: '知识库',
  model: '模型',
  chat: '对话',
  system: '系统',
}

export function formatAuditAction(action: string) {
  return PLATFORM_AUDIT_ACTION_LABELS[action] || action
}

export function formatAuditResourceType(resourceType: string) {
  return PLATFORM_AUDIT_RESOURCE_TYPE_LABELS[resourceType] || resourceType
}
