from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.core.openai_compat import (
    build_chat_completion_chunk,
    estimate_usage,
    last_user_content as _last_user_content_from_messages,
    normalize_openai_messages as _normalize_openai_messages_list,
    validate_messages_last_role_is_user,
)
from app.core.provider_adapter import get_provider
from app.models.chat import ChatConversation, ChatMessage, ChatSession
from app.models.knowledge_base import KnowledgeBase
from app.models.model_management import AIModel, AIModelDefault, AIModelProvider
from app.core.knowledge_retrieval_defaults import DEFAULT_TOP_K
from app.schemas.chat import (
    ChatConfigurationResponse,
    ChatConfigurationUpdate,
    ChatConversationCreate,
    ChatConversationUpdate,
    ChatSessionCreate,
    ChatSessionUpdate,
    OpenAICompatMessage,
)


DEFAULT_CHAT_SYSTEM_PROMPT_RAG = (
    "你是一个智能助手。下面「参考片段」来自用户所选知识库的检索结果，条目以 [1]、[2]… 编号，可作引用。\n"
    "作答要求：\n"
    "1）若问题需要依据文档，请优先引用参考片段中的信息，并在对应叙述处使用角标 [1]、[2] 等。\n"
    "2）若问题是问候、闲聊、常识、或明显与参考片段无关（例如询问你是谁、用的什么模型），请直接自然回答，不要强行引用片段，也不要说「知识库中未找到您要的答案」之类套话。\n"
    "3）仅当用户问题**明确期望**从知识库文档中得到事实，且参考片段均不相关或明显不足时，再说明「知识库中未找到您要的答案！」并可补充合理说明。\n"
    "回答需结合聊天历史。\n以下是参考片段：\n{knowledge}\n以上结束。"
)

DEFAULT_CHAT_SYSTEM_PROMPT_GENERAL = (
    "你是一个乐于助人的智能助手。请结合聊天历史自然回答用户问题。\n"
    "当前对话未选择知识库，或本轮检索未返回任何参考片段：请按通用对话方式回复，不必强行关联知识库或编造文档来源。"
)

# 兼容旧代码与文档中的名称：默认 GENERAL 作为「未自定义且未注入片段」时的基线说明长度参考
DEFAULT_CHAT_SYSTEM_PROMPT = DEFAULT_CHAT_SYSTEM_PROMPT_GENERAL

_CITATION_HINT_SUFFIX = (
    "\n\n（请在回答中引用上述片段时，在对应句末使用角标 [1]、[2] 等与编号对应；"
    "综合多条时可写 [1][2]。未用到的编号勿标注。）"
)


def _clamp_retrieval_top_k(raw: Any) -> int:
    if raw is None:
        return DEFAULT_TOP_K
    try:
        return max(1, min(50, int(raw)))
    except (TypeError, ValueError):
        return DEFAULT_TOP_K


def _default_top_k_for_kb_ids(db: Session, *, enterprise_space_id: int, kb_ids: list[int]) -> int:
    if not kb_ids:
        return DEFAULT_TOP_K
    kb = db.execute(
        select(KnowledgeBase.default_top_k).where(
            KnowledgeBase.enterprise_space_id == enterprise_space_id,
            KnowledgeBase.id == int(kb_ids[0]),
            KnowledgeBase.status != "deleted",
        )
    ).scalar_one_or_none()
    if kb is None:
        return DEFAULT_TOP_K
    return _clamp_retrieval_top_k(kb)


def _merge_top_k_for_conversation(conv: ChatConversation | None) -> int:
    if conv is None:
        return DEFAULT_TOP_K
    return _clamp_retrieval_top_k(getattr(conv, "retrieval_top_k", None))


