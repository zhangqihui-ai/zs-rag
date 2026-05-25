# OpenAI 兼容接口 Demo

调用 zs-rag 的 OpenAI 兼容端点 `POST /api/v1/openai/{chat_id}/chat/completions`，在终端多轮对话。本目录提供多种示例：

| 文件 | 说明 | 依赖 |
|------|------|------|
| `curl_chat.sh` | **curl + jq** 交互脚本 | curl、jq |
| `chat_demo.py` | OpenAI 官方 Python SDK | Python 3.10+ |
| `langchain_zs_rag.py` | LangChain `ChatOpenAI` + 多轮 `session_id` | Python + langchain-openai |
| `langchain_openai.py` | 同事侧参考示例（第三方 OpenAI 网关） | — |

## 前置条件

1. 已启动 zs-rag backend（默认 `http://localhost:8000`）
2. 在平台 **对话设置** 里为测试对话配置好 **大语言模型**（未配置时只会 Echo）
3. 在 **嵌入网站** 或对话设置中复制 **聊天 ID**、**嵌入 API Key**

## 配置 `.env`

```bash
cd demo/openai_chat
cp .env.example .env
```

编辑 `.env`，至少填写：

- `ZS_RAG_API_KEY`（推荐，`zs_rag_embed_...`）
- `ZS_RAG_CHAT_ID`（必填，不会自动创建对话）

未配置 API Key 时，脚本会用 `ZS_RAG_USERNAME` / `ZS_RAG_PASSWORD` 登录获取 JWT。

---

## curl 脚本 `curl_chat.sh`

无需 Python，适合快速验证接口或查看原始 JSON。

### 安装依赖

