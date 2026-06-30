from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.provider_adapter import _http_error_message, get_provider
from app.models.chat import ChatConversation
from app.services.agentic_rag.graph import build_agentic_rag_graph
from app.services.agentic_rag.kb_route_context import build_kb_route_context
from app.services.agentic_rag.state import AgenticRAGState

settings = get_settings()


def _clamp_agentic_iterations(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = settings.agentic_rag_max_iterations
    return max(1, min(5, value))


def _clamp_agentic_min_relevant(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = settings.agentic_rag_min_relevant_docs
    return max(1, min(10, value))


def build_state_from_conversation(
    db: Session,
    *,
    conv: ChatConversation,
    enterprise_space_id: int,
    user_content: str,
    chat_history: list[dict[str, str]] | None = None,
) -> tuple[AgenticRAGState, Any]:
    from app.services.chat_service import _clamp_agentic_context_user_turns, _llm_sampling_kwargs, _resolve_chat_llm

    provider_cfg, api_model_name = _resolve_chat_llm(db, conv=conv, enterprise_space_id=enterprise_space_id)
    provider = get_provider(provider_cfg)
    sampling = _llm_sampling_kwargs(conv)
    kb_ids = list(conv.knowledge_base_ids or [])
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
        "question": user_content.strip(),
        "current_query": user_content.strip(),
        "chat_history": list(chat_history or []),
        "trace": [],
        "iterations": 0,
        "max_iterations": _clamp_agentic_iterations(getattr(conv, "agentic_max_iterations", None)),
        "min_relevant_docs": _clamp_agentic_min_relevant(getattr(conv, "agentic_min_relevant_docs", None)),
        "context_user_turns": _clamp_agentic_context_user_turns(
            getattr(conv, "agentic_context_user_turns", None)
        ),
        "top_k": int(getattr(conv, "retrieval_top_k", None) or 8),
        "vector_top_k": int(getattr(conv, "vector_retrieval_top_k", None) or 8),
        "lightrag_top_k": int(getattr(conv, "lightrag_retrieval_top_k", None) or 8),
        "retrieval_mode": None,
        "score_threshold": None,
        "vector_weight": None,
        "fusion_method": None,
        "include_image_ocr": None,
        "lightrag_query_mode": str(getattr(conv, "lightrag_query_mode", None) or "mix"),
        "lightrag_chunk_top_k": getattr(conv, "lightrag_chunk_top_k", None),
        "llm_provider": provider,
        "llm_model_name": api_model_name,
        "temperature": sampling.get("temperature"),
        "max_tokens": sampling.get("max_tokens"),
        "top_p": sampling.get("top_p"),
    }
    return state, provider


def _public_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer": str(state.get("answer") or ""),
        "citations": list(state.get("citations") or []),
        "trace": list(state.get("trace") or []),
        "route_decision": state.get("route_decision"),
        "route_reason": state.get("route_reason"),
        "iterations": int(state.get("iterations") or 0),
        "current_query": state.get("current_query"),
    }


def iter_agentic_graph_events(
    state: AgenticRAGState,
    *,
    step_event_type: str = "step_completed",
) -> Iterator[dict[str, Any]]:
    merged: dict[str, Any] = dict(state)
    graph = build_agentic_rag_graph()
    try:
        for update in graph.stream(state):
            if not isinstance(update, dict):
                continue
            for node_name, delta in update.items():
                if isinstance(delta, dict):
                    merged.update(delta)
                trace = list(merged.get("trace") or [])
                latest = trace[-1] if trace else {"step": node_name}
                yield {
                    "type": step_event_type,
                    "step": node_name,
                    "trace": latest,
                    "route_decision": merged.get("route_decision"),
                    "iterations": int(merged.get("iterations") or 0),
                }
                if node_name == "generate":
                    answer = str(merged.get("answer") or "")
                    if answer:
                        yield {"type": "assistant_delta", "content": answer}
        yield {"type": "assistant_done", **_public_state(merged)}
    except httpx.HTTPStatusError as exc:
        yield {"type": "error", "message": _http_error_message(exc)}
    except httpx.RequestError as exc:
        yield {"type": "error", "message": f"LLM 请求失败：{exc}"}
    except Exception as exc:
        yield {"type": "error", "message": str(exc)}


def iter_agentic_chat_turn_events(
    db: Session,
    *,
    conv: ChatConversation,
    enterprise_space_id: int,
    user_content: str,
    chat_history: list[dict[str, str]] | None = None,
) -> Iterator[dict[str, Any]]:
    if not settings.agentic_rag_enabled:
        yield {"type": "error", "code": "AGENTIC_RAG_DISABLED", "message": "Agentic RAG 未启用"}
        return

    state, provider = build_state_from_conversation(
        db,
        conv=conv,
        enterprise_space_id=enterprise_space_id,
        user_content=user_content,
        chat_history=chat_history,
    )
    try:
        yield from iter_agentic_graph_events(state, step_event_type="agent_step")
    finally:
        provider.close()
