"""OpenAI 形态的对话补全：兼容官方请求/响应字段。"""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.routes.chats import ChatId
from app.core.enterprise_space_context import CurrentSpace, CurrentUser
from app.core.errors import AppError
from app.core.openai_compat import (
    build_chat_completion_response,
    resolve_response_model_name,
    resolve_session_id_from_body,
)
from app.db.session import SessionLocal, get_db
from app.models.chat import ChatConversation
from app.schemas.chat import ChatCompletionsRequest
from app.services import chat_service

router = APIRouter(tags=["chat-completions"])
openai_router = APIRouter(tags=["openai-chat-completions"])

async def _execute_chat_completion(
    *,
    payload: ChatCompletionsRequest,
    chat_id: str,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    db: Session,
):
    session = chat_service.ensure_session_for_completion(
        db,
        chat_id=chat_id,
        session_id=resolve_session_id_from_body(payload),
        user_id=current_user.id,
        enterprise_space_id=current_space.id,
    )
    llm_messages, user_text, turn_citations = chat_service.build_completion_messages(
        db,
        session=session,
        request_messages=payload.messages,
        question=payload.question,
    )
    session_id = session.id
    conv = db.get(ChatConversation, session.conversation_id)
    response_model = resolve_response_model_name(
        payload.model,
        conv.model_name if conv else None,
    )

    # 流式响应在请求返回后才消费生成器，须用独立 DB 会话并提前取出标量，避免 DetachedInstanceError
    user_id = current_user.id
    enterprise_space_id = current_space.id

    if payload.stream:

        async def event_gen():
            stream_db = SessionLocal()
            try:
                iterator = chat_service.iter_openai_completion_events(
                    stream_db,
                    session_id=session_id,
                    chat_id=chat_id,
                    user_id=user_id,
                    enterprise_space_id=enterprise_space_id,
                    user_content_to_persist=user_text,
                    llm_messages=llm_messages,
                    turn_citations=turn_citations,
                    response_model=response_model,
                )
                for event in iterator:
                    line = json.dumps(event, ensure_ascii=False)
                    yield f"data: {line}\n\n".encode("utf-8")
                    await asyncio.sleep(0)
                yield b"data: [DONE]\n\n"
            except AppError as e:
                err = {"error": {"message": e.message, "type": "invalid_request_error", "code": e.code}}
                yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n".encode("utf-8")
            except Exception as e:
                err = {"error": {"message": str(e), "type": "internal_error"}}
                yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n".encode("utf-8")
            finally:
                stream_db.close()

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        result = chat_service.run_chat_completion_blocking(
            db,
            session_id=session_id,
            chat_id=chat_id,
            user_id=current_user.id,
            enterprise_space_id=current_space.id,
            user_content_to_persist=user_text,
            llm_messages=llm_messages,
            turn_citations=turn_citations,
            response_model=response_model,
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(status_code=500, code="COMPLETION_FAILED", message=str(e)) from e

    body = build_chat_completion_response(
        completion_id=str(result["completion_id"]),
        created=int(result["created"]),
        model=str(result["model"]),
        assistant_content=str(result["content"]),
        prompt_messages=llm_messages,
        chat_id=chat_id,
        session_id=session_id,
    )
    return JSONResponse(body)


@router.post("/completions")
async def chat_completions_legacy(
    payload: ChatCompletionsRequest,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """
    兼容旧路径：`POST /api/v1/chat/completions`，请求体须含 `chat_id`。

    请求/响应字段对齐 OpenAI Chat Completions；扩展字段 `chat_id`、`session_id`（或 `extra_body.session_id`）。
    """
    if not (payload.chat_id or "").strip():
        raise AppError(status_code=400, code="CHAT_ID_REQUIRED", message="chat_id is required in request body")
    return await _execute_chat_completion(
        payload=payload,
        chat_id=str(payload.chat_id).strip(),
        current_space=current_space,
        current_user=current_user,
        db=db,
    )


@openai_router.post("/{chat_id}/chat/completions")
async def openai_chat_completions(
    chat_id: ChatId,
    payload: ChatCompletionsRequest,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """
    OpenAI 风格路径：`POST /api/v1/openai/{chat_id}/chat/completions`。

    请求体与 OpenAI 一致（`model`、`messages`、`stream` 等）；`chat_id` 由 URL 提供。
    扩展：`session_id` 或 `extra_body.session_id` 用于多轮会话。
    """
    return await _execute_chat_completion(
        payload=payload,
        chat_id=chat_id,
        current_space=current_space,
        current_user=current_user,
        db=db,
    )
