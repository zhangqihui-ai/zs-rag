from __future__ import annotations

from pydantic import BaseModel, Field


class SearchCitationResponse(BaseModel):
    document_name: str
    page_no: int | None = None
    chunk_index: int
    heading_path: str | None = None
    location_label: str | None = None
    block: str | None = None


class SearchResultItem(BaseModel):
    chunk_id: int
    chunk_uid: str
    document_id: int
    document_name: str
    chunk_index: int
    content: str
    content_preview: str | None = None
    char_count: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    heading_path: str | None = None
    enrichment_keywords: list[str] = Field(default_factory=list)
    enrichment_questions: list[str] = Field(default_factory=list)
    score: float
    vector_score: float | None = None
    keyword_score: float | None = None
    metadata: dict | None = None
    citation: SearchCitationResponse
    knowledge_base_id: int | None = None
    knowledge_base_name: str | None = None


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    mode: str | None = Field(default=None, pattern="^(vector|keyword|hybrid)$")
    top_k: int | None = Field(default=None, ge=1, le=50)
    score_threshold: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "相似度下限（0~1）。混合模式：先对向量/全文各路候选分别归一化并按阈值过滤，"
            "再按权重融合；未开启时混合检索仍会用内置相对阈值预过滤弱命中。"
            "单路模式：对返回分数直接过滤（向量原始分通常远小于 1，建议仅混合模式使用）。"
        ),
    )
    vector_weight: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="混合检索时向量分支权重 w，全文关键词权重为 1-w；缺省为 0.3",
    )
    fusion_method: str | None = Field(
        default=None,
        pattern="^(weighted|rrf)$",
        description=(
            "混合检索通道融合方式：weighted=归一化加权求和（默认）；"
            "rrf=加权倒数排名融合（按名次融合，跨量纲更稳）。"
            "缺省读取知识库 config.retrieval.fusion_method。"
        ),
    )
    include_image_ocr: bool | None = Field(
        default=None,
        description=(
            "是否召回独立 block=image 的截图 OCR 切片。"
            "缺省时读取知识库 config.retrieval.include_image_ocr（默认 false）；"
            "UI/截图类问句可在 auto_image_ocr_on_ui_query 开启时自动放宽。"
        ),
    )
    document_ids: list[int] | None = None


class KnowledgeSearchResponse(BaseModel):
    query: str
    mode: str
    total: int
    results: list[SearchResultItem]


class MultiKnowledgeSearchRequest(KnowledgeSearchRequest):
    knowledge_base_ids: list[int] = Field(..., min_length=1, max_length=24, description="参与检索的知识库 ID，顺序保留")


class MultiKnowledgeSearchResponse(BaseModel):
    query: str
    mode: str
    knowledge_base_ids: list[int]
    total: int
    results: list[SearchResultItem]
