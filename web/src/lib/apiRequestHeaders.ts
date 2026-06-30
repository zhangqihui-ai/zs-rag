/** 供 nginx 识别为 API 请求，避免 /knowledge-bases 等路径误回退 index.html */
export const ZS_RAG_API_HEADER = 'X-ZS-RAG-API'
export const ZS_RAG_API_VALUE = '1'

export function buildApiRequestHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_token') || '' : ''
  return {
    Accept: 'application/json',
    [ZS_RAG_API_HEADER]: ZS_RAG_API_VALUE,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  }
}
