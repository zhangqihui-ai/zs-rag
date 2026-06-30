/** 聊天对外 REST 接入说明（与 backend chats / chat-completions 路由一致） */

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

export interface ChatApiAccessContext {
  apiBaseUrl: string
  chatId: string
  sessionId: string
  spaceSlug: string
}

export interface ChatApiEndpointDef {
  id: string
  method: HttpMethod
  /** 相对路径，含 {chat_id} / {session_id} 占位 */
  pathTemplate: string
  summary: string
  bodyExample?: string
  notes?: string
}

export interface ChatApiGroupDef {
  id: string
  title: string
  description?: string
  endpoints: ChatApiEndpointDef[]
}

const PLACEHOLDER_CHAT = '<chat_id>'
const PLACEHOLDER_SESSION = '<session_id>'

export function resolveApiPath(
  pathTemplate: string,
  ctx: Pick<ChatApiAccessContext, 'chatId' | 'sessionId'>,
): string {
  const chatId = ctx.chatId.trim() || PLACEHOLDER_CHAT
  const sessionId = ctx.sessionId.trim() || PLACEHOLDER_SESSION
  return pathTemplate.replace('{chat_id}', chatId).replace('{session_id}', sessionId)
}

export function fullApiUrl(apiBaseUrl: string, pathTemplate: string, ctx: ChatApiAccessContext): string {
  const base = apiBaseUrl.replace(/\/$/, '')
  return `${base}${resolveApiPath(pathTemplate, ctx)}`
}

export function buildAuthHeadersExample(spaceSlug: string): string {
  const space = spaceSlug.trim() || 'default'
  return [
    'Authorization: Bearer <access_token 或嵌入 API Key>',
    '# 嵌入 API Key：可不传 X-Enterprise-Space（服务端按 Key 自动识别企业空间）',
    '# 登录 JWT：多企业空间时建议传；省略时默认为 default',
    `X-Enterprise-Space: ${space}  # 可选`,
    'Content-Type: application/json',
  ].join('\n')
}

export function buildCurlExample(
  method: HttpMethod,
  url: string,
  opts?: { body?: string; spaceSlug?: string },
): string {
  const lines = [`curl -X ${method} '${url}' \\`]
  lines.push(`  -H 'Authorization: Bearer <token>' \\`)
  if (opts?.spaceSlug) {
    lines.push(`  -H 'X-Enterprise-Space: ${opts.spaceSlug.trim()}' \\`)
  }
  if (opts?.body) {
    lines.push(`  -H 'Content-Type: application/json' \\`)
    const compact = opts.body.replace(/\n\s*/g, ' ').trim()
    lines.push(`  -d '${compact.replace(/'/g, "'\\''")}'`)
  } else {
    const last = lines.length - 1
    lines[last] = lines[last]!.replace(/ \\$/, '')
  }
  return lines.join('\n')
}

