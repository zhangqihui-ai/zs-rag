from __future__ import annotations

from typing import Any, Literal, TypedDict


RouteDecision = Literal["retrieve", "direct"]


class AgenticRAGState(TypedDict, total=False):
    """LangGraph 运行态；只存可序列化字段，便于 trace 下发到前端。"""

    db: Any
    enterprise_space_id: int
    knowledge_base_ids: list[int]
    question: str
    current_query: str
    answer: str
    citations: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    graded_docs: list[dict[str, Any]]
    relevant_docs: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    route_decision: RouteDecision
    route_reason: str
    iterations: int
    max_iterations: int
    min_relevant_docs: int
    top_k: int
    vector_top_k: int
    lightrag_top_k: int
    retrieval_mode: str | None
    score_threshold: float | None
    vector_weight: float | None
    fusion_method: str | None
    include_image_ocr: bool | None
    lightrag_query_mode: str | None
    lightrag_chunk_top_k: int | None
    llm_provider: Any
    llm_model_name: str
    temperature: float | None
    max_tokens: int | None
    top_p: float | None
    chat_history: list[dict[str, str]]
    kb_context: str
    pre_retrieval_candidates: list[dict[str, Any]]
    route_pre_retrieve_enabled: bool
    context_user_turns: int
    resolved_query: str