def _retrieve_knowledge_block_and_citations(
    db: Session,
    *,
    enterprise_space_id: int,
    knowledge_base_ids: list[int],
    query: str,
    merge_top_k: int = 8,
    lightrag_query_mode: str = "mix",
) -> tuple[str, list[dict[str, Any]]]:
    q = (query or "").strip()
    ids = [int(x) for x in knowledge_base_ids if x is not None]
    unique_ids = list(dict.fromkeys(ids))
    if not q or not unique_ids:
        return "", []

    kb_rows = db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.enterprise_space_id == enterprise_space_id,
            KnowledgeBase.id.in_(unique_ids),
            KnowledgeBase.status != "deleted",
        )
    ).scalars().all()
    if not kb_rows:
        return "", []

    kb_by_id = {kb.id: kb for kb in kb_rows}
    ordered_existing = [kid for kid in unique_ids if kid in kb_by_id]
    if not ordered_existing:
        return "", []

    from app.core.kb_type import is_lightrag_kb
    from app.schemas.retrieval import KnowledgeSearchRequest
    from app.services.lightrag_engine import query_graph_kb
    from app.services.retrieval_service import search_knowledge_bases_multi

    cap = _clamp_retrieval_top_k(merge_top_k)
    classic_ids = [kid for kid in ordered_existing if not is_lightrag_kb(kb_by_id[kid])]
    lightrag_ids = [kid for kid in ordered_existing if is_lightrag_kb(kb_by_id[kid])]

    parts: list[str] = []
    citations: list[dict[str, Any]] = []
    ref = 0

    if classic_ids:
        try:
            data = search_knowledge_bases_multi(
                db,
                space_id=enterprise_space_id,
                knowledge_base_ids=classic_ids,
                payload=KnowledgeSearchRequest(query=q[:2000], top_k=cap),
            )
            for item in data.get("results") or []:
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
        except AppError:
            pass

    mode = lightrag_query_mode if lightrag_query_mode in ("naive", "local", "global", "hybrid", "mix") else "mix"
    per_kb_top_k = max(1, cap // max(len(lightrag_ids), 1)) if lightrag_ids else cap
    for kb_id in lightrag_ids:
        kb = kb_by_id[kb_id]
        try:
            graph_data = query_graph_kb(
                db,
                knowledge_base=kb,
                query=q[:2000],
                mode=mode,
                top_k=per_kb_top_k,
                include_references=True,
            )
        except AppError:
            continue
        block = str(graph_data.get("answer_context") or "").strip()
        if block:
            parts.append(block)
        for cite in graph_data.get("citations") or []:
            if not isinstance(cite, dict):
                continue
            ref = int(cite.get("ref") or ref + 1)
            citations.append(
                {
                    "ref": ref,
                    "document_name": cite.get("document_name"),
                    "page_no": None,
                    "chunk_id": cite.get("chunk_id"),
                    "document_id": cite.get("document_id"),
                    "chunk_index": None,
                    "knowledge_base_id": kb_id,
                    "score": None,
                }
            )

    if not parts:
        return "", []

    return "\n\n---\n\n".join(parts), citations


def _effective_system_prompt(conv: ChatConversation | None, *, knowledge_block: str = "") -> str:
    kb_nonempty = bool((knowledge_block or "").strip())
    custom: str | None = None
    if conv is not None and conv.system_prompt is not None:
        s = str(conv.system_prompt).strip()
        if s:
            custom = s
    if custom is None:
        if kb_nonempty:
            return DEFAULT_CHAT_SYSTEM_PROMPT_RAG.strip().replace("{knowledge}", knowledge_block.strip())
        return DEFAULT_CHAT_SYSTEM_PROMPT_GENERAL.strip()
    if "{knowledge}" in custom:
        kb_subst = knowledge_block.strip() if kb_nonempty else "（本轮尚未注入检索片段）"
        return custom.replace("{knowledge}", kb_subst)
    return custom


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
        lightrag_query_mode=str(getattr(conv, "lightrag_query_mode", None) or "mix"),
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
                status_code=400,
                code="CHAT_MODEL_NOT_FOUND",
                message="对话绑定的模型不存在、未启用或已删除，请在聊天设置中重新选择模型",
            )
        api_name = (model.model_name or model.model_code or "").strip()
        if not api_name:
            raise AppError(
                status_code=500,
                code="CHAT_MODEL_MISCONFIGURED",
                message="模型缺少 model_name / model_code",
            )
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
            status_code=400,
            code="AMBIGUOUS_LLM_PROVIDER",
            message="存在多条相同「模型名称 + provider_code」的接入（通常为不同网关 URL）。请在聊天设置里重新选择模型以绑定 model_id。",
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
            status_code=400,
            code="AMBIGUOUS_PROVIDER_CODE",
            message="存在多个相同 provider_code 的厂商配置，无法唯一确定接入。请在聊天设置里重新选择模型以绑定 model_id。",
        )
    if len(provs) == 1:
        return provs[0], name
    return None, name