/** 对外暴露的聊天 REST 分组（不含嵌入密钥管理，见「嵌入网站」） */
export function buildChatApiAccessGroups(): ChatApiGroupDef[] {
  return [
    {
      id: 'conversation',
      title: '1. 对话（Chat）',
      description: '一个对话对应一套模型/知识库配置，其下可挂多个会话。',
      endpoints: [
        {
          id: 'list-chats',
          method: 'GET',
          pathTemplate: '/api/v1/chats',
          summary: '列出当前用户在本企业空间下的对话',
          notes: 'Query: skip（默认 0）、limit（默认 100）',
        },
        {
          id: 'create-chat',
          method: 'POST',
          pathTemplate: '/api/v1/chats',
          summary: '创建对话',
          bodyExample: `{
  "title": "新建对话",
  "configuration": {
    "model_id": 1,
    "knowledge_base_ids": [],
    "system_prompt": "你是助手…",
    "temperature": 0.7,
    "max_tokens": 2000,
    "top_p": 1.0,
    "show_citations": true,
    "retrieval_top_k": 5,
    "vector_retrieval_top_k": 8,
    "lightrag_retrieval_top_k": 8
  }
}`,
        },
        {
          id: 'get-chat',
          method: 'GET',
          pathTemplate: '/api/v1/chats/{chat_id}',
          summary: '获取单个对话详情（含模型与知识库配置）',
        },
        {
          id: 'update-chat',
          method: 'PUT',
          pathTemplate: '/api/v1/chats/{chat_id}',
          summary: '修改对话标题',
          bodyExample: '{ "title": "新标题" }',
        },
        {
          id: 'delete-chat',
          method: 'DELETE',
          pathTemplate: '/api/v1/chats/{chat_id}',
          summary: '删除对话（其下会话与消息一并删除）',
        },
      ],
    },
    {
      id: 'sessions-under-chat',
      title: '2. 会话（Session）— 隶属于某对话',
      description: '在指定 chat_id 下创建与管理多轮会话线程。',
      endpoints: [
        {
          id: 'list-sessions',
          method: 'GET',
          pathTemplate: '/api/v1/chats/{chat_id}/sessions',
          summary: '列出该对话下的全部会话',
        },
        {
          id: 'create-session',
          method: 'POST',
          pathTemplate: '/api/v1/chats/{chat_id}/sessions',
          summary: '在该对话下新建会话',
          bodyExample: '{ "title": "新会话" }',
        },
      ],
    },
    {
      id: 'session-manage',
      title: '3. 会话（Session）— 按 session_id 管理',
      description: '路径前缀固定为 /api/v1/chats/sessions/，避免与 chat_id 路由冲突。',
      endpoints: [
        {
          id: 'get-session',
          method: 'GET',
          pathTemplate: '/api/v1/chats/sessions/{session_id}',
          summary: '获取会话元信息',
        },
        {
          id: 'update-session',
          method: 'PUT',
          pathTemplate: '/api/v1/chats/sessions/{session_id}',
          summary: '修改会话标题',
          bodyExample: '{ "title": "会话标题" }',
        },
        {
          id: 'delete-session',
          method: 'DELETE',
          pathTemplate: '/api/v1/chats/sessions/{session_id}',
          summary: '删除会话及其消息记录',
        },
      ],
    },
    {
      id: 'session-data',
      title: '4. 会话消息与配置',
      endpoints: [
        {
          id: 'list-messages',
          method: 'GET',
          pathTemplate: '/api/v1/chats/sessions/{session_id}/messages',
          summary: '获取会话历史消息',
          notes: 'Query: skip（默认 0）、limit（默认 100）',
        },
        {
          id: 'get-config',
          method: 'GET',
          pathTemplate: '/api/v1/chats/sessions/{session_id}/config',
          summary: '读取所属对话的模型/知识库配置（经 session 定位）',
        },
        {
          id: 'update-config',
          method: 'PUT',
          pathTemplate: '/api/v1/chats/sessions/{session_id}/config',
          summary: '更新所属对话的配置（本对话下所有会话共用）',
          bodyExample: `{
  "model_id": 1,
  "knowledge_base_ids": [1, 2],
  "system_prompt": "…",
  "temperature": 0.7,
  "max_tokens": 2000,
  "top_p": 1.0,
  "show_citations": true,
  "retrieval_top_k": 5,
  "vector_retrieval_top_k": 8,
  "lightrag_retrieval_top_k": 8
}`,
        },
      ],
    },
    {
      id: 'chat-inference',
      title: '5. 聊天推理（发送消息）',
      description: '推荐 OpenAI 官方请求/响应格式；路径二选一。',
      endpoints: [
        {
          id: 'openai-completions',
          method: 'POST',
          pathTemplate: '/api/v1/openai/{chat_id}/chat/completions',
          summary: '【推荐】OpenAI 标准路径（chat_id 在 URL，body 与 OpenAI 一致）',
          bodyExample: `{
  "model": "text-embedding-v4",
  "messages": [{"role": "user", "content": "Say this is a test!"}],
  "stream": true,
  "session_id": "{session_id}"
}`,
          notes:
            '响应对齐 OpenAI：流式为 chat.completion.chunk（含 delta.role/content、finish_reason、末帧 usage）；非流式为 chat.completion + usage。扩展字段 chat_id、session_id 会附在 JSON 根级。messages 末条须为 user。',
        },
        {
          id: 'completions',
          method: 'POST',
          pathTemplate: '/api/v1/chat/completions',
          summary: '兼容路径：chat_id 放在请求体',
          bodyExample: `{
  "chat_id": "{chat_id}",
  "session_id": "{session_id}",
  "model": "your-model",
  "messages": [{"role": "user", "content": "你好"}],
  "stream": true
}`,
          notes: '与上接口行为相同；也可用 question 字段代替 messages（旧客户端）。',
        },
        {
          id: 'stream-sse',
          method: 'POST',
          pathTemplate: '/api/v1/chats/sessions/{session_id}/stream',
          summary: '站内 SSE 协议（assistant_delta / assistant_done）',
          bodyExample: '{ "content": "用户本轮输入的纯文本" }',
          notes: '响应 Content-Type: text/event-stream，每行 data: <json>',
        },
      ],
    },
  ]
}

