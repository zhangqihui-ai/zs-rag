from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.enterprise_space_context import CurrentSpace, RequireMembership
from app.db.session import SessionLocal, get_db
from app.schemas.agentic_rag import AgenticRAGCompleteResponse, AgenticRAGQueryRequest
from app.services import agentic_rag_service

router = APIRouter(tags=["agentic-rag"])


@router.post("/query")
async def query_agentic_rag_sse(
    payload: AgenticRAGQueryRequest,
    current_space: CurrentSpace,
    _: RequireMembership,
):
    """Agentic RAG 流式事件：步骤轨迹 + 最终 assistant_done。"""

    enterprise_space_id = current_space.id

    async def event_gen():
        stream_db = SessionLocal()
        try:
            for event in agentic_rag_service.iter_agentic_rag_events(
                stream_db,
                enterprise_space_id=enterprise_space_id,
                payload=payload,
            ):
                line = json.dumps(event, ensure_ascii=False)
                yield f"data: {line}\n\n".encode("utf-8")
                await asyncio.sleep(0)
        except Exception as exc:
            err = json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
            yield f"data: {err}\n\n".encode("utf-8")
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


@router.post("/query/complete", response_model=AgenticRAGCompleteResponse)
def query_agentic_rag_complete(
    payload: AgenticRAGQueryRequest,
    current_space: CurrentSpace,
    _: RequireMembership,
    db: Session = Depends(get_db),
) -> AgenticRAGCompleteResponse:
    """Agentic RAG 非流式执行，返回最终答案、引用与决策轨迹。"""
    return agentic_rag_service.run_agentic_rag_complete(
        db,
        enterprise_space_id=current_space.id,
        payload=payload,
    )
