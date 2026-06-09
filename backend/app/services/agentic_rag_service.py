from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.provider_adapter import get_provider
from app.models.model_management import AIModel, AIModelDefault, AIModelProvider
from app.schemas.agentic_rag import AgenticRAGCompleteResponse, AgenticRAGQueryRequest
from app.services.agentic_rag.chat_runner import _public_state, iter_agentic_graph_events
from app.services.agentic_rag.graph import build_agentic_rag_graph
from app.services.agentic_rag.kb_route_context import build_kb_route_context
from app.services.agentic_rag.state import AgenticRAGState

settings = get_settings()


def _resolve_agentic_llm(
    db: Session,
    *,
    enterprise_space_id: int,
    model_id: int | None,
) -> tuple[AIModelProvider, str]:
    if model_id is not None:
        model = db.execute(
            select(AIModel)
            .options(selectinload(AIModel.provider))
            .where(
                AIModel.id == model_id,
                AIModel.enterprise_space_id == enterprise_space_id,
                AIModel.model_type == "llm",
                AIModel.is_enabled.is_(True),
            )
        ).scalar_one_or_none()
        if model is None or model.provider is None:
            raise AppError(
                status_code=400,
                code="AGENTIC_RAG_MODEL_NOT_FOUND",
                message="Agentic RAG 绑定的模型不存在、未启用或已删除",
            )
        api_name = (model.model_name or model.model_code or "").strip()
        if not api_name:
            raise AppError(
                status_code=500,
                code="AGENTIC_RAG_MODEL_MISCONFIGURED",
                message="Agentic RAG 模型缺少 model_name / model_code",
            )
        return model.provider, api_name

    binding = db.execute(
        select(AIModelDefault)
        .options(selectinload(AIModelDefault.model).selectinload(AIModel.provider))
        .where(
            AIModelDefault.enterprise_space_id == enterprise_space_id,
            AIModelDefault.model_type == "llm",
        )
    ).scalar_one_or_none()
    model = binding.model if binding else None
    if model is None or model.provider is None or not model.is_enabled:
        raise AppError(
            status_code=400,
            code="AGENTIC_RAG_DEFAULT_MODEL_NOT_CONFIGURED",
            message="请先在模型管理中配置默认 LLM，或在请求中指定 model_id",
        )
    api_name = (model.model_name or model.model_code or "").strip()
    if not api_name:
        raise AppError(
            status_code=500,
            code="AGENTIC_RAG_MODEL_MISCONFIGURED",
            message="默认 LLM 缺少 model_name / model_code",
        )
    return model.provider, api_name


def _initial_state(
    db: Session,
    *,
    enterprise_space_id: int,
    payload: AgenticRAGQueryRequest,
) -> tuple[AgenticRAGState, Any]:
    provider_cfg, api_model_name = _resolve_agentic_llm(
        db,
        enterprise_space_id=enterprise_space_id,
        model_id=payload.model_id,
    )
    provider = get_provider(provider_cfg)
    max_iterations = payload.max_iterations or settings.agentic_rag_max_iterations
    min_relevant_docs = payload.min_relevant_docs or settings.agentic_rag_min_relevant_docs
    kb_ids = list(payload.knowledge_base_ids)
    kb_context = build_kb_route_context(
        db,
        enterprise_space_id=enterprise_space_id,
        knowledge_base_ids=kb_ids,
    )
    state: AgenticRAGState = {
        "db": db,
        "enterprise_space_id": enterprise_space_id,
        "knowledge_base_ids": kb_ids,
        "kb_context": kb_context,
        "pre_retrieval_candidates": [],
        "route_pre_retrieve_enabled": settings.agentic_route_pre_retrieve_enabled,
        "question": payload.question.strip(),
        "current_query": payload.question.strip(),
        "trace": [],
        "iterations": 0,
        "max_iterations": max(1, min(5, int(max_iterations))),
        "min_relevant_docs": max(1, min(10, int(min_relevant_docs))),
        "top_k": int(payload.top_k),
        "retrieval_mode": payload.mode,
        "score_threshold": payload.score_threshold,
        "vector_weight": payload.vector_weight,
        "fusion_method": payload.fusion_method,
        "include_image_ocr": payload.include_image_ocr,
        "llm_provider": provider,
        "llm_model_name": api_model_name,
        "temperature": payload.temperature,
        "max_tokens": payload.max_tokens,
        "top_p": payload.top_p,
        "chat_history": [],
    }
    return state, provider


def run_agentic_rag_complete(
    db: Session,
    *,
    enterprise_space_id: int,
    payload: AgenticRAGQueryRequest,
) -> AgenticRAGCompleteResponse:
    if not settings.agentic_rag_enabled:
        raise AppError(status_code=403, code="AGENTIC_RAG_DISABLED", message="Agentic RAG 未启用")
    state, provider = _initial_state(db, enterprise_space_id=enterprise_space_id, payload=payload)
    try:
        graph = build_agentic_rag_graph()
        final_state = graph.invoke(state)
        return AgenticRAGCompleteResponse(**_public_state(final_state))
    finally:
        provider.close()


def iter_agentic_rag_events(
    db: Session,
    *,
    enterprise_space_id: int,
    payload: AgenticRAGQueryRequest,
) -> Iterator[dict[str, Any]]:
    if not settings.agentic_rag_enabled:
        yield {"type": "error", "code": "AGENTIC_RAG_DISABLED", "message": "Agentic RAG 未启用"}
        return

    state, provider = _initial_state(db, enterprise_space_id=enterprise_space_id, payload=payload)
    try:
        for event in iter_agentic_graph_events(state, step_event_type="step_completed"):
            if event.get("type") == "assistant_done":
                yield {"type": "assistant_done", **{k: v for k, v in event.items() if k != "type"}}
            else:
                yield event
    finally:
        provider.close()
