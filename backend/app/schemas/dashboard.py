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


class DashboardModelStats(BaseModel):
    provider_total: int = 0
    model_total: int = 0
    enabled_model_total: int = 0
    llm_total: int = 0
    embedding_total: int = 0


class DashboardUserStats(BaseModel):
    member_total: int = 0


class DashboardOverviewResponse(BaseModel):
    space_id: int
    space_name: str
    knowledge: DashboardKnowledgeStats
    retrieval: DashboardRetrievalStats
    chat: DashboardChatStats
    models: DashboardModelStats
    users: DashboardUserStats = Field(default_factory=DashboardUserStats)
