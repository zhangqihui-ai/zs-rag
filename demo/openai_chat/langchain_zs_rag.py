"""
zs-rag OpenAI 兼容接口 · LangChain 调用示例

与同事 langchain_openai.py 结构一致：通过 langchain_openai.ChatOpenAI 访问服务。
多轮对话请使用 ZsRagChatSession：首轮可无 session_id，之后自动复用服务端返回的 session_id。

用法：
  cd demo/openai_chat
  pip install -r requirements.txt
  cp .env.example .env   # 填入 ZS_RAG_API_KEY、ZS_RAG_CHAT_ID
  python langchain_zs_rag.py              # 交互多轮
  python langchain_zs_rag.py --demo-multi  # 脚本演示两轮复用 session
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

# 同目录同事的 langchain_openai.py 会遮蔽 PyPI 包，先移出 sys.path
_demo_dir = str(Path(__file__).resolve().parent)
if sys.path and Path(sys.path[0]).resolve() == Path(_demo_dir).resolve():
    sys.path.pop(0)
elif _demo_dir in sys.path:
    sys.path.remove(_demo_dir)

import httpx
from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI
from openai import OpenAI

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _openai_base_url() -> str:
    base = _env("ZS_RAG_BASE_URL", "http://localhost:8000").rstrip("/")
    chat_id = _env("ZS_RAG_CHAT_ID")
    if not chat_id:
        raise ValueError(
            "请在 .env 中设置 ZS_RAG_CHAT_ID（Web 对话页 URL 或「嵌入网站」中复制）。"
        )
    return f"{base}/api/v1/openai/{chat_id}"


def _require_api_key() -> str:
    key = _env("ZS_RAG_API_KEY")
    if not key:
        raise ValueError("请在 .env 中设置 ZS_RAG_API_KEY（嵌入密钥或 JWT）。")
    return key


def _stream_enabled() -> bool:
    return _env("ZS_RAG_STREAM", "true").lower() not in {"0", "false", "no"}


def _to_openai_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in messages:
        role = "user"
        if isinstance(m, SystemMessage):
            role = "system"
        elif isinstance(m, AIMessage):
            role = "assistant"
        elif isinstance(m, HumanMessage):
            role = "user"
        else:
            role = getattr(m, "type", "user")
            if role == "human":
                role = "user"
            elif role == "ai":
                role = "assistant"
        content = m.content
        if isinstance(content, list):
            content = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        out.append({"role": role, "content": str(content)})
    return out


def _pick_session_id_from_openai(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, dict):
        sid = obj.get("session_id")
        return str(sid) if sid else None
    if hasattr(obj, "model_dump"):
        sid = obj.model_dump().get("session_id")
        if sid:
            return str(sid)
    sid = getattr(obj, "session_id", None)
    return str(sid) if sid else None


def create_llm(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.7,
    streaming: bool = False,
    session_id: Optional[str] = None,
    **kwargs: Any,
) -> ChatOpenAI:
    """
    创建指向 zs-rag OpenAI 兼容端点的 ChatOpenAI 实例。

    多轮对话：每轮带上同一 session_id，并在响应后更新为服务端返回的新 id：
      session = ZsRagChatSession()
      session.chat("第一句")
      llm = session.llm  # 已绑定 session.session_id

    若自行 llm.invoke()，需每轮手动 create_llm(session_id=...) 或 session.bind_llm(llm)。
    """
    key = api_key or _require_api_key()

    llm_kwargs: dict[str, Any] = {
        "model": model or _env("ZS_RAG_MODEL", "deepseek-chat") or "model",
        "api_key": key,
        "base_url": base_url or _openai_base_url(),
        "temperature": temperature,
        "streaming": streaming,
        **kwargs,
    }

    sid = session_id if session_id is not None else _env("ZS_RAG_SESSION_ID") or None
    if sid:
        llm_kwargs["extra_body"] = {"session_id": sid}

    return ChatOpenAI(**llm_kwargs)


class ZsRagChatSession:
    """
    维护多轮 session_id 的会话封装。

    - 首轮请求可不传 session_id，服务端会创建并在响应根级返回 session_id。
    - 后续轮次自动在 extra_body.session_id 中复用同一 session_id。
    - `chat()` 默认在客户端累积 messages 全文发送（兼容 OpenAI SDK，且服务端会持久化每轮）。
    - `chat(..., server_history=True)` 使用 zs-rag 扩展字段 `question`，由服务端按 session 合并历史
      （无需客户端维护 messages，适合只发当前一句的场景）。
    """

    def __init__(
        self,
        *,
        session_id: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> None:
        self.session_id: Optional[str] = (
            session_id if session_id is not None else _env("ZS_RAG_SESSION_ID") or None
        )
        self.model = model or _env("ZS_RAG_MODEL", "deepseek-chat") or "model"
        self.temperature = temperature
        self._api_key = api_key or _require_api_key()
        self._base_url = base_url or _openai_base_url()
        self._root_url = _env("ZS_RAG_BASE_URL", "http://localhost:8000").rstrip("/")
        self._messages: list[dict[str, str]] = []
        self._client = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=120.0,
        )

    def clear_history(self) -> None:
        """清空客户端侧累积的 messages（不删除服务端 session）。"""
        self._messages.clear()

    @property
    def llm(self) -> ChatOpenAI:
        """当前 session_id 绑定的 LangChain ChatOpenAI（只读快照，调用 chat/invoke 后会话 id 可能已更新）。"""
        return create_llm(
            model=self.model,
            api_key=self._api_key,
            base_url=self._base_url,
            temperature=self.temperature,
            session_id=self.session_id,
            streaming=False,
        )

    def _completion_kwargs(self, messages: list[dict[str, str]], *, stream: bool) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if self.session_id:
            kwargs["extra_body"] = {"session_id": self.session_id}
        return kwargs

    def _apply_session_id(self, obj: Any) -> None:
        sid = _pick_session_id_from_openai(obj)
        if sid:
            self.session_id = sid

    def chat(
        self,
        user_text: str,
        *,
        stream: Optional[bool] = None,
        system_prompt: Optional[str] = None,
        server_history: bool = False,
    ) -> str:
        """
        发送单条用户消息，自动维护 session_id。

        server_history=False（默认）：在客户端累积 messages，每轮带上完整上下文。
        server_history=True：仅传 question + session_id，由 zs-rag 服务端合并会话历史。
        """
        if server_history:
            return self._chat_with_server_history(user_text, stream=stream)

        if system_prompt and not self._messages:
            self._messages.append({"role": "system", "content": system_prompt})
        self._messages.append({"role": "user", "content": user_text})
        text = self._invoke_openai_messages(self._messages, stream=stream)
        self._messages.append({"role": "assistant", "content": text})
        return text

    def _chat_with_server_history(
        self,
        question: str,
        *,
        stream: Optional[bool] = None,
    ) -> str:
        use_stream = _stream_enabled() if stream is None else stream
        body: dict[str, Any] = {
            "model": self.model,
            "question": question,
            "stream": use_stream,
        }
        if self.session_id:
            body["session_id"] = self.session_id

        url = f"{self._root_url}/api/v1/openai/{_env('ZS_RAG_CHAT_ID')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        if not use_stream:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(url, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
            self._apply_session_id(data)
            choices = data.get("choices") or []
            text = ""
            if choices:
                text = str((choices[0].get("message") or {}).get("content") or "")
            return text

        parts: list[str] = []
        with httpx.Client(timeout=120.0) as client:
            with client.stream("POST", url, headers=headers, json=body) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    chunk = json.loads(payload)
                    self._apply_session_id(chunk)
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        piece = delta.get("content")
                        if piece:
                            parts.append(piece)
                            print(piece, end="", flush=True)
        if parts:
            print()
        return "".join(parts)

    def invoke(
        self,
        messages: list[BaseMessage],
        *,
        stream: Optional[bool] = None,
    ) -> str:
        """发送 LangChain 消息列表，返回助手文本并更新 session_id（不写入 chat 内部历史）。"""
        return self._invoke_openai_messages(_to_openai_messages(messages), stream=stream)

    def _invoke_openai_messages(
        self,
        messages: list[dict[str, str]],
        *,
        stream: Optional[bool] = None,
    ) -> str:
        use_stream = _stream_enabled() if stream is None else stream
        if use_stream:
            return self._invoke_stream(messages)
        return self._invoke_blocking(messages)

    def _invoke_blocking(self, messages: list[dict[str, str]]) -> str:
        resp = self._client.chat.completions.create(**self._completion_kwargs(messages, stream=False))
        self._apply_session_id(resp)
        text = ""
        if resp.choices:
            text = getattr(resp.choices[0].message, "content", None) or ""
        return text

    def _invoke_stream(self, messages: list[dict[str, str]]) -> str:
        stream_resp = self._client.chat.completions.create(
            **self._completion_kwargs(messages, stream=True),
        )
        parts: list[str] = []
        for chunk in stream_resp:
            self._apply_session_id(chunk)
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = getattr(delta, "content", None)
            if piece:
                parts.append(piece)
                print(piece, end="", flush=True)
        if parts:
            print()
        text = "".join(parts)
        if not text.strip():
            print("[warn] 流式为空，改非流式重试", file=sys.stderr)
            return self._invoke_blocking(messages)
        return text


def demo_multi_turn() -> None:
    """演示两轮对话复用同一 session_id。"""
    session = ZsRagChatSession()
    print("=" * 50)
    print("多轮 session 演示（同一 ZsRagChatSession 实例）")
    print(f"初始 session_id: {session.session_id or '(新建)'}")
    print("=" * 50)

    print("\n[user] 请记住数字 42，只回答「好的」。")
    r1 = session.chat("请记住数字 42，只回答「好的」。", stream=False, server_history=True)
    print(f"[assistant] {r1}")
    print(f"[session_id] {session.session_id}")

    print("\n[user] 我刚才让你记住的数字是多少？")
    print("[assistant] ", end="", flush=True)
    r2 = session.chat("我刚才让你记住的数字是多少？", server_history=True)
    if not _stream_enabled():
        print(r2)
    print(f"\n[session_id] {session.session_id}（两轮应相同）")
    print("=" * 50)


def interactive_chat() -> None:
    session = ZsRagChatSession()
    use_stream = _stream_enabled()

    print("=" * 50)
    print("zs-rag · LangChain 多轮对话")
    print(f"base_url: {session._base_url}")
    print(f"model:    {session.model}")
    if session.session_id:
        print(f"接续会话: {session.session_id}")
    print("输入内容聊天；/quit 退出；/session 打印当前 session_id")
    print("=" * 50)

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
        if user_text.lower() == "/session":
            print(f"session_id: {session.session_id or '(尚未建立)'}")
            continue

        try:
            print("assistant> ", end="", flush=True)
            text = session.chat(user_text, stream=use_stream)
            if not use_stream:
                print(text)
            if session.session_id:
                print(f"[session_id] {session.session_id}")
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr)


def test_stream_chat(messages: Optional[list[BaseMessage]] = None) -> str:
    """单轮流式测试（不演示 session 复用，多轮请用 ZsRagChatSession）。"""
    if messages is None:
        messages = [
            SystemMessage(content="你是一个有用的 AI 助手。"),
            HumanMessage(content="请用一两句话介绍一下你自己。"),
        ]

    session = ZsRagChatSession()
    use_stream = _stream_enabled()

    print("=" * 50)
    print("zs-rag · 单轮测试（多轮请用 ZsRagChatSession.chat）")
    print(f"base_url: {session._base_url}")
    print(f"model:    {session.model}")
    print("=" * 50)

    if use_stream:
        print("assistant> ", end="", flush=True)
    text = session.invoke(messages, stream=use_stream)
    if not use_stream:
        print(text)

    print("=" * 50)
    if session.session_id:
        print(f"[session_id] {session.session_id}")
    print(f"完整回复长度: {len(text)} 字符")
    print("=" * 50)
    return text


if __name__ == "__main__":
    if "--demo-multi" in sys.argv:
        demo_multi_turn()
    elif "--once" in sys.argv:
        test_stream_chat()
    else:
        interactive_chat()
