from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.core.provider_adapter import get_provider
from app.models.chat import ChatConversation, ChatMessage, ChatSession
from app.models.knowledge_base import KnowledgeBase
from app.models.model_management import AIModel, AIModelDefault, AIModelProvider
from app.schemas.chat import (
    ChatConfigurationResponse,
    ChatConfigurationUpdate,
    ChatConversationCreate,
    ChatConversationUpdate,
    ChatSessionCreate,
    ChatSessionUpdate,
    OpenAICompatMessage,
)


DEFAULT_CHAT_SYSTEM_PROMPT = (
    "你是一个智能助手，请总结知识库的内容来回答问题，请列举知识库中的数据详细回答。"
    "当所有知识库内容都与问题无关时，你的回答必须包括「知识库中未找到您要的答案！」这句话。"
    "回答需要考虑聊天历史。\n以下是知识库：\n{knowledge}\n以上是知识库。"
)

_CITATION_HINT_SUFFIX = (
    "\n\n（请在回答中引用上述片段时，在对应句末使用角标 [1]、[2] 等与编号对应；"
    "综合多条时可写 [1][2]。未用到的编号勿标注。）"
)


def _clamp_retrieval_top_k(raw: Any) -> int:
    if raw is None:
        return 8
    try:
        return max(1, min(50, int(raw)))
    except (TypeError, ValueError):
        return 8


def _merge_top_k_for_conversation(conv: ChatConversation | None) -> int:
    if conv is None:
        return 8
    return _clamp_retrieval_top_k(getattr(conv, "retrieval_top_k", None))


def _retrieve_knowledge_block_and_citations(
    db: Session,
    *,
    enterprise_space_id: int,
    knowledge_base_ids: list[int],
    query: str,
    merge_top_k: int = 8,
) -> tuple[str, list[dict[str, Any]]]:
    q = (query or "").strip()
    ids = [int(x) for x in knowledge_base_ids if x is not None]
    unique_ids = list(dict.fromkeys(ids))
    if not q or not unique_ids:
        return "", []

    existing_ids = set(
        db.execute(
            select(KnowledgeBase.id).where(
                KnowledgeBase.enterprise_space_id == enterprise_space_id,
                KnowledgeBase.id.in_(unique_ids),
                KnowledgeBase.status != "deleted",
            )
        )
        .scalars()
        .all()
    )
    ordered_existing = [kid for kid in unique_ids if kid in existing_ids]
    if not ordered_existing:
        return "", []

    from app.schemas.retrieval import KnowledgeSearchRequest
    from app.services.retrieval_service import search_knowledge_bases_multi

    cap = _clamp_retrieval_top_k(merge_top_k)
    try:
        data = search_knowledge_bases_multi(
            db,
            space_id=enterprise_space_id,
            knowledge_base_ids=ordered_existing,
            payload=KnowledgeSearchRequest(query=q[:2000], top_k=cap),
        )
    except AppError:
        return "", []

    picked = data.get("results") or []
    if not picked:
        return "", []

    parts: list[str] = []
    citations: list[dict[str, Any]] = []
    ref = 0
    for item in picked:
        raw_kb = item.get("knowledge_base_id")
        if raw_kb is None:
            continue
        ref += 1
        src_kb_id = int(raw_kb)
        cite_raw = item.get("citation")
        cite: dict[str, Any] = cite_raw if isinstance(cite_raw, dict) else {}
        doc = str(item.get("document_name") or cite.get("document_name") or "文献")
        page = cite.get("page_no")
        page_bit = f" 第{int(page)}页" if isinstance(page, (int, float)) else ""
        header = f"[{ref}] 《{doc}》{page_bit}"
        body = str(item.get("content") or "").strip()
        parts.append(f"{header}\n{body}")
        pn: int | None = int(page) if isinstance(page, (int, float)) else None
        citations.append(
            {
                "ref": ref,
                "document_name": doc,
                "page_no": pn,
                "chunk_id": item.get("chunk_id"),
                "document_id": item.get("document_id"),
                "chunk_index": item.get("chunk_index"),
                "knowledge_base_id": int(src_kb_id),
                "score": round(float(item.get("score") or 0), 4),
            }
        )

    block = "\n\n---\n\n".join(parts)
    return block, citations