def _touch_conversation(db: Session, conversation_id: str) -> None:
    conv = db.get(ChatConversation, conversation_id)
    if conv is not None:
        conv.updated_at = datetime.utcnow()
        db.add(conv)


def _conversation_row_after_user_message(db: Session, conversation_id: str) -> ChatConversation | None:
    """在用户消息已写入并可能触发 _touch_conversation 加载过对话行后，强制从库重读，避免 identity map 沿用切换模型前的旧字段。"""
    conv = db.get(ChatConversation, conversation_id)
    if conv is not None:
        db.refresh(conv)
    return conv


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
        raise AppError(status_code=404, code="CONVERSATION_NOT_FOUND", message="Conversation not found")
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
    kb_ids = list(config_data.get("knowledge_base_ids") or [])
    top_k_raw = config_data.get("retrieval_top_k")
    if top_k_raw is None and kb_ids:
        top_k_raw = _default_top_k_for_kb_ids(db, enterprise_space_id=enterprise_space_id, kb_ids=kb_ids)

    conv = ChatConversation(
        id=conv_id,
        user_id=user_id,
        enterprise_space_id=enterprise_space_id,
        title=obj_in.title,
        model_provider=config_data.get("model_provider"),
        model_name=config_data.get("model_name"),
        selected_llm_model_id=config_data.get("model_id"),
        knowledge_base_ids=kb_ids,
        show_citations=bool(config_data.get("show_citations", True)),
        retrieval_top_k=_clamp_retrieval_top_k(top_k_raw),
        lightrag_query_mode=str(config_data.get("lightrag_query_mode") or "mix"),
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
        raise AppError(status_code=404, code="SESSION_NOT_FOUND", message="Chat session not found")
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
        raise AppError(status_code=404, code="CONVERSATION_NOT_FOUND", message="Conversation not found")
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
        raise AppError(status_code=404, code="CONVERSATION_NOT_FOUND", message="Conversation not found")

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


def complete_chat_turn_blocking(
    db: Session,
    *,
    session_id: str,
    user_id: int,
    enterprise_space_id: int,
    user_content: str,
) -> dict[str, object]:
    """单轮非流式：执行与 /stream 相同的推理逻辑，返回 assistant_done 载荷。"""
    done: dict[str, object] | None = None
    for event in iter_chat_stream_events(
        db,
        session_id=session_id,
        user_id=user_id,
        enterprise_space_id=enterprise_space_id,
        user_content=user_content,
    ):
        if event.get("type") == "assistant_done":
            done = event
    if done is None:
        raise AppError(status_code=500, code="CHAT_TURN_FAILED", message="未收到 assistant_done 事件")
    return done


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

    conv = _conversation_row_after_user_message(db, session_obj.conversation_id)

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
                lightrag_query_mode=str(getattr(conv, "lightrag_query_mode", None) or "mix"),
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
                status_code=400,
                code="SESSION_CHAT_MISMATCH",
                message="session_id does not belong to the given chat_id",
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
        validate_messages_last_role_is_user(normalized)
        user_text = _last_user_content_from_messages(normalized)
        if not user_text.strip():
            raise AppError(
                status_code=400,
                code="INVALID_MESSAGES",
                message="messages must include a user message with non-empty content",
            )
        kb_block, cites = _retrieve_knowledge_block_and_citations(
            db,
            enterprise_space_id=session.enterprise_space_id,
            knowledge_base_ids=list(conv.knowledge_base_ids or []) if conv else [],
            query=user_text,
            merge_top_k=_merge_top_k_for_conversation(conv),
            lightrag_query_mode=str(getattr(conv, "lightrag_query_mode", None) or "mix"),
        )
        if kb_block:
            kb_block = kb_block + (_CITATION_HINT_SUFFIX if getattr(conv, "show_citations", True) else "")
        return inject_system_into_messages(normalized, conv, knowledge_block=kb_block), user_text, cites
    q = (question or "").strip()
    if not q:
        raise AppError(
            status_code=400,
            code="MESSAGES_NORMALIZATION_EMPTY",
            message="messages 无有效条目；请提供 question 或有效的 messages",
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
        lightrag_query_mode=str(getattr(conv, "lightrag_query_mode", None) or "mix"),
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
    response_model: str | None = None,
) -> Iterator[dict[str, Any]]:
    session_obj = get_chat_session(
        db, session_id=session_id, user_id=user_id, enterprise_space_id=enterprise_space_id
    )
    if session_obj.conversation_id != chat_id:
        raise AppError(
            status_code=400,
            code="SESSION_CHAT_MISMATCH",
            message="session_id does not belong to the given chat_id",
        )

    add_chat_message(db, session_id=session_id, role="user", content=user_content_to_persist)
    conv = _conversation_row_after_user_message(db, session_obj.conversation_id)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    model_label = response_model or (conv.model_name if conv else None) or "model"

    yield build_chat_completion_chunk(
        completion_id=completion_id,
        created=created,
        model=model_label,
        chat_id=chat_id,
        session_id=session_id,
        content=None,
        role="assistant",
        finish_reason=None,
        usage=None,
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
            if api_model_name and not response_model:
                model_label = api_model_name
        except AppError as e:
            assistant_content = f"【错误】{e.message}"
            yield build_chat_completion_chunk(
                completion_id=completion_id,
                created=created,
                model=model_label,
                chat_id=chat_id,
                session_id=session_id,
                content=assistant_content,
                role="assistant",
                finish_reason=None,
                usage=None,
            )
            add_chat_message(db, session_id=session_id, role="assistant", content=assistant_content)
            yield build_chat_completion_chunk(
                completion_id=completion_id,
                created=created,
                model=model_label,
                chat_id=chat_id,
                session_id=session_id,
                content=None,
                role="assistant",
                finish_reason="stop",
                usage=None,
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
                yield build_chat_completion_chunk(
                    completion_id=completion_id,
                    created=created,
                    model=model_label,
                    chat_id=chat_id,
                    session_id=session_id,
                    content=piece,
                    role="assistant",
                    finish_reason=None,
                    usage=None,
                )
            assistant_content = "".join(parts)
        except Exception as e:
            tail = f"\n\n【错误】{e!s}"
            assistant_content = "".join(parts) + (tail if parts else f"Exception: {e!s}")
            yield build_chat_completion_chunk(
                completion_id=completion_id,
                created=created,
                model=model_label,
                chat_id=chat_id,
                session_id=session_id,
                content=tail if parts else f"Exception: {e!s}",
                role="assistant",
                finish_reason=None,
                usage=None,
            )
    else:
        assistant_content = f"Echo: {user_content_to_persist} (No model configured)"
        yield build_chat_completion_chunk(
            completion_id=completion_id,
            created=created,
            model=model_label,
            chat_id=chat_id,
            session_id=session_id,
            content=assistant_content,
            role="assistant",
            finish_reason=None,
            usage=None,
        )

    add_chat_message(
        db,
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        citations=turn_citations if turn_citations else None,
    )
    yield build_chat_completion_chunk(
        completion_id=completion_id,
        created=created,
        model=model_label,
        chat_id=chat_id,
        session_id=session_id,
        content=None,
        role="assistant",
        finish_reason="stop",
        usage=estimate_usage(prompt_messages=llm_messages, completion_text=assistant_content),
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
    response_model: str | None = None,
) -> dict[str, Any]:
    session_obj = get_chat_session(
        db, session_id=session_id, user_id=user_id, enterprise_space_id=enterprise_space_id
    )
    if session_obj.conversation_id != chat_id:
        raise AppError(
            status_code=400,
            code="SESSION_CHAT_MISMATCH",
            message="session_id does not belong to the given chat_id",
        )

    add_chat_message(db, session_id=session_id, role="user", content=user_content_to_persist)
    conv = _conversation_row_after_user_message(db, session_obj.conversation_id)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    model_label = response_model or (conv.model_name if conv else None) or "model"

    provider_cfg: AIModelProvider | None = None
    api_model_name = ""
    if conv:
        try:
            provider_cfg, api_model_name = _resolve_chat_llm(
                db, conv=conv, enterprise_space_id=session_obj.enterprise_space_id
            )
            if api_model_name and not response_model:
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
