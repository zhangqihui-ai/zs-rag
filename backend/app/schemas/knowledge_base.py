from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="知识库名称")
    description: str | None = Field(None, max_length=2000, description="知识库描述")
    vector_db_enabled: bool = Field(default=True, description="是否启用向量数据库")
    graph_db_enabled: bool = Field(default=False, description="是否启用图数据库")
    config: dict | None = None


class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    status: str | None = Field(None, pattern="^(active|inactive|deleted)$")
    vector_db_enabled: bool | None = None
    graph_db_enabled: bool | None = None
    config: dict | None = None


class KnowledgeBaseResponse(KnowledgeBaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    enterprise_space_id: int
    status: str
    created_at: datetime
    updated_at: datetime


class MilvusConnectionBase(BaseModel):
    host: str = Field(..., min_length=1, max_length=200, description="Milvus 主机地址")
    port: int = Field(default=19530, ge=1, le=65535, description="Milvus 端口")
    username: str | None = Field(None, max_length=100, description="用户名")
    dimension: int = Field(default=1536, ge=1, description="向量维度")
    metric_type: str = Field(default="COSINE", description="距离度量类型")
    config: dict | None = None


class MilvusConnectionCreate(MilvusConnectionBase):
    password: str | None = Field(None, description="密码")


class MilvusConnectionUpdate(BaseModel):
    host: str | None = Field(None, min_length=1, max_length=200)
    port: int | None = Field(None, ge=1, le=65535)
    password: str | None = Field(None, description="密码")
    username: str | None = Field(None, max_length=100)
    dimension: int | None = Field(None, ge=1)
    metric_type: str | None = Field(None)
    is_active: bool | None = None
    config: dict | None = None


class MilvusConnectionResponse(MilvusConnectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    collection_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


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
