#!/usr/bin/env bash
# zs-rag OpenAI 兼容接口 · curl 交互脚本
#
# 用法：
#   cd demo/openai_chat
#   cp .env.example .env   # 填入 ZS_RAG_API_KEY、ZS_RAG_CHAT_ID
#   chmod +x curl_chat.sh
#   ./curl_chat.sh              # 交互模式
#   ./curl_chat.sh 你好         # 单轮
#
# 依赖：curl、jq

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

BASE_URL="${ZS_RAG_BASE_URL:-http://localhost:8000}"
BASE_URL="${BASE_URL%/}"
CHAT_ID="${ZS_RAG_CHAT_ID:-}"
API_KEY="${ZS_RAG_API_KEY:-}"
MODEL="${ZS_RAG_MODEL:-deepseek-chat}"
STREAM="${ZS_RAG_STREAM:-true}"
RAW="${ZS_RAG_RAW:-false}"
SESSION_ID="${ZS_RAG_SESSION_ID:-}"

if [[ "${1:-}" == "--raw" ]]; then
  RAW=true
  shift
fi
USERNAME="${ZS_RAG_USERNAME:-admin}"
PASSWORD="${ZS_RAG_PASSWORD:-ChangeMe123!}"
ENTERPRISE_SPACE="${ZS_RAG_ENTERPRISE_SPACE:-default}"

die() {
  echo "[error] $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令: $1（请先安装）"
}

need_cmd curl
need_cmd jq

[[ -n "$CHAT_ID" ]] || die "请在 .env 中设置 ZS_RAG_CHAT_ID"

TOKEN="$API_KEY"
if [[ -z "$TOKEN" ]]; then
  echo "[auth] 未配置 ZS_RAG_API_KEY，使用账号登录…" >&2
  TOKEN="$(
    curl -sS -X POST "${BASE_URL}/auth/login" \
      -H "Content-Type: application/json" \
      -d "$(jq -n --arg u "$USERNAME" --arg p "$PASSWORD" '{username:$u,password:$p}')" \
      | jq -r '.access_token // empty'
  )"
  [[ -n "$TOKEN" ]] || die "登录失败，请检查 ZS_RAG_USERNAME / ZS_RAG_PASSWORD"
  echo "[auth] 登录成功" >&2
else
  echo "[auth] 使用 ZS_RAG_API_KEY" >&2
fi

CURL_HEADERS=(-H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json")
if [[ -n "$ENTERPRISE_SPACE" && "$TOKEN" != zs_rag_embed_* ]]; then
  CURL_HEADERS+=(-H "X-Enterprise-Space: ${ENTERPRISE_SPACE}")
fi

API_URL="${BASE_URL}/api/v1/openai/${CHAT_ID}/chat/completions"

build_body() {
  local question="$1"
  local stream_flag="$2"
  if [[ -n "$SESSION_ID" ]]; then
    jq -n \
      --arg model "$MODEL" \
      --arg question "$question" \
      --arg session_id "$SESSION_ID" \
      --argjson stream "$stream_flag" \
      '{model: $model, question: $question, session_id: $session_id, stream: $stream}'
  else
    jq -n \
      --arg model "$MODEL" \
      --arg question "$question" \
      --argjson stream "$stream_flag" \
      '{model: $model, question: $question, stream: $stream}'
  fi
}

apply_session_from_json() {
  local json="$1"
  local sid
  sid="$(echo "$json" | jq -r '.session_id // empty')"
  if [[ -n "$sid" ]]; then
    SESSION_ID="$sid"
  fi
}

print_assistant_content() {
  local json="$1"
  echo "$json" | jq -r '.choices[0].message.content // empty'
}

chat_blocking() {
  local question="$1"
  local body resp
  body="$(build_body "$question" false)"
  resp="$(
    curl -sS -X POST "$API_URL" "${CURL_HEADERS[@]}" -d "$body"
  )"
  if echo "$resp" | jq -e '.code' >/dev/null 2>&1; then
    echo "$resp" | jq -r '"[\(.code)] \(.message)"' >&2
    return 1
  fi
  apply_session_from_json "$resp"
  if [[ "${RAW,,}" == "true" || "${RAW}" == "1" ]]; then
    echo "$resp" | jq .
  else
    print_assistant_content "$resp"
  fi
}

chat_stream() {
  local question="$1"
  local body
  body="$(build_body "$question" true)"

  while IFS= read -r line; do
    line="${line%$'\r'}"
    [[ -z "$line" ]] && continue
    [[ "$line" == data:* ]] || continue
    local payload="${line#data: }"
    payload="${payload#"${payload%%[![:space:]]*}"}"
    [[ "$payload" == "[DONE]" || -z "$payload" ]] && continue

    local sid content
    sid="$(echo "$payload" | jq -r '.session_id // empty')"
    if [[ -n "$sid" ]]; then
      SESSION_ID="$sid"
    fi
    if [[ "${RAW,,}" == "true" || "${RAW}" == "1" ]]; then
      echo "$payload" | jq -c .
    else
      content="$(echo "$payload" | jq -r '.choices[0].delta.content // empty')"
      if [[ -n "$content" ]]; then
        printf '%s' "$content"
      fi
    fi
  done < <(curl -sS -N -X POST "$API_URL" "${CURL_HEADERS[@]}" -d "$body")
  [[ "${RAW,,}" == "true" || "${RAW}" == "1" ]] || printf '\n'
}

chat_once() {
  local question="$1"
  echo "assistant> " >&2
  if [[ "${STREAM,,}" == "false" || "${STREAM}" == "0" ]]; then
    chat_blocking "$question"
  else
    chat_stream "$question"
  fi
  if [[ -n "$SESSION_ID" ]]; then
    echo "[session_id] ${SESSION_ID}" >&2
  fi
}

echo "============================================================"
echo "zs-rag · curl 对话"
echo "服务: ${BASE_URL}"
echo "对话: ${CHAT_ID}"
echo "流式: ${STREAM}  原始JSON: ${RAW}（或 ZS_RAG_RAW=1 / --raw）"
echo "输入内容聊天；/quit 退出；/session 查看 session_id"
echo "============================================================"

if [[ $# -gt 0 ]]; then
  chat_once "$*"
  exit 0
fi

while true; do
  if ! IFS= read -r -p "user> " user_text; then
    echo
    echo "再见。"
    break
  fi
  user_text="${user_text#"${user_text%%[![:space:]]*}"}"
  user_text="${user_text%"${user_text##*[![:space:]]}"}"
  [[ -z "$user_text" ]] && continue
  case "${user_text,,}" in
    /quit | /exit | quit | exit)
      echo "再见。"
      break
      ;;
    /session)
      echo "session_id: ${SESSION_ID:-（尚未建立）}"
      continue
      ;;
  esac
  chat_once "$user_text" || true
done