def _effective_system_prompt(conv: ChatConversation | None, *, knowledge_block: str = "") -> str:
    raw = ""
    if conv is not None and conv.system_prompt is not None:
        raw = str(conv.system_prompt).strip()
    if not raw:
        raw = DEFAULT_CHAT_SYSTEM_PROMPT.strip()
    kb = knowledge_block.strip() if knowledge_block.strip() else "（本轮尚未注入检索片段）"
    return raw.replace("{knowledge}", kb)


def inject_system_into_messages(
    messages: list[dict[str, str]],
    conv: ChatConversation | None,
    *,
    knowledge_block: str = "",
) -> list[dict[str, str]]:
    content = _effective_system_prompt(conv, knowledge_block=knowledge_block)
    if not content.strip():
        return messages
    if messages and str(messages[0].get("role")) == "system":
        return messages
    return [{"role": "system", "content": content}, *messages]


def _default_llm_model_for_space(db: Session, *, enterprise_space_id: int) -> AIModel | None:
    binding = db.execute(
        select(AIModelDefault)
        .options(selectinload(AIModelDefault.model).selectinload(AIModel.provider))
        .where(
            AIModelDefault.enterprise_space_id == enterprise_space_id,
            AIModelDefault.model_type == "llm",
        )
    ).scalar_one_or_none()
    if not binding or binding.model is None:
        return None
    model = binding.model
    if not model.is_enabled:
        return None
    return model


def _default_llm_model_fields_for_space(
    db: Session, *, enterprise_space_id: int
) -> tuple[str | None, str | None]:
    """Resolve default LLM model_name and provider_code from model management defaults."""
    model = _default_llm_model_for_space(db, enterprise_space_id=enterprise_space_id)
    if model is None:
        return None, None
    code = model.provider.provider_code if model.provider else None
    return model.model_name, code


def _apply_default_llm_if_missing(
    db: Session, *, config_data: dict, enterprise_space_id: int
) -> None:
    raw_name = config_data.get("model_name")
    name_ok = isinstance(raw_name, str) and bool(raw_name.strip())
    if name_ok:
        return
    model = _default_llm_model_for_space(db, enterprise_space_id=enterprise_space_id)
    if model:
        config_data["model_name"] = model.model_name
        if model.provider:
            config_data["model_provider"] = model.provider.provider_code
        config_data["model_id"] = model.id


def _config_response(conv: ChatConversation) -> ChatConfigurationResponse:
    return ChatConfigurationResponse(
        id=conv.id,
        chat_id=conv.id,
        model_provider=conv.model_provider,
        model_name=conv.model_name,
        model_id=conv.selected_llm_model_id,
        knowledge_base_ids=list(conv.knowledge_base_ids or []),
        show_citations=bool(getattr(conv, "show_citations", True)),
        retrieval_top_k=_merge_top_k_for_conversation(conv),
        temperature=float(conv.temperature),
        max_tokens=int(conv.max_tokens),
        top_p=float(conv.top_p),
        system_prompt=conv.system_prompt,
    )