export function countChatApiEndpoints(groups: ChatApiGroupDef[]): number {
  return groups.reduce((n, g) => n + g.endpoints.length, 0)
}

export type ApiAccessMode = 'zs-rag' | 'openai'

const OPENAI_COMPLETION_ENDPOINT_IDS = new Set(['openai-completions', 'completions'])

/** 按接入方式筛选接口目录（zs-rag 原生 REST+SSE / OpenAI 兼容补全） */
export function filterChatApiAccessGroups(
  groups: ChatApiGroupDef[],
  mode: ApiAccessMode,
): ChatApiGroupDef[] {
  if (mode === 'openai') {
    const inference = groups.find((g) => g.id === 'chat-inference')
    const endpoints =
      inference?.endpoints.filter((ep) => OPENAI_COMPLETION_ENDPOINT_IDS.has(ep.id)) ?? []
    return [
      {
        id: 'openai-completions',
        title: 'OpenAI Chat Completions',
        description:
          '请求/响应字段与 OpenAI 官方 POST /v1/chat/completions 对齐；chat_id 放在 URL。扩展字段 session_id、question 见文档。',
        endpoints,
      },
    ]
  }

  return []
}

/** zs-rag 弹窗：对话级 SSE curl（自动建会话，assistant_done 含 session_id） */
export function buildZsRagChatLevelCurl(ctx: ChatApiAccessContext): string {
  const url = fullApiUrl(ctx.apiBaseUrl, '/api/v1/chats/{chat_id}/stream', ctx)
  const body = JSON.stringify({ content: 'Hello!' }, null, 2)
  return [
    `curl ${url} \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -H "Authorization: Bearer $ZS_RAG_API_KEY" \\`,
    `  -d '${body.replace(/'/g, "'\\''")}'`,
  ].join('\n')
}

/** zs-rag 弹窗：会话级站内 SSE */
export function buildZsRagSessionStreamCurl(ctx: ChatApiAccessContext): string {
  const url = fullApiUrl(ctx.apiBaseUrl, '/api/v1/chats/sessions/{session_id}/stream', ctx)
  const body = JSON.stringify({ content: 'Hello!' }, null, 2)
  return [
    `curl -N ${url} \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -H "Authorization: Bearer $ZS_RAG_API_KEY" \\`,
    `  -d '${body.replace(/'/g, "'\\''")}'`,
  ].join('\n')
}

/** zs-rag 弹窗：会话级非流式（assistant_done JSON） */
export function buildZsRagSessionCompletionCurl(ctx: ChatApiAccessContext): string {
  const url = fullApiUrl(ctx.apiBaseUrl, '/api/v1/chats/sessions/{session_id}/complete', ctx)
  const body = JSON.stringify({ content: 'Hello!' }, null, 2)
  return [
    `curl ${url} \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -H "Authorization: Bearer $ZS_RAG_API_KEY" \\`,
    `  -d '${body.replace(/'/g, "'\\''")}'`,
  ].join('\n')
}

