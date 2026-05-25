#!/usr/bin/env python3
"""
使用 OpenAI 官方 Python SDK 调用 zs-rag 的 OpenAI 兼容接口，终端交互聊天。

用法：
  cd demo/openai_chat
  pip install -r requirements.txt
  cp .env.example .env
  # 必填 ZS_RAG_CHAT_ID（在平台对话列表 URL 或设置里复制）
  python chat_demo.py
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _auth_headers(token: str) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    space = _env("ZS_RAG_ENTERPRISE_SPACE", "default")
    if space and not token.startswith("zs_rag_embed_"):
        headers["X-Enterprise-Space"] = space
    return headers


def login(base_url: str) -> str:
    username = _env("ZS_RAG_USERNAME", "admin")
    password = _env("ZS_RAG_PASSWORD", "ChangeMe123!")
    if not username or not password:
        raise SystemExit("请设置 ZS_RAG_API_KEY，或设置 ZS_RAG_USERNAME / ZS_RAG_PASSWORD")
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            f"{base_url}/auth/login",
            json={"username": username, "password": password},
        )
        r.raise_for_status()
        data = r.json()
        token = data.get("access_token")
        if not token:
            raise SystemExit(f"登录失败：未返回 access_token，响应={data}")
        return str(token)


def resolve_api_key(base_url: str) -> str:
    key = _env("ZS_RAG_API_KEY")
    if key:
        print("[auth] 使用 ZS_RAG_API_KEY")
        return key
    print("[auth] 未配置 ZS_RAG_API_KEY，使用账号登录…")
    token = login(base_url)
    print("[auth] 登录成功")
    return token


def require_chat_id() -> str:
    chat_id = _env("ZS_RAG_CHAT_ID")
    if not chat_id:
        raise SystemExit(
            "请在 .env 中设置 ZS_RAG_CHAT_ID（必填，不会自动创建对话）。\n"
            "可在 Web 对话页 URL 或「对话设置」中复制对话 ID。"
        )
    return chat_id


def load_chat_meta(base_url: str, token: str, chat_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(
            f"{base_url}/api/v1/chats/{chat_id}",
            headers=_auth_headers(token),
        )
    if r.status_code == 404:
        raise SystemExit(f"对话不存在或无权访问：{chat_id}")
    if r.status_code >= 400:
        raise SystemExit(f"读取对话失败 HTTP {r.status_code}: {r.text}")
    return r.json()


def _pick_session_id(obj: Any) -> str | None:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        sid = obj.model_dump().get("session_id")
        if sid:
            return str(sid)
    direct = getattr(obj, "session_id", None)
    if direct:
        return str(direct)
    return None


def _print_stream(stream: Any) -> tuple[str, str | None]:
    parts: list[str] = []
    session_id: str | None = None
    print("assistant> ", end="", flush=True)
    for chunk in stream:
        if hasattr(chunk, "model_dump"):
            raw = chunk.model_dump()
            if raw.get("error"):
                err = raw["error"]
                msg = err.get("message") if isinstance(err, dict) else str(err)
                print(f"\n[API error] {msg}", file=sys.stderr)
                break
        sid = _pick_session_id(chunk)
        if sid:
            session_id = sid
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        piece = getattr(delta, "content", None)
        if piece:
            parts.append(piece)
            print(piece, end="", flush=True)
    print("\n")
    return "".join(parts), session_id


def chat_once(
    client: OpenAI,
    *,
    model: str,
    user_text: str,
    session_id: str | None,
    stream: bool,
) -> str | None:
    extra: dict[str, Any] = {}
    if session_id:
        extra["session_id"] = session_id

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": user_text}],
        "stream": stream,
    }
    if extra:
        kwargs["extra_body"] = extra

    if stream:
        stream_resp = client.chat.completions.create(**kwargs)
        text, new_sid = _print_stream(stream_resp)
        if not text.strip():
            print("[warn] 流式回复为空，尝试非流式…", file=sys.stderr)
            kwargs["stream"] = False
            resp = client.chat.completions.create(**kwargs)
            sid = _pick_session_id(resp) or session_id
            content = ""
            if resp.choices:
                content = getattr(resp.choices[0].message, "content", None) or ""
            print(f"assistant> {content}\n")
            return sid or new_sid
        return new_sid or session_id

    resp = client.chat.completions.create(**kwargs)
    sid = _pick_session_id(resp) or session_id
    text = ""
    if resp.choices:
        msg = resp.choices[0].message
        text = getattr(msg, "content", None) or ""
    print(f"assistant> {text}\n")
    return sid


def main() -> None:
    base_url = _env("ZS_RAG_BASE_URL", "http://localhost:8000").rstrip("/")
    model = _env("ZS_RAG_MODEL", "deepseek-chat") or "model"
    use_stream = _env("ZS_RAG_STREAM", "true").lower() not in {"0", "false", "no"}
    one_shot = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else ""

    print("=" * 60)
    print("zs-rag · OpenAI SDK 对话 Demo")
    print(f"服务: {base_url}")
    print("输入内容聊天；/quit 退出")
    print("=" * 60)

    token = resolve_api_key(base_url)
    chat_id = require_chat_id()
    meta = load_chat_meta(base_url, token, chat_id)
    print(f"[chat] {chat_id}  标题: {meta.get('title', '')}")
    provider = meta.get("model_provider") or "(未配置)"
    model_name = meta.get("model_name") or "(未配置)"
    print(f"[chat] 模型: {provider} / {model_name}")
    if not meta.get("model_name"):
        print(
            "[warn] 该对话未配置大语言模型，回复可能为空。请先在 Web 端打开该对话并选择模型。",
            file=sys.stderr,
        )

    openai_base = f"{base_url}/api/v1/openai/{chat_id}"
    client = OpenAI(api_key=token, base_url=openai_base, timeout=120.0)

    session_id: str | None = _env("ZS_RAG_SESSION_ID") or None
    if session_id:
        print(f"[session] 使用环境变量中的会话: {session_id}")

    def run_turn(text: str) -> None:
        nonlocal session_id
        session_id = chat_once(
            client,
            model=model,
            user_text=text,
            session_id=session_id,
            stream=use_stream,
        )
        if session_id:
            print(f"[session] {session_id}")

    if one_shot:
        try:
            run_turn(one_shot)
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr)
            sys.exit(1)
        return

    while True:
        try:
            user_text = input("user> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if not user_text:
            continue
        if user_text.lower() in {"/quit", "/exit", "quit", "exit"}:
            print("再见。")
            break
        try:
            run_turn(user_text)
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
