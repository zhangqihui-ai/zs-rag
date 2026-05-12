/**
 * Chat completion stream over HTTP POST + Server-Sent Events (SSE).
 * Each event is one line: `data: <json>\n\n` where json matches legacy WebSocket payloads.
 */

const sseBaseUrl = (): string => {
  const env = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (env != null && String(env).trim().length > 0) {
    return String(env).replace(/\/$/, '')
  }
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location
    return `${protocol}//${hostname}:8000`
  }
  return 'http://localhost:8000'
}

export async function streamChatCompletion(
  sessionId: string,
  content: string,
  onEvent: (data: unknown) => void,
  options?: { signal?: AbortSignal },
): Promise<void> {
  const token = localStorage.getItem('auth_token') || ''
  const enterpriseSpace = localStorage.getItem('current_enterprise_space')
  const res = await fetch(`${sseBaseUrl()}/api/v1/chats/sessions/${sessionId}/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(enterpriseSpace ? { 'X-Enterprise-Space': enterpriseSpace } : {}),
    },
    body: JSON.stringify({ content }),
    signal: options?.signal,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = (await res.json()) as { message?: string; detail?: unknown }
      if (typeof j?.message === 'string' && j.message.trim()) {
        detail = j.message
      } else if (j?.detail != null) {
        detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
      }
    } catch {
      try {
        const t = await res.text()
        if (t.trim()) {
          detail = t
        }
      } catch {
        /* noop */
      }
    }
    throw new Error(`${res.status}: ${detail}`)
  }

  if (!res.body) {
    throw new Error('响应无 body（无法读取 SSE）')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })

    let sep: number
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      for (const line of block.split('\n')) {
        const t = line.trim()
        if (!t.startsWith('data:')) {
          continue
        }
        const jsonStr = t.slice(5).trimStart()
        if (jsonStr === '[DONE]') {
          continue
        }
        try {
          onEvent(JSON.parse(jsonStr) as unknown)
        } catch (e) {
          console.warn('SSE JSON 解析跳过', jsonStr, e)
        }
      }
    }
  }
}