def _resolve_chat_llm(
    db: Session, *, conv: ChatConversation, enterprise_space_id: int
) -> tuple[AIModelProvider | None, str]:
    """解析聊天使用的厂商配置与下游 API model 名称（字符串）。"""
    if conv.selected_llm_model_id is not None:
        model = db.execute(
            select(AIModel)
            .options(selectinload(AIModel.provider))
            .where(
                AIModel.id == conv.selected_llm_model_id,
                AIModel.enterprise_space_id == enterprise_space_id,
                AIModel.model_type == "llm",
                AIModel.is_enabled.is_(True),
            )
        ).scalar_one_or_none()
        if model is None or model.provider is None:
            raise AppError(
                400,
                "CHAT_MODEL_NOT_FOUND",
                "对话绑定的模型不存在、未启用或已删除，请在聊天设置中重新选择模型",
            )
        api_name = (model.model_name or model.model_code or "").strip()
        if not api_name:
            raise AppError(500, "CHAT_MODEL_MISCONFIGURED", "模型缺少 model_name / model_code")
        return model.provider, api_name

    code = (conv.model_provider or "").strip()
    name = (conv.model_name or "").strip()
    if not code or not name:
        return None, ""

    pairs = db.execute(
        select(AIModelProvider)
        .join(AIModel, AIModel.provider_id == AIModelProvider.id)
        .where(
            AIModelProvider.enterprise_space_id == enterprise_space_id,
            AIModelProvider.provider_code == code,
            AIModel.model_name == name,
            AIModel.model_type == "llm",
            AIModel.is_enabled.is_(True),
        )
    ).scalars().unique().all()
    if len(pairs) > 1:
        raise AppError(
            400,
            "AMBIGUOUS_LLM_PROVIDER",
            "存在多条相同「模型名称 + provider_code」的接入（通常为不同网关 URL）。请在聊天设置里重新选择模型以绑定 model_id。",
        )
    if len(pairs) == 1:
        return pairs[0], name

    provs = db.execute(
        select(AIModelProvider).where(
            AIModelProvider.enterprise_space_id == enterprise_space_id,
            AIModelProvider.provider_code == code,
        )
    ).scalars().all()
    if len(provs) > 1:
        raise AppError(
            400,
            "AMBIGUOUS_PROVIDER_CODE",
            "存在多个相同 provider_code 的厂商配置，无法唯一确定接入。请在聊天设置里重新选择模型以绑定 model_id。",
        )
    if len(provs) == 1:
        return provs[0], name
    return None, name


def _touch_conversation(db: Session, conversation_id: str) -> None:
    conv = db.get(ChatConversation, conversation_id)
    if conv is not None:
        conv.updated_at = datetime.utcnow()
        db.add(conv)


def get_chat_conversation(
    db: Session, *, conversation_id: str, user_id: int, enterprise_space_id: int
) -> ChatConversation:
    stmt = select(ChatConversation).where(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == user_id,
        ChatConversation.enterprise_space_id == enterprise_space_id,
    )
    obj = db.execute(stmt).scalar_one_or_none()
    if not obj:
        raise AppError(404, "CONVERSATION_NOT_FOUND", "Conversation not found")
    return obj


