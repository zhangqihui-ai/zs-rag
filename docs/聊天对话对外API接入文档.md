# 聊天对话对外 API 接入文档

本文档描述 **zs-rag** 对外开放的聊天 REST 接口，供第三方系统通过 **Bearer Token** 或 **嵌入 API Key** 集成。实现源码：`backend/app/api/routes/chats.py`、`backend/app/api/routes/chat_completions.py`。

> 更详细的字段说明与排错见同目录 [`聊天助手会话管理接口文档.md`](./聊天助手会话管理接口文档.md)。

---

## 1. 基础约定

| 项目 | 说明 |
|------|------|
| **Base URL** | 例：`https://your-domain.com` 或 `http://localhost:8000` |
| **对话/会话前缀** | `{BASE_URL}/api/v1/chats` |
| **补全前缀** | `{BASE_URL}/api/v1/chat` |
| **Content-Type** | `application/json`（流式接口除外） |
| **主键** | `chat_id`、`session_id` 均为 UUID 字符串 |

### 1.1 认证

| 方式 | 请求头 | `X-Enterprise-Space` |
|------|--------|----------------------|
| **嵌入 API Key**（推荐对外） | `Authorization: Bearer zs_rag_embed_...` | **可不传**（服务端按 Key 自动识别企业空间） |
| **登录 JWT** | `Authorization: Bearer <access_token>` | 省略时默认为 `default`；非 default 空间须显式传 |

```http
Authorization: Bearer <token>
Content-Type: application/json
# X-Enterprise-Space: your-space   # 仅 JWT 且非 default 空间时需要
```

嵌入 Key 在管理台「对话设置 → 嵌入网站」签发，明文仅展示一次，请妥善保存。

### 1.2 典型调用流程

```text
POST /api/v1/chats                                    → 获得 chat_id
POST /api/v1/chats/{chat_id}/sessions                 → 获得 session_id（可选）
POST /api/v1/openai/{chat_id}/chat/completions        → 发消息（OpenAI 标准路径，推荐）
```

兼容旧路径：`POST /api/v1/chat/completions`（`chat_id` 放在 JSON body）。

---

## 2. 接口一览（共 16 个）

### 2.1 对话（Chat）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/chats` | 列出对话（`skip`、`limit`） |
| POST | `/api/v1/chats` | 创建对话（可带 `configuration`） |
| GET | `/api/v1/chats/{chat_id}` | 获取对话详情 |
| PUT | `/api/v1/chats/{chat_id}` | 修改标题 `{"title":"..."}` |
| DELETE | `/api/v1/chats/{chat_id}` | 删除对话（204） |

**创建对话请求体示例：**

```json
{
  "title": "新建对话",
  "configuration": {
    "model_id": 1,
    "knowledge_base_ids": [],
    "system_prompt": "你是助手…",
    "temperature": 0.7,
    "max_tokens": 2000,
    "top_p": 1.0,
    "show_citations": true,
    "retrieval_top_k": 8
  }
}
```

### 2.2 会话 — 隶属于某对话

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/chats/{chat_id}/sessions` | 列出会话 |
| POST | `/api/v1/chats/{chat_id}/sessions` | 新建会话 `{"title":"新会话"}` |

### 2.3 会话 — 按 session_id 管理

> 路径前缀固定为 `/api/v1/chats/sessions/`，避免与 `{chat_id}` 路由冲突。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/chats/sessions/{session_id}` | 获取会话 |
| PUT | `/api/v1/chats/sessions/{session_id}` | 修改标题 |
| DELETE | `/api/v1/chats/sessions/{session_id}` | 删除会话（204） |

### 2.4 消息与配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/chats/sessions/{session_id}/messages` | 历史消息（`skip`、`limit`） |
| GET | `/api/v1/chats/sessions/{session_id}/config` | 读取对话级模型/知识库配置 |
| PUT | `/api/v1/chats/sessions/{session_id}/config` | 更新对话级配置（该对话下所有会话共用） |

### 2.5 聊天推理（发消息）

| 方法 | 路径 | 说明 |
|------|------|------|
| **POST** | `/api/v1/openai/{chat_id}/chat/completions` | **推荐**：与 OpenAI 路径一致 |
| POST | `/api/v1/chat/completions` | 兼容：`chat_id` 在 body |
| POST | `/api/v1/chats/sessions/{session_id}/stream` | 站内 SSE（`assistant_delta` / `assistant_done`） |

**OpenAI 标准请求体（流式）：**

```json
{
  "model": "your-model-name",
  "messages": [{"role": "user", "content": "你好，请介绍一下要点"}],
  "stream": true,
  "session_id": "<session_id>"
}
```

| 条件 | 行为 |
|------|------|
| URL 含 `chat_id`，无 `session_id` | 自动新建会话并回复 |
| 带 `session_id`（或 `extra_body.session_id`） | 在已有会话内多轮 |
| `messages` 末条 | 必须为 `user`，否则 400 |
| `stream: true` | SSE：`chat.completion.chunk`（含 `delta`、`usage` 末帧）、`data: [DONE]` |
| `stream: false` | `chat.completion` + `usage` |

响应根级扩展字段：`chat_id`、`session_id`（便于客户端关联）。详见 [`openai接口示例.md`](./openai接口示例.md)。

**站内 SSE 请求体：**

```json
{ "content": "用户本轮输入的纯文本" }
```

响应 `Content-Type: text/event-stream`，每行 `data: <json>`。

---

## 3. curl 示例

```bash
BASE_URL="http://localhost:8000"
TOKEN="zs_rag_embed_xxxx"   # 或登录 access_token

# 创建对话
curl -sS -X POST "${BASE_URL}/api/v1/chats" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"title":"对外接入测试"}'

# 创建会话（将 CHAT 换为上一步返回的 id）
CHAT="<chat_id>"
curl -sS -X POST "${BASE_URL}/api/v1/chats/${CHAT}/sessions" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"title":"会话 1"}'

# 流式补全（OpenAI 路径）
SESS="<session_id>"
curl -N -sS -X POST "${BASE_URL}/api/v1/openai/${CHAT}/chat/completions" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"your-model\",\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}],\"stream\":true,\"session_id\":\"${SESS}\"}"
```

---

## 4. 常见错误

| HTTP | 说明 |
|------|------|
| 401 | Token / Key 无效或过期 |
| 403 | 无该企业空间权限（JWT 与空间头不匹配时） |
| 404 | 对话/会话不存在 |
| 422 | 请求体校验失败 |

业务错误体：`{ "code", "message", "request_id" }`。

---

## 5. 嵌入密钥管理（可选）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/chats/embed-api-keys` | 签发/确保嵌入 Key（需登录） |
| GET | `/api/v1/chats/embed-api-keys` | 列出活跃 Key 元信息 |
| DELETE | `/api/v1/chats/embed-api-keys/{key_id}` | 吊销 |

---

*文档与仓库代码同步维护；如有不一致以源码为准。*

---

**维护说明：** 修改本文档后请同步到前端静态目录，供「API 接入 → 下载文档」使用：

```bash
cp docs/聊天对话对外API接入文档.md web/public/docs/聊天对话对外API接入文档.md
```