/** 弹窗用：仅 2 个 zs-rag 原生接入场景 */
export function buildZsRagApiAccessGroups(): ChatApiGroupDef[] {
  return [
    {
      id: 'zs-rag-chat-level',
      title: '1. 对话级（不携带 session_id）',
      description:
        '仅传 chat_id。服务端自动创建新会话并返回站内 SSE；assistant_done 事件含 session_id，请复制保存供接口 2 使用。',
      endpoints: [
        {
          id: 'chat-level-stream',
          method: 'POST',
          pathTemplate: '/api/v1/chats/{chat_id}/stream',
          summary: '自动建会话 + 站内 SSE（assistant_delta / assistant_done）',
          bodyExample: '{ "content": "用户本轮输入的纯文本" }',
          notes: '无需 session_id。assistant_done 含 session_id、content、citations。',
        },
      ],
    },
    {
      id: 'zs-rag-session-level',
      title: '2. 会话级（绑定当前 session_id）',
      description: '使用上方复制的 session_id，在已有会话内多轮对话；支持流式与非流式。',
      endpoints: [
        {
          id: 'session-stream-sse',
          method: 'POST',
          pathTemplate: '/api/v1/chats/sessions/{session_id}/stream',
          summary: '流式：站内 SSE（assistant_delta / assistant_done）',
          bodyExample: '{ "content": "用户本轮输入的纯文本" }',
          notes: '请求体仅 content；Content-Type: text/event-stream。',
        },
        {
          id: 'session-completion',
          method: 'POST',
          pathTemplate: '/api/v1/chats/sessions/{session_id}/complete',
          summary: '非流式：返回 assistant_done JSON',
          bodyExample: '{ "content": "用户本轮输入的纯文本" }',
          notes: '响应为单条 JSON（含 session_id、content、citations），非 SSE。',
        },
      ],
    },
  ]
}

const PLACEHOLDER_NEW_SESSION = '<new_session_id>'

function formatSseLines(chunks: string[], trailingDone = false): string {
  const lines = chunks.map((c) => `data: ${c}`)
  if (trailingDone) {
    lines.push('data: [DONE]')
  }
  return lines.join('\n\n')
}

/** OpenAI 流式 SSE 响应示例 */
export function buildOpenAiStreamResponseExample(ctx: ChatApiAccessContext): string {
  const chatId = ctx.chatId.trim() || PLACEHOLDER_CHAT
  const sessionId = ctx.sessionId.trim() || PLACEHOLDER_NEW_SESSION
  const chunk = JSON.stringify({
    id: 'chatcmpl-...',
    object: 'chat.completion.chunk',
    created: 1694268190,
    model: 'deepseek-chat',
    choices: [
      {
        index: 0,
        delta: { content: 'Hello', role: 'assistant', function_call: null, tool_calls: null, reasoning_content: null },
        finish_reason: null,
        logprobs: null,
      },
    ],
    usage: null,
    chat_id: chatId,
    session_id: sessionId,
  })
  const lastChunk = JSON.stringify({
    id: 'chatcmpl-...',
    object: 'chat.completion.chunk',
    created: 1694268190,
    model: 'deepseek-chat',
    choices: [
      {
        index: 0,
        delta: { content: null, role: 'assistant', function_call: null, tool_calls: null, reasoning_content: null },
        finish_reason: 'stop',
        logprobs: null,
      },
    ],
    usage: { prompt_tokens: 5, completion_tokens: 10, total_tokens: 15 },
    chat_id: chatId,
    session_id: sessionId,
  })
  return formatSseLines([chunk, lastChunk], true)
}

/** OpenAI 非流式 JSON 响应示例 */
export function buildOpenAiNonStreamResponseExample(ctx: ChatApiAccessContext): string {
  const chatId = ctx.chatId.trim() || PLACEHOLDER_CHAT
  const sessionId = ctx.sessionId.trim() || PLACEHOLDER_NEW_SESSION
  return JSON.stringify(
    {
      id: 'chatcmpl-...',
      object: 'chat.completion',
      created: 1694268190,
      model: 'deepseek-chat',
      choices: [
        {
          index: 0,
          message: { role: 'assistant', content: 'Hello!' },
          finish_reason: 'stop',
          logprobs: null,
        },
      ],
      usage: {
        prompt_tokens: 5,
        completion_tokens: 10,
        total_tokens: 15,
      },
      chat_id: chatId,
      session_id: sessionId,
    },
    null,
    2,
  )
}

