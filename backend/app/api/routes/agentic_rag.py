from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.async_sse import _sse_headers, iter_sse_from_sync_iterator
from app.core.enterprise_space_context import CurrentSpace, RequireMembership
from app.db.session import get_db
from app.schemas.agentic_rag import AgenticRAGCompleteResponse, AgenticRAGQueryRequest
from app.services import agentic_rag_service

router = APIRouter(tags=["agentic-rag"])


@router.post("/query")
async def query_agentic_rag_sse(
    request: Request,
    payload: AgenticRAGQueryRequest,
    current_space: CurrentSpace,
    _: RequireMembership,
):
    """Agentic RAG 流式事件：步骤轨迹 + 最终 assistant_done。"""

    enterprise_space_id = current_space.id

    def build_sync_iter(stream_db: Session):
        return agentic_rag_service.iter_agentic_rag_events(
            stream_db,
            enterprise_space_id=enterprise_space_id,
            payload=payload,
        )

    return StreamingResponse(
        iter_sse_from_sync_iterator(request, build_sync_iter),
        media_type="text/event-stream",
        headers=_sse_headers(),
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
