from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


RetrievalMode = Literal["hybrid", "vector", "keyword"]
KnowledgeBaseStatus = Literal["active", "inactive", "deleted"]
KnowledgeBaseType = Literal["classic", "lightrag"]


class KnowledgeBaseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="知识库名称")
    description: str | None = Field(None, max_length=2000, description="知识库描述")
    kb_type: KnowledgeBaseType = Field(default="classic", description="知识库类型：classic 经典库 / lightrag 图库")
    vector_db_enabled: bool = Field(default=True, description="是否启用向量数据库")
    graph_db_enabled: bool = Field(default=False, description="是否启用图数据库")
    embedding_model_id: int | None = Field(default=None, description="知识库级别 embedding 模型")
    default_chunk_size: int = Field(default=512, ge=100, le=5000, description="默认分块大小（字符）")
    default_chunk_overlap: int = Field(default=50, ge=0, le=1000, description="默认重叠大小（字符）")
    default_retrieval_mode: RetrievalMode = Field(default="hybrid", description="默认检索模式")
    default_top_k: int = Field(default=5, ge=1, le=50, description="默认返回条数")
    default_score_threshold: float | None = Field(
        default=0.5, ge=0, le=1, description="默认分数阈值（混合检索分路过滤）"
    )
    config: dict | None = None

    @model_validator(mode="after")
    def validate_chunking(self) -> "KnowledgeBaseBase":
        if self.default_chunk_overlap >= self.default_chunk_size:
            raise ValueError("default_chunk_overlap 必须小于 default_chunk_size")
        return self


class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    status: KnowledgeBaseStatus | None = None
    kb_type: KnowledgeBaseType | None = None
    vector_db_enabled: bool | None = None
    graph_db_enabled: bool | None = None
    embedding_model_id: int | None = None
    default_chunk_size: int | None = Field(None, ge=100, le=5000)
    default_chunk_overlap: int | None = Field(None, ge=0, le=1000)
    default_retrieval_mode: RetrievalMode | None = None
    default_top_k: int | None = Field(None, ge=1, le=50)
    default_score_threshold: float | None = Field(None, ge=0, le=1)
    config: dict | None = None

    @model_validator(mode="after")
    def validate_chunking(self) -> "KnowledgeBaseUpdate":
        if (
            self.default_chunk_size is not None
            and self.default_chunk_overlap is not None
            and self.default_chunk_overlap >= self.default_chunk_size
        ):
            raise ValueError("default_chunk_overlap 必须小于 default_chunk_size")
        return self


class KnowledgeBaseResponse(KnowledgeBaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    enterprise_space_id: int
    status: str
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseStatsResponse(BaseModel):
    knowledge_base_id: int
    document_total: int
    indexed_document_total: int
    chunk_total: int
    failed_document_total: int


class KnowledgeBasePurgeRequest(BaseModel):
    """彻底删除知识库：需要二次确认（输入名称）。"""

    confirm_name: str = Field(..., min_length=1, max_length=200, description="输入知识库名称以确认")
    confirm: bool = Field(default=False, description="必须为 true 才会执行彻底删除")


class Neo4jConnectionBase(BaseModel):
    uri: str = Field(..., min_length=1, max_length=500, description="Neo4j URI")
    username: str = Field(..., min_length=1, max_length=100, description="用户名")
    database: str | None = Field(None, max_length=100, description="数据库名")
    config: dict | None = None


class Neo4jConnectionCreate(Neo4jConnectionBase):
    password: str | None = Field(None, description="密码")


class Neo4jConnectionUpdate(BaseModel):
    uri: str | None = Field(None, min_length=1, max_length=500)
    username: str | None = Field(None, min_length=1, max_length=100)
    password: str | None = Field(None, description="密码")
    database: str | None = Field(None, max_length=100)
    is_active: bool | None = None
    config: dict | None = None


class Neo4jConnectionResponse(Neo4jConnectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    response_time_ms: float | None = None
