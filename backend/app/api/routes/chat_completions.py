"""OpenAI 形态的对话补全：POST /api/v1/chat/completions"""

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.enterprise_space_context import CurrentSpace, CurrentUser
from app.core.errors import AppError
from app.schemas.chat import ChatCompletionsRequest
from app.services import chat_service

router = APIRouter(tags=["chat-completions"])

_SSE_ITER_DONE = object()


@router.post("/completions")
async def chat_completions(
    payload: ChatCompletionsRequest,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """
    - 仅 `chat_id`：按该对话配置自动新建会话并发话。
    - `chat_id` + `session_id`：校验会话属于该对话后继续多轮。
    - `stream=true`：SSE，帧格式对齐 OpenAI `chat.completion.chunk`（并附带 `chat_id`、`session_id`）。
    - `stream=false`：返回 OpenAI `chat.completion` 形态 JSON（并附带 `chat_id`、`session_id`）。
    """
    chat_id = payload.chat_id
    session = chat_service.ensure_session_for_completion(
        db,
        chat_id=chat_id,
        session_id=payload.session_id,
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

    if payload.stream:

        async def event_gen():
            iterator = chat_service.iter_openai_completion_events(
                db,
                session_id=session_id,
                chat_id=chat_id,
                user_id=current_user.id,
                enterprise_space_id=current_space.id,
                user_content_to_persist=user_text,
                llm_messages=llm_messages,
                turn_citations=turn_citations,
            )
            try:
                while True:
                    event = await asyncio.to_thread(next, iterator, _SSE_ITER_DONE)
                    if event is _SSE_ITER_DONE:
                        break
                    line = json.dumps(event, ensure_ascii=False)
                    yield f"data: {line}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"
            except Exception as e:
                err = {"error": {"message": str(e), "type": "internal_error"}}
                yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n".encode("utf-8")

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
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(500, "COMPLETION_FAILED", str(e)) from e

    completion_id = result["completion_id"]
    created = int(result["created"])
    model = str(result["model"])
    assistant_text = str(result["content"])
    return JSONResponse(
        {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": assistant_text},
                    "finish_reason": "stop",
                }
            ],
            "chat_id": chat_id,
            "session_id": session_id,
        }
    )
