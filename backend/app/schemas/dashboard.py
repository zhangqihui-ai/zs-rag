from datetime import datetime

from pydantic import BaseModel, Field


class DashboardKnowledgeStats(BaseModel):
    total: int = 0
    active: int = 0
    vector: int = 0
    graph: int = 0
    document_total: int = 0
    indexed_document_total: int = 0
    chunk_total: int = 0
    storage_bytes: int = 0


class DashboardRetrievalStats(BaseModel):
    ready_knowledge_base_total: int = 0
    indexed_document_total: int = 0
    chunk_total: int = 0


class DashboardChatStats(BaseModel):
    conversation_total: int = 0
    session_total: int = 0
    message_total: int = 0
    agentic_conversation_total: int = 0
    classic_conversation_total: int = 0


class DashboardModelStats(BaseModel):
    provider_total: int = 0
    model_total: int = 0
    enabled_model_total: int = 0
    llm_total: int = 0
    embedding_total: int = 0


class DashboardUserStats(BaseModel):
    member_total: int = 0


class DashboardKbUsageItem(BaseModel):
    kb_id: int
    kb_name: str
    conversation_bind_count: int = 0
    recall_count: int = 0


class DashboardFileExtItem(BaseModel):
    file_ext: str
    count: int = 0


class DashboardKnowledgeUsageStats(BaseModel):
    top_knowledge_bases: list[DashboardKbUsageItem] = Field(default_factory=list)
    file_ext_distribution: list[DashboardFileExtItem] = Field(default_factory=list)


class DashboardDocumentPipelineStats(BaseModel):
    parsing: int = 0
    indexed: int = 0
    failed: int = 0


class DashboardAuditItem(BaseModel):
    id: int
    action: str
    resource_type: str
    resource_id: str | None = None
    username: str | None = None
    message: str | None = None
    created_at: datetime


class DashboardOverviewResponse(BaseModel):
    space_id: int
    space_name: str
    knowledge: DashboardKnowledgeStats
    retrieval: DashboardRetrievalStats
    chat: DashboardChatStats
    models: DashboardModelStats
    users: DashboardUserStats = Field(default_factory=DashboardUserStats)
    knowledge_usage: DashboardKnowledgeUsageStats = Field(default_factory=DashboardKnowledgeUsageStats)
    document_pipeline: DashboardDocumentPipelineStats = Field(default_factory=DashboardDocumentPipelineStats)
    recent_audit: list[DashboardAuditItem] = Field(default_factory=list)


class DashboardUsagePoint(BaseModel):
    t: str
    v: int = 0


class DashboardUsageSeries(BaseModel):
    key: str
    label: str
    points: list[DashboardUsagePoint] = Field(default_factory=list)


class DashboardUsageResponse(BaseModel):
    space_id: int
    space_name: str
    range: str
    metric: str
    series: list[DashboardUsageSeries] = Field(default_factory=list)
    total: int = 0


class DashboardChatTopItem(BaseModel):
    conversation_id: str
    title: str
    session_count: int = 0
    message_count: int = 0


class DashboardChatTopResponse(BaseModel):
    space_id: int
    space_name: str
    range: str
    items: list[DashboardChatTopItem] = Field(default_factory=list)
