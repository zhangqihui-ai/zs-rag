from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RagBenchmarkItemCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    expected_answer: str | None = Field(default=None, max_length=8000)
    sort_order: int = 0


class RagBenchmarkCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    knowledge_base_ids: list[int] = Field(..., min_length=1, max_length=24)
    items: list[RagBenchmarkItemCreate] = Field(default_factory=list)


class RagBenchmarkItemResponse(BaseModel):
    id: int
    question: str
    expected_answer: str | None
    sort_order: int

    model_config = {"from_attributes": True}


class RagBenchmarkResponse(BaseModel):
    id: int
    enterprise_space_id: int
    name: str
    description: str | None
    knowledge_base_ids: list[int]
    created_by_user_id: int | None
    created_at: datetime
    updated_at: datetime
    items: list[RagBenchmarkItemResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class RagEvaluationRunRequest(BaseModel):
    retrieval_config: dict | None = None


class RagAgenticComparisonRequest(BaseModel):
    retrieval_config: dict | None = None
    agentic_config: dict | None = None


class RagAgenticComparisonItem(BaseModel):
    question: str
    baseline_hit: bool
    agentic_hit: bool
    baseline_top_score: float | None = None
    baseline_total: int = 0
    agentic_citation_count: int = 0
    agentic_iterations: int = 0
    agentic_route_decision: str | None = None
    agentic_trace: list[dict] = Field(default_factory=list)


class RagAgenticComparisonResponse(BaseModel):
    benchmark_id: int
    total: int
    baseline_hits: int
    agentic_hits: int
    baseline_hit_rate: float
    agentic_hit_rate: float
    avg_agentic_iterations: float
    items: list[RagAgenticComparisonItem] = Field(default_factory=list)


class RagEvaluationResultResponse(BaseModel):
    id: int
    benchmark_item_id: int
    question: str
    hit: bool
    top_score: float | None
    retrieved_chunk_ids: list[int]
    detail: dict | None

    model_config = {"from_attributes": True}


class RagEvaluationRunResponse(BaseModel):
    id: int
    benchmark_id: int
    enterprise_space_id: int
    status: str
    retrieval_config: dict | None
    started_by_user_id: int | None
    summary: dict | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    results: list[RagEvaluationResultResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