- [curl](https://curl.se/)
- [jq](https://jqlang.github.io/jq/)

### 基本用法

```bash
chmod +x curl_chat.sh

./curl_chat.sh                      # 交互模式：user> 输入，打印 assistant 回复
./curl_chat.sh 你好，一句话介绍自己    # 单轮，问完即退出
```

交互命令：

| 输入 | 作用 |
|------|------|
| 任意文本 | 发送一轮对话 |
| `/session` | 打印当前 `session_id` |
| `/quit` 或 `exit` | 退出 |

多轮：脚本使用 zs-rag 扩展字段 **`question` + `session_id`**，首轮由服务端创建会话，后续自动复用响应里的 `session_id`（终端会打印 `[session_id] ...`）。

### 环境变量（curl 脚本）

除下方「通用环境变量」外，curl 脚本还支持：

| 变量 | 说明 | 默认 |
|------|------|------|
| `ZS_RAG_STREAM` | `true` 流式 SSE；`false` 一次返回整段 JSON | `true` |
| `ZS_RAG_RAW` | `1`/`true` 时打印完整 JSON，不抽 assistant 文本 | `false` |

示例：

```bash
# 非流式 + 格式化打印整段响应 JSON
ZS_RAG_STREAM=false ZS_RAG_RAW=1 ./curl_chat.sh "说一个字：好"

# 流式：每条 SSE data 行打印一行 JSON（compact）
ZS_RAG_RAW=1 ./curl_chat.sh --raw "你好"
```

`--raw` 与 `ZS_RAG_RAW=1` 等价。

### 手写 curl 查看 JSON（不经过脚本）

```bash
source .env

# 非流式
curl -sS -X POST "${ZS_RAG_BASE_URL}/api/v1/openai/${ZS_RAG_CHAT_ID}/chat/completions" \
  -H "Authorization: Bearer ${ZS_RAG_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","question":"你好","stream":false}' | jq .

# 流式 SSE
curl -sS -N -X POST "${ZS_RAG_BASE_URL}/api/v1/openai/${ZS_RAG_CHAT_ID}/chat/completions" \
  -H "Authorization: Bearer ${ZS_RAG_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","question":"你好","stream":true}'
```

响应结构与 [`../../docs/openai接口示例.md`](../../docs/openai接口示例.md) 一致；根级 **`chat_id`、`session_id` 为 zs-rag 扩展字段**。

---

## Python SDK `chat_demo.py`

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python chat_demo.py
python chat_demo.py 你好，请用一句话介绍你自己   # 单轮
```

流式为空时会自动降级为非流式重试。退出：输入 `/quit` 或 `Ctrl+C`。

---

## LangChain `langchain_zs_rag.py`

```bash
pip install -r requirements.txt

python langchain_zs_rag.py              # 交互多轮
python langchain_zs_rag.py --demo-multi # 演示 session_id 复用
python langchain_zs_rag.py --once       # 单轮测试
```

多轮推荐 **`ZsRagChatSession`**：

```python
from langchain_zs_rag import ZsRagChatSession

session = ZsRagChatSession()          # 或 session_id="已有uuid"
session.chat("你好")
session.chat("继续刚才的话题")          # 默认客户端累积 messages
session.chat("继续", server_history=True)  # 仅发 question，历史由服务端合并

print(session.session_id)
```

> 同目录 `langchain_openai.py` 为同事参考文件，文件名会遮蔽 PyPI 包，请勿与 `langchain_zs_rag.py` 同目录直接 `import langchain_openai`。

---

## 通用环境变量

| 变量 | 说明 |
|------|------|
| `ZS_RAG_BASE_URL` | API 根地址，默认 `http://localhost:8000`（不要末尾 `/`） |
| `ZS_RAG_API_KEY` | 嵌入 API Key（推荐）；嵌入 Key **无需** `X-Enterprise-Space` |
| `ZS_RAG_USERNAME` / `ZS_RAG_PASSWORD` | 未配置 API Key 时用 JWT 登录 |
| `ZS_RAG_ENTERPRISE_SPACE` | JWT 时企业空间 slug，默认 `default` |
| `ZS_RAG_CHAT_ID` | **必填**，平台里已配置模型的对话 ID |
| `ZS_RAG_SESSION_ID` | 可选，接续已有会话 |
| `ZS_RAG_STREAM` | `true`/`false`（Python / curl 脚本） |
| `ZS_RAG_MODEL` | 请求体 `model` 回显名，默认 `deepseek-chat` |
| `ZS_RAG_RAW` | 仅 curl 脚本：是否打印原始 JSON |

## 工作原理

```text
Authorization: Bearer <嵌入 Key 或 JWT>
POST {BASE_URL}/api/v1/openai/{chat_id}/chat/completions

扩展字段（非 OpenAI 官方）：
  session_id  — 多轮会话 ID（请求根级或 extra_body.session_id）
  question    — 仅发当前一句时，服务端按 session 合并历史（curl 脚本默认用法）
  chat_id     — 响应根级回显
```

首次无 `session_id` 时服务端会创建会话；后续请求带上同一 `session_id` 即可持续对话。

## 相关文档

- [`../../docs/openai接口示例.md`](../../docs/openai接口示例.md) — 请求/响应 JSON 样例
- [`../../docs/会话多轮历史实现说明.md`](../../docs/会话多轮历史实现说明.md) — `session_id` / `messages` / `question` 多轮实现
- [`../../docs/聊天对话对外API接入文档.md`](../../docs/聊天对话对外API接入文档.md) — 完整 REST 列表

如果完全按照OpenAI 习惯：每轮 messages 带全历史即可，可以不传 session_id，模型多轮没问题。
对于zs-rag平台来讲，每次相当于都开启了一个sessionid，
{
  "model": "deepseek-chat",
  "stream": true,
  "messages": [
    { "role": "user", "content": "记住数字 42" },
    { "role": "assistant", "content": "好的。" },
    { "role": "user", "content": "刚才的数字是多少？" }
    
  ]
}
不传 session_id 时，模型仍能根据 messages 回答「42」；只是平台里对应多个 session 记录。

