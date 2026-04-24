from __future__ import annotations

from pydantic import BaseModel, Field


class SearchCitationResponse(BaseModel):
    document_name: str
    page_no: int | None = None
    chunk_index: int


class SearchResultItem(BaseModel):
    chunk_id: int
    chunk_uid: str
    document_id: int
    document_name: str
    chunk_index: int
    content: str
    score: float
    vector_score: float | None = None
    keyword_score: float | None = None
    metadata: dict | None = None
    citation: SearchCitationResponse


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    mode: str | None = Field(default=None, pattern="^(vector|keyword|hybrid)$")
    top_k: int | None = Field(default=None, ge=1, le=50)
    score_threshold: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="相似度下限（0~1）；混合模式下对融合后的 score 过滤，关键词/向量模式对各自 score 过滤",
    )
    vector_weight: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="混合检索时向量分支权重 w，全文关键词权重为 1-w；缺省为 0.5",
    )
    document_ids: list[int] | None = None


class KnowledgeSearchResponse(BaseModel):
    query: str
    mode: str
    total: int
    results: list[SearchResultItem]
