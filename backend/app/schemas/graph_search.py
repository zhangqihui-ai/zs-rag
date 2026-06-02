from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

LightRagQueryMode = Literal["naive", "local", "global", "hybrid", "mix"]


class GraphSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    mode: LightRagQueryMode = Field(default="mix")
    top_k: int = Field(default=5, ge=1, le=50)
    chunk_top_k: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="向量侧召回的文档片段数；为空时沿用 LightRAG 默认（20）。",
    )
    include_references: bool = Field(default=True)


class GraphSearchCitation(BaseModel):
    ref: int
    document_name: str
    document_id: int | None = None
    file_path: str | None = None
    chunk_id: str | None = None
    knowledge_base_id: int


class GraphSearchResponse(BaseModel):
    query: str
    mode: str
    answer_context: str = ""
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[GraphSearchCitation] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None