/** zs-rag 站内 SSE 响应示例 */
export function buildZsRagSseResponseExample(
  ctx: ChatApiAccessContext,
  opts?: { newSession?: boolean },
): string {
  const sessionId = opts?.newSession
    ? PLACEHOLDER_NEW_SESSION
    : ctx.sessionId.trim() || PLACEHOLDER_SESSION
  const delta = JSON.stringify({ type: 'assistant_delta', content: '片段' })
  const done = JSON.stringify({
    type: 'assistant_done',
    id: '550e8400-e29b-41d4-a716-446655440000',
    session_id: sessionId,
    role: 'assistant',
    content: '完整回复',
    created_at: '2026-01-01T00:00:00',
    citations: [],
  })
  return formatSseLines([delta, done], false)
}

/** zs-rag 非流式 assistant_done JSON 响应示例 */
export function buildZsRagCompleteResponseExample(ctx: ChatApiAccessContext): string {
  const sessionId = ctx.sessionId.trim() || PLACEHOLDER_SESSION
  return JSON.stringify(
    {
      type: 'assistant_done',
      id: '550e8400-e29b-41d4-a716-446655440000',
      session_id: sessionId,
      role: 'assistant',
      content: '完整回复',
      created_at: '2026-01-01T00:00:00',
      citations: [],
    },
    null,
    2,
  )
}

export const ZS_RAG_SSE_EVENTS_EXAMPLE = buildZsRagSseResponseExample({
  apiBaseUrl: '',
  chatId: '',
  sessionId: '',
})

/** OpenAI 兼容：SDK base_url（chat_id 在路径中） */
export function buildOpenAiChatCompletionsBaseUrl(
  apiBaseUrl: string,
  chatId: string,
): string {
  const base = apiBaseUrl.replace(/\/$/, '')
  const id = chatId.trim() || PLACEHOLDER_CHAT
  return `${base}/api/v1/openai/${id}`
}

export function buildOpenAiChatCompletionsUrl(
  apiBaseUrl: string,
  chatId: string,
): string {
  return `${buildOpenAiChatCompletionsBaseUrl(apiBaseUrl, chatId)}/chat/completions`
}

/** 弹窗用 curl 示例（对齐 OpenAI 官方 Create chat completion） */
export function buildOpenAiAccessCurl(
  ctx: ChatApiAccessContext,
  opts?: { stream?: boolean; model?: string },
): string {
  const stream = opts?.stream !== false
  const url = buildOpenAiChatCompletionsUrl(ctx.apiBaseUrl, ctx.chatId)
  const body: Record<string, unknown> = {
    model: opts?.model?.trim() || 'deepseek-chat',
    messages: [{ role: 'user', content: 'Hello!' }],
    stream,
  }
  const sid = ctx.sessionId.trim()
  if (sid) {
    body.extra_body = { session_id: sid }
  }
  const bodyJson = JSON.stringify(body, null, 2)
  const lines = [
    `curl ${url} \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -H "Authorization: Bearer $OPENAI_API_KEY" \\`,
    `  -d '${bodyJson.replace(/'/g, "'\\''")}'`,
  ]
  return lines.join('\n')
}

/** 弹窗用 Python SDK 示例 */
export function buildOpenAiAccessPython(
  ctx: ChatApiAccessContext,
  opts?: { stream?: boolean },
): string {
  const stream = opts?.stream !== false
  const base = buildOpenAiChatCompletionsBaseUrl(ctx.apiBaseUrl, ctx.chatId)
  const sid = ctx.sessionId.trim()
  const extra = sid ? `\n    extra_body={"session_id": "${sid}"},` : ''
  return `from openai import OpenAI

client = OpenAI(
    api_key="<嵌入 API Key 或 JWT>",
    base_url="${base}",
)
client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=${stream ? 'True' : 'False'},${extra}
)`
}

export type OpenAiClientLang = 'http' | 'python'

export const OPENAI_STREAM_SSE_EXAMPLE = `data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello","role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"content":null},"finish_reason":"stop"}],"usage":{"prompt_tokens":5,"completion_tokens":10,"total_tokens":15}}

data: [DONE]`