def list_chat_conversations(
    db: Session, *, user_id: int, enterprise_space_id: int, skip: int = 0, limit: int = 100
) -> list[ChatConversation]:
    stmt = (
        select(ChatConversation)
        .where(
            ChatConversation.user_id == user_id,
            ChatConversation.enterprise_space_id == enterprise_space_id,
        )
        .order_by(ChatConversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def create_chat_conversation(
    db: Session, *, obj_in: ChatConversationCreate, user_id: int, enterprise_space_id: int
) -> ChatConversation:
    if obj_in.configuration:
        config_data = obj_in.configuration.model_dump(exclude_unset=True)
    else:
        config_data = {}
    _apply_default_llm_if_missing(db, config_data=config_data, enterprise_space_id=enterprise_space_id)

    conv_id = str(uuid.uuid4())
    conv = ChatConversation(
        id=conv_id,
        user_id=user_id,
        enterprise_space_id=enterprise_space_id,
        title=obj_in.title,
        model_provider=config_data.get("model_provider"),
        model_name=config_data.get("model_name"),
        selected_llm_model_id=config_data.get("model_id"),
        knowledge_base_ids=list(config_data.get("knowledge_base_ids") or []),
        show_citations=bool(config_data.get("show_citations", True)),
        retrieval_top_k=_clamp_retrieval_top_k(config_data.get("retrieval_top_k")),
        temperature=float(config_data.get("temperature", 0.7)),
        max_tokens=int(config_data.get("max_tokens", 2000)),
        top_p=float(config_data.get("top_p", 1.0)),
        system_prompt=config_data.get("system_prompt"),
    )
    db.add(conv)
    db.flush()

    first_session = ChatSession(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        user_id=user_id,
        enterprise_space_id=enterprise_space_id,
        title="会话 1",
    )
    db.add(first_session)
    db.commit()
    db.refresh(conv)
    return conv


def update_chat_conversation(
    db: Session,
    *,
    conversation_id: str,
    obj_in: ChatConversationUpdate,
    user_id: int,
    enterprise_space_id: int,
) -> ChatConversation:
    db_obj = get_chat_conversation(
        db, conversation_id=conversation_id, user_id=user_id, enterprise_space_id=enterprise_space_id
    )
    db_obj.title = obj_in.title
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_chat_conversation(
    db: Session, *, conversation_id: str, user_id: int, enterprise_space_id: int
) -> None:
    db_obj = get_chat_conversation(
        db, conversation_id=conversation_id, user_id=user_id, enterprise_space_id=enterprise_space_id
    )
    db.delete(db_obj)
    db.commit()


def list_sessions_for_conversation(
    db: Session, *, conversation_id: str, user_id: int, enterprise_space_id: int
) -> list[ChatSession]:
    get_chat_conversation(
        db, conversation_id=conversation_id, user_id=user_id, enterprise_space_id=enterprise_space_id
    )
    stmt = (
        select(ChatSession)
        .where(ChatSession.conversation_id == conversation_id)
        .order_by(ChatSession.updated_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def create_session_in_conversation(
    db: Session,
    *,
    conversation_id: str,
    obj_in: ChatSessionCreate,
    user_id: int,
    enterprise_space_id: int,
) -> ChatSession:
    get_chat_conversation(
        db, conversation_id=conversation_id, user_id=user_id, enterprise_space_id=enterprise_space_id
    )
    db_obj = ChatSession(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        user_id=user_id,
        enterprise_space_id=enterprise_space_id,
        title=obj_in.title,
    )
    db.add(db_obj)
    _touch_conversation(db, conversation_id)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_chat_session(
    db: Session, *, session_id: str, user_id: int, enterprise_space_id: int
) -> ChatSession:
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
        ChatSession.enterprise_space_id == enterprise_space_id,
    )
    session_obj = db.execute(stmt).scalar_one_or_none()
    if not session_obj:
        raise AppError(404, "SESSION_NOT_FOUND", "Chat session not found")
    return session_obj


def update_chat_session(
    db: Session, *, session_id: str, obj_in: ChatSessionUpdate, user_id: int, enterprise_space_id: int
) -> ChatSession:
    db_obj = get_chat_session(db, session_id=session_id, user_id=user_id, enterprise_space_id=enterprise_space_id)
    db_obj.title = obj_in.title
    _touch_conversation(db, db_obj.conversation_id)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_chat_session(
    db: Session, *, session_id: str, user_id: int, enterprise_space_id: int
) -> None:
    db_obj = get_chat_session(db, session_id=session_id, user_id=user_id, enterprise_space_id=enterprise_space_id)
    conv_id = db_obj.conversation_id
    db.delete(db_obj)
    db.flush()
    cnt = db.execute(
        select(func.count()).select_from(ChatSession).where(ChatSession.conversation_id == conv_id)
    ).scalar_one()
    if cnt == 0:
        conv = db.get(ChatConversation, conv_id)
        if conv is not None:
            db.delete(conv)
    else:
        _touch_conversation(db, conv_id)
    db.commit()


def get_chat_configuration(
    db: Session, *, session_id: str, user_id: int, enterprise_space_id: int
) -> ChatConfigurationResponse:
    session_obj = get_chat_session(db, session_id=session_id, user_id=user_id, enterprise_space_id=enterprise_space_id)
    conv = db.get(ChatConversation, session_obj.conversation_id)
    if conv is None:
        raise AppError(404, "CONVERSATION_NOT_FOUND", "Conversation not found")
    raw_name = conv.model_name
    if not (isinstance(raw_name, str) and raw_name.strip()):
        model = _default_llm_model_for_space(db, enterprise_space_id=session_obj.enterprise_space_id)
        if model and model.provider:
            conv.model_name = model.model_name
            conv.model_provider = model.provider.provider_code
            conv.selected_llm_model_id = model.id
            db.add(conv)
            _touch_conversation(db, session_obj.conversation_id)
            db.commit()
            db.refresh(conv)
    return _config_response(conv)


def update_chat_configuration(
    db: Session, *, session_id: str, obj_in: ChatConfigurationUpdate, user_id: int, enterprise_space_id: int
) -> ChatConfigurationResponse:
    session_obj = get_chat_session(db, session_id=session_id, user_id=user_id, enterprise_space_id=enterprise_space_id)
    conv = db.get(ChatConversation, session_obj.conversation_id)
    if conv is None:
        raise AppError(404, "CONVERSATION_NOT_FOUND", "Conversation not found")

    update_data = obj_in.model_dump(exclude_unset=True)
    mid = update_data.pop("model_id", None)
    if mid is not None:
        conv.selected_llm_model_id = mid
    for field, value in update_data.items():
        setattr(conv, field, value)

    db.add(conv)
    _touch_conversation(db, session_obj.conversation_id)
    db.commit()
    db.refresh(conv)
    return _config_response(conv)


def get_chat_messages(
    db: Session, *, session_id: str, user_id: int, enterprise_space_id: int, skip: int = 0, limit: int = 100
) -> list[ChatMessage]:
    get_chat_session(db, session_id=session_id, user_id=user_id, enterprise_space_id=enterprise_space_id)

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def add_chat_message(
    db: Session,
    *,
    session_id: str,
    role: str,
    content: str,
    message_id: str | None = None,
    citations: list[dict[str, Any]] | None = None,
) -> ChatMessage:
    mid = message_id or str(uuid.uuid4())
    cite_store = citations if role == "assistant" and citations else None
    msg = ChatMessage(id=mid, session_id=session_id, role=role, content=content, citations=cite_store)
    db.add(msg)
    db.flush()
    sess = db.get(ChatSession, session_id)
    if sess is not None:
        _touch_conversation(db, sess.conversation_id)
        sess.updated_at = datetime.utcnow()
        db.add(sess)
    db.commit()
    db.refresh(msg)
    return msg


_STREAM_STOP = object()


def _next_stream_chunk(stream_iter: Iterator[str]) -> str | object:
    try:
        return next(stream_iter)
    except StopIteration:
        return _STREAM_STOP


def iter_chat_stream_events(
    db: Session,
    *,
    session_id: str,
    user_id: int,
    enterprise_space_id: int,
    user_content: str,
) -> Iterator[dict[str, object]]:
    """One chat turn: persist user message, stream assistant text chunks, persist assistant; yields event dicts."""
    session_obj = get_chat_session(
        db, session_id=session_id, user_id=user_id, enterprise_space_id=enterprise_space_id
    )

    add_chat_message(db, session_id=session_id, role="user", content=user_content)

    conv = db.get(ChatConversation, session_obj.conversation_id)

    provider_cfg: AIModelProvider | None = None
    api_model_name = ""
    if conv:
        try:
            provider_cfg, api_model_name = _resolve_chat_llm(
                db, conv=conv, enterprise_space_id=session_obj.enterprise_space_id
            )
        except AppError as e:
            assistant_content = f"【错误】{e.message}"
            yield {"type": "assistant_delta", "content": assistant_content}
            saved = add_chat_message(db, session_id=session_id, role="assistant", content=assistant_content)
            yield {
                "type": "assistant_done",
                "id": saved.id,
                "session_id": saved.session_id,
                "role": saved.role,
                "content": saved.content,
                "created_at": saved.created_at.isoformat(),
                "citations": [],
            }
            return

    assistant_content = ""
    parts: list[str] = []
    turn_citations: list[dict[str, Any]] = []

    if provider_cfg and api_model_name:
        try:
            history = db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
                .limit(20)
            ).scalars().all()

            messages = [{"role": msg.role, "content": msg.content} for msg in history]
            kb_block, turn_citations = _retrieve_knowledge_block_and_citations(
                db,
                enterprise_space_id=session_obj.enterprise_space_id,
                knowledge_base_ids=list(conv.knowledge_base_ids or []) if conv else [],
                query=user_content,
                merge_top_k=_merge_top_k_for_conversation(conv),
            )
            if kb_block:
                kb_block = kb_block + (
                    _CITATION_HINT_SUFFIX if getattr(conv, "show_citations", True) else ""
                )
            messages = inject_system_into_messages(messages, conv, knowledge_block=kb_block)

            provider = get_provider(provider_cfg)
            stream_iter = iter(provider.chat_stream_chunks(api_model_name, messages))
            while True:
                chunk = _next_stream_chunk(stream_iter)
                if chunk is _STREAM_STOP:
                    break
                piece = str(chunk)
                parts.append(piece)
                yield {"type": "assistant_delta", "content": piece}
            assistant_content = "".join(parts)
        except Exception as e:
            tail = f"\n\n【错误】{e!s}"
            assistant_content = "".join(parts) + (tail if parts else f"Exception: {e!s}")
            yield {"type": "assistant_delta", "content": tail if parts else f"Exception: {e!s}"}
            turn_citations = []
    else:
        assistant_content = f"Echo: {user_content} (No model configured)"
        yield {"type": "assistant_delta", "content": assistant_content}

    saved = add_chat_message(
        db,
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        citations=turn_citations or None,
    )
    yield {
        "type": "assistant_done",
        "id": saved.id,
        "session_id": saved.session_id,
        "role": saved.role,
        "content": saved.content,
        "created_at": saved.created_at.isoformat(),
        "citations": list(saved.citations or []),
    }


def _normalize_openai_messages_list(
    messages: list[OpenAICompatMessage] | list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    if not messages:
        return []
    out: list[dict[str, str]] = []
    for m in messages:
        if isinstance(m, OpenAICompatMessage):
            role, content = m.role, m.content
        elif isinstance(m, dict):
            role, content = m.get("role"), m.get("content")
        else:
            continue
        if role not in ("system", "user", "assistant"):
            continue
        if content is None:
            continue
        s = str(content)
        if not s.strip():
            continue
        out.append({"role": str(role), "content": s})
    return out


def _last_user_content_from_messages(messages: list[dict[str, str]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return str(m.get("content") or "")
    return ""


def _openai_stream_chunk_dict(
    *,
    completion_id: str,
    created: int,
    model: str,
    chat_id: str,
    session_id: str,
    content: str | None = None,
    role: str | None = None,
    finish_reason: str | None = None,
) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    if role is not None:
        delta["role"] = role
    if content:
        delta["content"] = content
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        "chat_id": chat_id,
        "session_id": session_id,
    }


def _extract_assistant_from_openai_completion(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not choices or not isinstance(choices, list):
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    msg = first.get("message")
    if isinstance(msg, dict):
        c = msg.get("content")
        return str(c) if c is not None else ""
    return ""


def ensure_session_for_completion(
    db: Session,
    *,
    chat_id: str,
    session_id: str | None,
    user_id: int,
    enterprise_space_id: int,
) -> ChatSession:
    get_chat_conversation(
        db, conversation_id=chat_id, user_id=user_id, enterprise_space_id=enterprise_space_id
    )
    if session_id:
        sess = get_chat_session(
            db, session_id=session_id, user_id=user_id, enterprise_space_id=enterprise_space_id
        )
        if sess.conversation_id != chat_id:
            raise AppError(
                400, "SESSION_CHAT_MISMATCH", "session_id does not belong to the given chat_id"
            )
        return sess
    cnt = db.execute(
        select(func.count()).select_from(ChatSession).where(ChatSession.conversation_id == chat_id)
    ).scalar_one()
    n = int(cnt) + 1
    return create_session_in_conversation(
        db,
        conversation_id=chat_id,
        obj_in=ChatSessionCreate(title=f"会话 {n}"),
        user_id=user_id,
        enterprise_space_id=enterprise_space_id,
    )


def build_completion_messages(
    db: Session,
    *,
    session: ChatSession,
    request_messages: list[OpenAICompatMessage] | list[dict[str, Any]] | None,
    question: str | None,
) -> tuple[list[dict[str, str]], str, list[dict[str, Any]]]:
    conv = db.get(ChatConversation, session.conversation_id)
    normalized = _normalize_openai_messages_list(request_messages)
    if normalized:
        user_text = _last_user_content_from_messages(normalized)
        if not user_text.strip():
            raise AppError(400, "INVALID_MESSAGES", "messages must include a user message with non-empty content")
        kb_block, cites = _retrieve_knowledge_block_and_citations(
            db,
            enterprise_space_id=session.enterprise_space_id,
            knowledge_base_ids=list(conv.knowledge_base_ids or []) if conv else [],
            query=user_text,
            merge_top_k=_merge_top_k_for_conversation(conv),
        )
        if kb_block:
            kb_block = kb_block + (_CITATION_HINT_SUFFIX if getattr(conv, "show_citations", True) else "")
        return inject_system_into_messages(normalized, conv, knowledge_block=kb_block), user_text, cites
    q = (question or "").strip()
    if not q:
        raise AppError(
            400,
            "MESSAGES_NORMALIZATION_EMPTY",
            "messages 无有效条目；请提供 question 或有效的 messages",
        )
    history = db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(20)
    ).scalars().all()
    hist_dicts = [{"role": m.role, "content": m.content} for m in history]
    merged = [*hist_dicts, {"role": "user", "content": q}]
    kb_block, cites = _retrieve_knowledge_block_and_citations(
        db,
        enterprise_space_id=session.enterprise_space_id,
        knowledge_base_ids=list(conv.knowledge_base_ids or []) if conv else [],
        query=q,
        merge_top_k=_merge_top_k_for_conversation(conv),
    )
    if kb_block:
        kb_block = kb_block + (_CITATION_HINT_SUFFIX if getattr(conv, "show_citations", True) else "")
    return inject_system_into_messages(merged, conv, knowledge_block=kb_block), q, cites


def iter_openai_completion_events(
    db: Session,
    *,
    session_id: str,
    chat_id: str,
    user_id: int,
    enterprise_space_id: int,
    user_content_to_persist: str,
    llm_messages: list[dict[str, str]],
    turn_citations: list[dict[str, Any]] | None = None,
) -> Iterator[dict[str, Any]]:
    session_obj = get_chat_session(
        db, session_id=session_id, user_id=user_id, enterprise_space_id=enterprise_space_id
    )
    if session_obj.conversation_id != chat_id:
        raise AppError(400, "SESSION_CHAT_MISMATCH", "session_id does not belong to the given chat_id")

    add_chat_message(db, session_id=session_id, role="user", content=user_content_to_persist)
    conv = db.get(ChatConversation, session_obj.conversation_id)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    model_label = (conv.model_name if conv else None) or "unknown"

    yield _openai_stream_chunk_dict(
        completion_id=completion_id,
        created=created,
        model=model_label,
        chat_id=chat_id,
        session_id=session_id,
        role="assistant",
        finish_reason=None,
    )

    assistant_content = ""
    parts: list[str] = []

    provider_cfg: AIModelProvider | None = None
    api_model_name = ""
    if conv:
        try:
            provider_cfg, api_model_name = _resolve_chat_llm(
                db, conv=conv, enterprise_space_id=session_obj.enterprise_space_id
            )
            if api_model_name:
                model_label = api_model_name
        except AppError as e:
            assistant_content = f"【错误】{e.message}"
            yield _openai_stream_chunk_dict(
                completion_id=completion_id,
                created=created,
                model=model_label,
                chat_id=chat_id,
                session_id=session_id,
                content=assistant_content,
                finish_reason=None,
            )
            add_chat_message(db, session_id=session_id, role="assistant", content=assistant_content)
            yield _openai_stream_chunk_dict(
                completion_id=completion_id,
                created=created,
                model=model_label,
                chat_id=chat_id,
                session_id=session_id,
                finish_reason="stop",
            )
            return

    if provider_cfg and api_model_name:
        try:
            provider = get_provider(provider_cfg)
            stream_iter = iter(provider.chat_stream_chunks(api_model_name, llm_messages))
            while True:
                chunk = _next_stream_chunk(stream_iter)
                if chunk is _STREAM_STOP:
                    break
                piece = str(chunk)
                parts.append(piece)
                yield _openai_stream_chunk_dict(
                    completion_id=completion_id,
                    created=created,
                    model=model_label,
                    chat_id=chat_id,
                    session_id=session_id,
                    content=piece,
                    finish_reason=None,
                )
            assistant_content = "".join(parts)
        except Exception as e:
            tail = f"\n\n【错误】{e!s}"
            assistant_content = "".join(parts) + (tail if parts else f"Exception: {e!s}")
            yield _openai_stream_chunk_dict(
                completion_id=completion_id,
                created=created,
                model=model_label,
                chat_id=chat_id,
                session_id=session_id,
                content=tail if parts else f"Exception: {e!s}",
                finish_reason=None,
            )
    else:
        assistant_content = f"Echo: {user_content_to_persist} (No model configured)"
        yield _openai_stream_chunk_dict(
            completion_id=completion_id,
            created=created,
            model=model_label,
            chat_id=chat_id,
            session_id=session_id,
            content=assistant_content,
            finish_reason=None,
        )

    add_chat_message(
        db,
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        citations=turn_citations if turn_citations else None,
    )
    yield _openai_stream_chunk_dict(
        completion_id=completion_id,
        created=created,
        model=model_label,
        chat_id=chat_id,
        session_id=session_id,
        finish_reason="stop",
    )


def run_chat_completion_blocking(
    db: Session,
    *,
    session_id: str,
    chat_id: str,
    user_id: int,
    enterprise_space_id: int,
    user_content_to_persist: str,
    llm_messages: list[dict[str, str]],
    turn_citations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    session_obj = get_chat_session(
        db, session_id=session_id, user_id=user_id, enterprise_space_id=enterprise_space_id
    )
    if session_obj.conversation_id != chat_id:
        raise AppError(400, "SESSION_CHAT_MISMATCH", "session_id does not belong to the given chat_id")

    add_chat_message(db, session_id=session_id, role="user", content=user_content_to_persist)
    conv = db.get(ChatConversation, session_obj.conversation_id)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    model_label = (conv.model_name if conv else None) or "unknown"

    provider_cfg: AIModelProvider | None = None
    api_model_name = ""
    if conv:
        try:
            provider_cfg, api_model_name = _resolve_chat_llm(
                db, conv=conv, enterprise_space_id=session_obj.enterprise_space_id
            )
            if api_model_name:
                model_label = api_model_name
        except AppError as e:
            assistant_content = f"【错误】{e.message}"
            add_chat_message(db, session_id=session_id, role="assistant", content=assistant_content)
            return {
                "completion_id": completion_id,
                "created": created,
                "model": model_label,
                "content": assistant_content,
            }

    if provider_cfg and api_model_name:
        provider = get_provider(provider_cfg)
        resp = provider.chat(api_model_name, llm_messages)
        if not resp.success:
            assistant_content = f"【错误】{resp.message}"
        else:
            assistant_content = _extract_assistant_from_openai_completion(resp.data) or ""
    else:
        assistant_content = f"Echo: {user_content_to_persist} (No model configured)"

    add_chat_message(
        db,
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        citations=turn_citations if turn_citations else None,
    )
    return {
        "completion_id": completion_id,
        "created": created,
        "model": model_label,
        "content": assistant_content,
    }
