import { http } from '../lib/http'

export interface ParserCapabilities {
  mineru: {
    enabled: boolean
    formats: string[]
  }
}

export type ComponentStatus = 'alive' | 'dead' | 'disabled' | 'unknown'

export interface ServiceComponentItem {
  id: string
  name: string
  service_type: string
  host: string
  port: number
  status: ComponentStatus
  message?: string | null
  response_time_ms?: number | null
  exposed: boolean
  external_port?: number | null
  visit_port?: number | null
  visit_path?: string | null
  visit_label?: string | null
  credentials?: ComponentCredential[]
}

export interface ComponentCredential {
  label: string
  value: string
}

export interface ServiceComponentsStatusResponse {
  checked_at: string
  items: ServiceComponentItem[]
}

interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
}

const isEnvelope = <T>(value: unknown): value is ApiEnvelope<T> => {
  return Boolean(value) && typeof value === 'object' && 'code' in (value as Record<string, unknown>) && 'data' in (value as Record<string, unknown>)
}

function unwrapParserCapabilities(raw: unknown): ParserCapabilities {
  const payload = isEnvelope<ParserCapabilities>(raw) ? raw.data : raw
  if (
    payload
    && typeof payload === 'object'
    && 'mineru' in payload
    && typeof (payload as ParserCapabilities).mineru?.enabled === 'boolean'
  ) {
    return payload as ParserCapabilities
  }
  throw new Error('无效的 parser-capabilities 响应')
}

function unwrapServiceComponentsStatus(raw: unknown): ServiceComponentsStatusResponse {
  const payload = isEnvelope<ServiceComponentsStatusResponse>(raw) ? raw.data : raw
  if (
    payload
    && typeof payload === 'object'
    && 'items' in payload
    && Array.isArray((payload as ServiceComponentsStatusResponse).items)
  ) {
    return payload as ServiceComponentsStatusResponse
  }
  throw new Error('无效的服务组件状态响应')
}

export async function fetchParserCapabilities(): Promise<ParserCapabilities> {
  const { data } = await http.get<ParserCapabilities | ApiEnvelope<ParserCapabilities>>('/system/parser-capabilities')
  return unwrapParserCapabilities(data)
}

export async function fetchServiceComponentsStatus(): Promise<ServiceComponentsStatusResponse> {
  const { data } = await http.get<ServiceComponentsStatusResponse | ApiEnvelope<ServiceComponentsStatusResponse>>(
    '/system/components/status',
  )
  return unwrapServiceComponentsStatus(data)
}

export function buildComponentVisitUrl(item: ServiceComponentItem): string | null {
  if (!item.exposed || !item.visit_port) {
    return null
  }
  const path = item.visit_path ?? ''
  return `${window.location.protocol}//${window.location.hostname}:${item.visit_port}${path}`
}

export function buildComponentExternalEndpoint(item: ServiceComponentItem): string | null {
  if (!item.exposed || !item.external_port) {
    return null
  }
  return `${window.location.hostname}:${item.external_port}`
}

export type ComponentAccessLine = {
  label: string
  text: string
  href?: string
  copyable?: boolean
}

export function buildComponentAccessLines(item: ServiceComponentItem): ComponentAccessLine[] {
  const lines: ComponentAccessLine[] = []
  const visit = buildComponentVisitUrl(item)
  if (visit) {
    lines.push({
      label: item.visit_label || '访问',
      text: visit,
      href: visit,
    })
  }

  const external = buildComponentExternalEndpoint(item)
  const showExternal = external && (!visit || item.external_port !== item.visit_port)
  if (showExternal && external) {
    lines.push({
      label: item.id === 'milvus' ? 'gRPC' : '连接地址',
      text: external,
      copyable: true,
    })
  }

  return lines
}
