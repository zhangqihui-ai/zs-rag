"""对话（chat）与其下会话（session）的 REST；会话子资源使用固定前缀 `/sessions/` 以免与 `{chat_id}` 混淆。"""

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.enterprise_space_context import CurrentSpace, CurrentUser
from app.schemas.chat import (
    ChatConfigurationUpdate,
    ChatConfigurationResponse,
    ChatConversationCreate,
    ChatConversationResponse,
    ChatConversationUpdate,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
    ChatStreamRequest,
)
from app.services import chat_service

router = APIRouter(tags=["chats"])

_SSE_ITER_DONE = object()

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
    current_space: CurrentSpace,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    chat_service.delete_chat_session(
        db,
        session_id=session_id,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )


@router.get("/sessions/{session_id}/config", response_model=ChatConfigurationResponse)
def get_session_config(
    session_id: str,
    current_space: CurrentSpace,
    current_user: CurrentUser,
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
    session_id: str,
    payload: ChatStreamRequest,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """兼容旧版 SSE：`assistant_delta` / `assistant_done`。"""

    async def event_gen():
        iterator = chat_service.iter_chat_stream_events(
            db,
            session_id=session_id,
            user_id=current_user.id,
            enterprise_space_id=current_space.id,
            user_content=payload.content,
        )
        try:
            while True:
                event = await asyncio.to_thread(next, iterator, _SSE_ITER_DONE)
                if event is _SSE_ITER_DONE:
                    break
                line = json.dumps(event, ensure_ascii=False)
                yield f"data: {line}\n\n".encode("utf-8")
        except Exception as e:
            err = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            yield f"data: {err}\n\n".encode("utf-8")

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- 对话（chat）本体：需注册在 /sessions/... 之后，避免误匹配 ---


@router.post("", response_model=ChatConversationResponse, status_code=status.HTTP_201_CREATED)
def create_chat(
    payload: ChatConversationCreate,
    current_space: CurrentSpace,
    current_user: CurrentUser,
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


@router.get("/{chat_id}/sessions", response_model=list[ChatSessionResponse])
def list_chat_sessions(
    chat_id: ChatId,
    current_space: CurrentSpace,
    current_user: CurrentUser,
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
    current_space: CurrentSpace,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    chat_service.delete_chat_conversation(
        db,
        conversation_id=chat_id,
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )
