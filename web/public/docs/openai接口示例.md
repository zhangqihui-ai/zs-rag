# OpenAI 兼容接口示例（对照 zs-rag 实现）

本文档整理常见 OpenAI Chat Completions 请求/响应样例；**zs-rag 已对齐相同字段结构**。

## 本系统对应端点

| 场景 | 方法 | URL |
|------|------|-----|
| **推荐（OpenAI 路径）** | POST | `{BASE_URL}/api/v1/openai/{chat_id}/chat/completions` |
| 兼容（chat_id 在 body） | POST | `{BASE_URL}/api/v1/chat/completions` |

认证：`Authorization: Bearer <嵌入 API Key 或 access_token>`。嵌入 Key **无需** `X-Enterprise-Space`。

多轮会话：请求体 `session_id` 或 `extra_body.session_id`。

---

## 请求示例

```bash
curl --request POST \
     --url "http://localhost:8000/api/v1/openai/{chat_id}/chat/completions" \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "Say this is a test!"}],
        "stream": true,
        "extra_body": {
          "session_id": "<optional_session_id>"
        }
      }'
```

> 说明：`extra_body` 为 OpenAI Python SDK 写法；直接 curl 时可将 `session_id` 写在 JSON 根级。

---

## 流式响应（Stream）

每条 SSE 行为 `data: <json>`，结束时 `data: [DONE]`。

```json
{
    "id": "chatcmpl-3b0397f277f511f0b47f729e3aa55728",
    "object": "chat.completion.chunk",
    "created": 1755084508,
    "model": "deepseek-chat",
    "system_fingerprint": "",
    "choices": [
        {
            "index": 0,
            "delta": {
                "content": "Hello! It seems like you're just greeting me.",
                "role": "assistant",
                "function_call": null,
                "tool_calls": null,
                "reasoning_content": null
            },
            "finish_reason": null,
            "logprobs": null
        }
    ],
    "usage": null,
    "chat_id": "<chat_id>",
    "session_id": "<session_id>"
}
```

末帧（`finish_reason: stop`，带 `usage`）：

```json
{
    "id": "chatcmpl-...",
    "object": "chat.completion.chunk",
    "choices": [{
        "delta": {
            "content": null,
            "role": "assistant",
            "function_call": null,
            "tool_calls": null,
            "reasoning_content": null
        },
        "finish_reason": "stop",
        "index": 0,
        "logprobs": null
    }],
    "usage": {
        "prompt_tokens": 5,
        "completion_tokens": 188,
        "total_tokens": 193
    }
}
```

---

## 非流式响应

```json
{
    "id": "chatcmpl-3b0397f277f511f0b47f729e3aa55728",
    "object": "chat.completion",
    "created": 1755084403,
    "model": "deepseek-chat",
    "choices": [
        {
            "finish_reason": "stop",
            "index": 0,
            "logprobs": null,
            "message": {
                "content": "Hello! I'm your smart assistant.",
                "role": "assistant"
            }
        }
    ],
    "usage": {
        "completion_tokens": 55,
        "completion_tokens_details": {
            "accepted_prediction_tokens": 55,
            "reasoning_tokens": 0,
            "rejected_prediction_tokens": 0
        },
        "prompt_tokens": 5,
        "total_tokens": 60
    },
    "chat_id": "<chat_id>",
    "session_id": "<session_id>"
}
```

---

## 失败示例

当 `messages` 最后一条不是 `user` 时：

```json
{
  "code": "LAST_MESSAGE_NOT_USER",
  "message": "The last content of this conversation is not from user.",
  "request_id": "..."
}
```

其它业务错误同样返回 `code` + `message`（HTTP 4xx）。

---

完整 REST 列表见 [`聊天对话对外API接入文档.md`](./聊天对话对外API接入文档.md)。
