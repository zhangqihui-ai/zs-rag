from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.knowledge_retrieval_defaults import DEFAULT_TOP_K


class AgenticRAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000, description="用户问题")
    knowledge_base_ids: list[int] = Field(..., min_length=1, max_length=24, description="参与检索的知识库 ID")
    model_id: int | None = Field(default=None, description="可选：指定 Agentic RAG 使用的 LLM 模型")
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=50)
    mode: str | None = Field(default=None, pattern="^(vector|keyword|hybrid)$")
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    vector_weight: float | None = Field(default=None, ge=0, le=1)
    fusion_method: str | None = Field(default=None, pattern="^(weighted|rrf)$")
    include_image_ocr: bool | None = None
    max_iterations: int | None = Field(default=None, ge=1, le=5)
    min_relevant_docs: int | None = Field(default=None, ge=1, le=10)
    context_user_turns: int | None = Field(default=None, ge=1, le=10)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)


class AgenticRAGTraceEvent(BaseModel):
    step: str
    elapsed_ms: float | None = None
    decision: str | None = None
    reason: str | None = None
    query: str | None = None
    total: int | None = None
    iteration: int | None = None
    relevant_count: int | None = None
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    citation_count: int | None = None
    answer_chars: int | None = None


class AgenticRAGCompleteResponse(BaseModel):
    answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    route_decision: str | None = None
    route_reason: str | None = None
    iterations: int = 0
    current_query: str | None = None
