"""OpenAI Chat Completions 请求/响应形态辅助（与官方 API 字段对齐）。"""

from __future__ import annotations

import time
import uuid
from typing import Any

from app.core.errors import AppError
from app.schemas.chat import OpenAICompatMessage


def new_completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex}"


def extract_message_content(content: Any) -> str:
    """支持 OpenAI 文本与多模态 content 数组（仅提取 text 部分）。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            elif "text" in item:
                parts.append(str(item["text"]))
        return "\n".join(p for p in parts if p)
    return str(content)


def normalize_openai_messages(
    messages: list[OpenAICompatMessage] | list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    if not messages:
        return []
    out: list[dict[str, str]] = []
    for m in messages:
        if isinstance(m, OpenAICompatMessage):
            role, raw_content = m.role, m.content
        elif isinstance(m, dict):
            role, raw_content = m.get("role"), m.get("content")
        else:
            continue
        if role not in ("system", "user", "assistant"):
            continue
        text = extract_message_content(raw_content)
        if not text.strip():
            continue
        out.append({"role": str(role), "content": text})
    return out


def last_user_content(messages: list[dict[str, str]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return str(m.get("content") or "")
    return ""


def validate_messages_last_role_is_user(messages: list[dict[str, str]]) -> None:
    """与常见 OpenAI 兼容网关一致：messages 末条须为 user。"""
    if not messages:
        raise AppError(
            status_code=400,
            code="LAST_MESSAGE_NOT_USER",
            message="The last content of this conversation is not from user.",
        )
    if messages[-1].get("role") != "user":
        raise AppError(
            status_code=400,
            code="LAST_MESSAGE_NOT_USER",
            message="The last content of this conversation is not from user.",
        )


def estimate_usage(*, prompt_messages: list[dict[str, str]], completion_text: str) -> dict[str, Any]:
    prompt_chars = sum(len(str(m.get("content") or "")) for m in prompt_messages)
    completion_chars = len(completion_text or "")
    prompt_tokens = max(1, prompt_chars // 4) if prompt_chars else 0
    completion_tokens = max(1, completion_chars // 4) if completion_chars else 0
    if prompt_tokens == 0 and completion_tokens == 0:
        completion_tokens = 1
    total = prompt_tokens + completion_tokens
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total,
        "completion_tokens_details": {
            "accepted_prediction_tokens": completion_tokens,
            "reasoning_tokens": 0,
            "rejected_prediction_tokens": 0,
        },
    }


def _delta_dict(
    *,
    content: str | None = None,
    role: str | None = "assistant",
) -> dict[str, Any]:
    return {
        "content": content,
        "role": role,
        "function_call": None,
        "tool_calls": None,
        "reasoning_content": None,
    }


def build_chat_completion_chunk(
    *,
    completion_id: str,
    created: int,
    model: str,
    content: str | None = None,
    role: str | None = "assistant",
    finish_reason: str | None = None,
    usage: dict[str, Any] | None = None,
    chat_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """SSE 单帧：对齐 OpenAI chat.completion.chunk。"""
    payload: dict[str, Any] = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "system_fingerprint": "",
        "choices": [
            {
                "index": 0,
                "delta": _delta_dict(content=content, role=role),
                "finish_reason": finish_reason,
                "logprobs": None,
            }
        ],
        "usage": usage,
    }
    if chat_id is not None:
        payload["chat_id"] = chat_id
    if session_id is not None:
        payload["session_id"] = session_id
    return payload


def build_chat_completion_response(
    *,
    completion_id: str,
    created: int,
    model: str,
    assistant_content: str,
    prompt_messages: list[dict[str, str]],
    chat_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """非流式：对齐 OpenAI chat.completion。"""
    usage = estimate_usage(prompt_messages=prompt_messages, completion_text=assistant_content)
    payload: dict[str, Any] = {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": assistant_content},
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": usage,
    }
    if chat_id is not None:
        payload["chat_id"] = chat_id
    if session_id is not None:
        payload["session_id"] = session_id
    return payload


def resolve_session_id_from_body(body: Any) -> str | None:
    """从 body.session_id 或 extra_body.session_id 解析会话 id。"""
    sid = getattr(body, "session_id", None)
    if sid and str(sid).strip():
        return str(sid).strip()
    extra = getattr(body, "extra_body", None)
    if isinstance(extra, dict):
        raw = extra.get("session_id")
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


def resolve_response_model_name(request_model: str | None, configured_model: str | None) -> str:
    if request_model and str(request_model).strip():
        return str(request_model).strip()
    if configured_model and str(configured_model).strip():
        return str(configured_model).strip()
    return "model"


def completion_created_ts() -> int:
    return int(time.time())
