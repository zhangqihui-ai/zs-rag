"""对话（chat）与其下会话（session）的 REST；会话子资源使用固定前缀 `/sessions/` 以免与 `{chat_id}` 混淆。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.async_sse import _sse_headers, iter_sse_from_sync_iterator
from app.core.enterprise_space_context import CurrentSpace, CurrentUser, RequireMembership
from app.core.platform_audit_helper import audit_action
from app.db.session import get_db
from app.schemas.chat import (
    ChatConfigurationUpdate,
    ChatConfigurationResponse,
    ChatConversationCreate,
    ChatConversationResponse,
    ChatConversationUpdate,
    ChatEmbedApiKeyCreateBody,
    ChatEmbedApiKeyCreateResponse,
    ChatEmbedApiKeyOut,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
    ChatStreamRequest,
)
from app.services import chat_embed_api_key_service as embed_key_service
from app.services import chat_service
from app.models.chat import ChatConversation

router = APIRouter(tags=["chats"])


def _assert_conversation_owned_embed(
    db: Session,
    conversation_id: str,
    *,
    user_id: int,
    enterprise_space_id: int,
) -> None:
    conv = db.get(ChatConversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    if conv.user_id != user_id or conv.enterprise_space_id != enterprise_space_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权为该对话管理嵌入密钥")


def _embed_keys_response_rows(
    db: Session,
    enterprise_space_id: int,
    conversation_id: str | None,
):
    if conversation_id:
        return embed_key_service.list_active_embed_keys_for_conversation(db, enterprise_space_id, conversation_id)
    return [
        k
        for k in embed_key_service.list_active_embed_keys(db, enterprise_space_id)
        if k.conversation_id is None
    ]

# chat_id 须为 UUID（带连字符）或 32 位十六进制；字面量 "sessions" 不匹配，避免与 /sessions/ 子路径混淆。
# 不使用正则前瞻（pydantic-core 不支持）。
ChatId = Annotated[
    str,
    Path(
        ...,
        min_length=1,
        max_length=36,
        pattern=r"^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32})$",
    ),
]


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
def get_session(
    session_id: str,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    return chat_service.get_chat_session(
        db,
        session_id=session_id,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )


@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
def update_session(
    session_id: str,
    payload: ChatSessionUpdate,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    return chat_service.update_chat_session(
        db,
        session_id=session_id,
        obj_in=payload,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    request: Request,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    chat_service.delete_chat_session(
        db,
        session_id=session_id,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )
    audit_action(
        db,
        request,
        action="chat.session.delete",
        resource_type="chat_session",
        resource_id=session_id,
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
    )
    db.commit()


@router.get("/sessions/{session_id}/config", response_model=ChatConfigurationResponse)
def get_session_config(
    session_id: str,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    return chat_service.get_chat_configuration(
        db,
        session_id=session_id,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )


@router.put("/sessions/{session_id}/config", response_model=ChatConfigurationResponse)
def update_session_config(
    session_id: str,
    payload: ChatConfigurationUpdate,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    return chat_service.update_chat_configuration(
        db,
        session_id=session_id,
        obj_in=payload,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def get_session_messages(
    session_id: str,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return chat_service.get_chat_messages(
        db,
        session_id=session_id,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
        skip=skip,
        limit=limit,
    )


@router.post("/sessions/{session_id}/stream")
async def session_stream_sse(
    request: Request,
    session_id: str,
    payload: ChatStreamRequest,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    """兼容旧版 SSE：`assistant_delta` / `assistant_done`。"""

    user_id = current_user.id
    enterprise_space_id = current_space.id

    def build_sync_iter(stream_db: Session):
        return chat_service.iter_chat_stream_events(
            stream_db,
            session_id=session_id,
            user_id=user_id,
            enterprise_space_id=enterprise_space_id,
            user_content=payload.content,
        )

    return StreamingResponse(
        iter_sse_from_sync_iterator(request, build_sync_iter),
        media_type="text/event-stream",
        headers=_sse_headers(),
    )


@router.post("/sessions/{session_id}/complete")
def session_complete_blocking(
    session_id: str,
    payload: ChatStreamRequest,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    """会话级非流式：返回 assistant_done 形态 JSON（含 session_id、content、citations）。"""
    return chat_service.complete_chat_turn_blocking(
        db,
        session_id=session_id,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
        user_content=payload.content,
    )


@router.post("/{chat_id}/stream")
async def chat_conversation_stream_sse(
    request: Request,
    chat_id: ChatId,
    payload: ChatStreamRequest,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    """对话级 SSE：自动新建会话；assistant_done 事件含 session_id，供后续会话级接口复用。"""
    session = chat_service.ensure_session_for_completion(
        db,
        chat_id=chat_id,
        session_id=None,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )
    bound_session_id = session.id
    user_id = current_user.id
    enterprise_space_id = current_space.id

    def build_sync_iter(stream_db: Session):
        return chat_service.iter_chat_stream_events(
            stream_db,
            session_id=bound_session_id,
            user_id=user_id,
            enterprise_space_id=enterprise_space_id,
            user_content=payload.content,
        )

    return StreamingResponse(
        iter_sse_from_sync_iterator(request, build_sync_iter),
        media_type="text/event-stream",
        headers=_sse_headers(),
    )


# --- 对话（chat）本体：需注册在 /sessions/... 之后，避免误匹配 ---


@router.post("", response_model=ChatConversationResponse, status_code=status.HTTP_201_CREATED)
def create_chat(
    payload: ChatConversationCreate,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    return chat_service.create_chat_conversation(
        db,
        obj_in=payload,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )


@router.get("", response_model=list[ChatConversationResponse])
def list_chats(
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return chat_service.list_chat_conversations(
        db,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
        skip=skip,
        limit=limit,
    )


@router.post("/embed-api-keys", response_model=ChatEmbedApiKeyCreateResponse)
def create_or_ensure_embed_api_key(
    payload: ChatEmbedApiKeyCreateBody,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    """嵌入分享：按对话签发密钥；打开面板时可立即获得可复制明文。"""
    cid = (payload.conversation_id or "").strip() or None
    if cid is not None:
        _assert_conversation_owned_embed(
            db, cid, user_id=current_user.id, enterprise_space_id=current_space.id
        )

    if payload.regenerate:
        if cid:
            embed_key_service.revoke_active_embed_keys_for_conversation(db, current_space.id, cid)
        else:
            embed_key_service.revoke_all_active_for_space(db, current_space.id)
        db.commit()
        plain, row = embed_key_service.create_embed_api_key_row(
            db,
            enterprise_space_id=current_space.id,
            created_by_user_id=current_user.id,
            conversation_id=cid,
        )
        db.commit()
        db.refresh(row)
        rows = _embed_keys_response_rows(db, current_space.id, cid)
        return ChatEmbedApiKeyCreateResponse(
            created=True,
            api_key=plain,
            keys=[ChatEmbedApiKeyOut.model_validate(k) for k in rows],
            message=None,
        )

    if cid and payload.issue_new_for_share:
        embed_key_service.revoke_active_embed_keys_for_conversation(db, current_space.id, cid)
        db.commit()
        plain, row = embed_key_service.create_embed_api_key_row(
            db,
            enterprise_space_id=current_space.id,
            created_by_user_id=current_user.id,
            conversation_id=cid,
        )
        db.commit()
        db.refresh(row)
        rows = _embed_keys_response_rows(db, current_space.id, cid)
        return ChatEmbedApiKeyCreateResponse(
            created=True,
            api_key=plain,
            keys=[ChatEmbedApiKeyOut.model_validate(k) for k in rows],
            message=None,
        )

    if cid:
        existing = embed_key_service.list_active_embed_keys_for_conversation(db, current_space.id, cid)
        if existing:
            return ChatEmbedApiKeyCreateResponse(
                created=False,
                api_key=None,
                keys=[ChatEmbedApiKeyOut.model_validate(k) for k in existing],
                message=None,
            )
        plain, row = embed_key_service.create_embed_api_key_row(
            db,
            enterprise_space_id=current_space.id,
            created_by_user_id=current_user.id,
            conversation_id=cid,
        )
        db.commit()
        db.refresh(row)
        rows = _embed_keys_response_rows(db, current_space.id, cid)
        return ChatEmbedApiKeyCreateResponse(
            created=True,
            api_key=plain,
            keys=[ChatEmbedApiKeyOut.model_validate(k) for k in rows],
            message=None,
        )

    all_active = embed_key_service.list_active_embed_keys(db, current_space.id)
    active_global = [k for k in all_active if k.conversation_id is None]
    if active_global:
        return ChatEmbedApiKeyCreateResponse(
            created=False,
            api_key=None,
            keys=[ChatEmbedApiKeyOut.model_validate(k) for k in active_global],
            message=None,
        )

    plain, row = embed_key_service.create_embed_api_key_row(
        db,
        enterprise_space_id=current_space.id,
        created_by_user_id=current_user.id,
        conversation_id=None,
    )
    db.commit()
    db.refresh(row)
    rows = _embed_keys_response_rows(db, current_space.id, None)
    return ChatEmbedApiKeyCreateResponse(
        created=True,
        api_key=plain,
        keys=[ChatEmbedApiKeyOut.model_validate(k) for k in rows],
        message=None,
    )


@router.get("/embed-api-keys", response_model=list[ChatEmbedApiKeyOut])
def list_embed_api_keys(
    current_space: CurrentSpace,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    active = embed_key_service.list_active_embed_keys(db, current_space.id)
    return [ChatEmbedApiKeyOut.model_validate(k) for k in active]


@router.delete("/embed-api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_embed_api_key(
    key_id: int,
    current_space: CurrentSpace,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    ok = embed_key_service.revoke_embed_key_by_id(db, key_id=key_id, enterprise_space_id=current_space.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="密钥不存在")
    db.commit()


@router.get("/{chat_id}/sessions", response_model=list[ChatSessionResponse])
def list_chat_sessions(
    chat_id: ChatId,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    return chat_service.list_sessions_for_conversation(
        db,
        conversation_id=chat_id,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )


@router.post(
    "/{chat_id}/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_chat_session(
    chat_id: ChatId,
    payload: ChatSessionCreate,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    return chat_service.create_session_in_conversation(
        db,
        conversation_id=chat_id,
        obj_in=payload,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )


@router.get("/{chat_id}", response_model=ChatConversationResponse)
def get_chat(
    chat_id: ChatId,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    return chat_service.get_chat_conversation(
        db,
        conversation_id=chat_id,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )


@router.put("/{chat_id}", response_model=ChatConversationResponse)
def update_chat(
    chat_id: ChatId,
    payload: ChatConversationUpdate,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    return chat_service.update_chat_conversation(
        db,
        conversation_id=chat_id,
        obj_in=payload,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(
    chat_id: ChatId,
    request: Request,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
):
    chat_service.delete_chat_conversation(
        db,
        conversation_id=chat_id,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )
    audit_action(
        db,
        request,
        action="chat.conversation.delete",
        resource_type="chat_conversation",
        resource_id=chat_id,
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
    )
    db.commit()