/** 将 body 示例中的占位符替换为当前对话/会话 ID */
export function resolveBodyExample(
  body: string | undefined,
  ctx: Pick<ChatApiAccessContext, 'chatId' | 'sessionId'>,
): string | undefined {
  if (!body) return undefined
  const chatId = ctx.chatId.trim() || PLACEHOLDER_CHAT
  const sessionId = ctx.sessionId.trim() || PLACEHOLDER_SESSION
  return body.replace(/\{chat_id\}/g, chatId).replace(/\{session_id\}/g, sessionId)
}

/** 静态文档（与 docs/ 目录下 md 同步，供页面下载） */
export const CHAT_API_DOC_FILENAME = '聊天对话对外API接入文档.md'
export const CHAT_API_DOC_PUBLIC_PATH = `/docs/${CHAT_API_DOC_FILENAME}`
export const OPENAI_EXAMPLE_DOC_FILENAME = 'openai接口示例.md'
export const OPENAI_EXAMPLE_DOC_PUBLIC_PATH = `/docs/${OPENAI_EXAMPLE_DOC_FILENAME}`

/** 由接口目录生成 Markdown（fetch 失败时的回退内容） */
export function buildChatApiAccessMarkdown(
  ctx: ChatApiAccessContext,
  groups: ChatApiGroupDef[] = buildChatApiAccessGroups(),
): string {
  const base = ctx.apiBaseUrl.replace(/\/$/, '')
  const lines: string[] = [
    '# 聊天对话对外 API 接入文档',
    '',
    '> 由平台根据当前环境自动生成；完整版见仓库 `docs/聊天对话对外API接入文档.md`。',
    '',
    `**Base URL：** \`${base}\``,
    '',
    '## 认证',
    '',
    '```http',
    buildAuthHeadersExample(ctx.spaceSlug),
    '```',
    '',
    '- **嵌入 API Key**：仅需 `Authorization`，无需 `X-Enterprise-Space`。',
    '- **登录 JWT**：非 default 空间建议传 `X-Enterprise-Space`。',
    '',
    '## 接口列表',
    '',
  ]

  for (const group of groups) {
    lines.push(`### ${group.title}`, '')
    if (group.description) {
      lines.push(group.description, '')
    }
    for (const ep of group.endpoints) {
      const path = resolveApiPath(ep.pathTemplate, ctx)
      const url = `${base}${path}`
      lines.push(`#### \`${ep.method} ${path}\``, '')
      lines.push(ep.summary, '')
      if (ep.notes) {
        lines.push('', `> ${ep.notes}`)
      }
      const body = resolveBodyExample(ep.bodyExample, ctx)
      if (body) {
        lines.push('', '**请求体：**', '', '```json', body, '```', '')
      }
      lines.push('**curl：**', '', '```bash', buildCurlExample(ep.method, url, body ? { body, spaceSlug: ctx.spaceSlug } : { spaceSlug: ctx.spaceSlug }), '```', '')
    }
  }

  lines.push('## SSE 事件（/stream）', '', '```', 'data: {"type":"assistant_delta","content":"片段"}', '', 'data: {"type":"assistant_done","id":"...","content":"完整回复"}', '```', '')
  return lines.join('\n')
}

export async function fetchChatApiDocMarkdown(): Promise<string> {
  const res = await fetch(CHAT_API_DOC_PUBLIC_PATH, { cache: 'no-cache' })
  if (!res.ok) {
    throw new Error(`无法加载文档：HTTP ${res.status}`)
  }
  return res.text()
}

export function downloadTextFile(filename: string, content: string, mime = 'text/markdown;charset=utf-8') {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export async function downloadChatApiDoc(ctx: ChatApiAccessContext): Promise<void> {
  let content: string
  try {
    content = await fetchChatApiDocMarkdown()
  } catch {
    content = buildChatApiAccessMarkdown(ctx)
  }
  downloadTextFile(CHAT_API_DOC_FILENAME, content)
}

export async function downloadOpenAiExampleDoc(): Promise<void> {
  const res = await fetch(OPENAI_EXAMPLE_DOC_PUBLIC_PATH, { cache: 'no-cache' })
  if (!res.ok) {
    throw new Error(`无法加载文档：HTTP ${res.status}`)
  }
  downloadTextFile(OPENAI_EXAMPLE_DOC_FILENAME, await res.text())
}
