from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chat import ChatConversation, ChatMessage, ChatSession
from app.models.enterprise_space import EnterpriseSpace, Membership
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseType, KnowledgeChunk, KnowledgeDocument
from app.models.model_management import AIModel, AIModelProvider


def get_space_dashboard_overview(db: Session, *, space: EnterpriseSpace) -> dict:
    space_id = space.id

    kb_base = KnowledgeBase.enterprise_space_id == space_id
    kb_active = kb_base & (KnowledgeBase.status == "active")
    kb_not_deleted = kb_base & (KnowledgeBase.status != "deleted")

    knowledge_total = _scalar(db, select(func.count(KnowledgeBase.id)).where(kb_not_deleted))
    knowledge_active = _scalar(db, select(func.count(KnowledgeBase.id)).where(kb_active))
    knowledge_vector = _scalar(
        db,
        select(func.count(KnowledgeBase.id)).where(
            kb_not_deleted,
            KnowledgeBase.kb_type == KnowledgeBaseType.CLASSIC.value,
        ),
    )
    knowledge_graph = _scalar(
        db,
        select(func.count(KnowledgeBase.id)).where(
            kb_not_deleted,
            KnowledgeBase.kb_type == KnowledgeBaseType.LIGHTRAG.value,
        ),
    )

    doc_base = (
        KnowledgeDocument.enterprise_space_id == space_id,
        KnowledgeDocument.status != "deleted",
    )
    document_total = _scalar(db, select(func.count(KnowledgeDocument.id)).where(*doc_base))
    indexed_document_total = _scalar(
        db,
        select(func.count(KnowledgeDocument.id)).where(
            *doc_base,
            KnowledgeDocument.status.in_(("indexed", "graph_indexed")),
        ),
    )
    storage_bytes = _scalar(
        db,
        select(func.coalesce(func.sum(KnowledgeDocument.file_size), 0)).where(*doc_base),
    )
    chunk_total = _scalar(
        db,
        select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.enterprise_space_id == space_id),
    )

    ready_kb_total = _scalar(
        db,
        select(func.count(func.distinct(KnowledgeDocument.knowledge_base_id))).where(
            *doc_base,
            KnowledgeDocument.status.in_(("indexed", "graph_indexed")),
        ),
    )

    conversation_total = _scalar(
        db,
        select(func.count(ChatConversation.id)).where(ChatConversation.enterprise_space_id == space_id),
    )
    session_total = _scalar(
        db,
        select(func.count(ChatSession.id)).where(ChatSession.enterprise_space_id == space_id),
    )
    message_total = _scalar(
        db,
        select(func.count(ChatMessage.id))
        .select_from(ChatMessage)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.enterprise_space_id == space_id),
    )

    provider_total = _scalar(
        db,
        select(func.count(AIModelProvider.id)).where(AIModelProvider.enterprise_space_id == space_id),
    )
    model_total = _scalar(
        db,
        select(func.count(AIModel.id)).where(AIModel.enterprise_space_id == space_id),
    )
    enabled_model_total = _scalar(
        db,
        select(func.count(AIModel.id)).where(
            AIModel.enterprise_space_id == space_id,
            AIModel.is_enabled.is_(True),
        ),
    )
    llm_total = _scalar(
        db,
        select(func.count(AIModel.id)).where(
            AIModel.enterprise_space_id == space_id,
            AIModel.model_type == "llm",
            AIModel.is_enabled.is_(True),
        ),
    )
    embedding_total = _scalar(
        db,
        select(func.count(AIModel.id)).where(
            AIModel.enterprise_space_id == space_id,
            AIModel.model_type == "embedding",
            AIModel.is_enabled.is_(True),
        ),
    )

    member_total = _scalar(
        db,
        select(func.count(Membership.id)).where(Membership.enterprise_space_id == space_id),
    )

    return {
        "space_id": space_id,
        "space_name": space.name,
        "knowledge": {
            "total": knowledge_total,
            "active": knowledge_active,
            "vector": knowledge_vector,
            "graph": knowledge_graph,
            "document_total": document_total,
            "indexed_document_total": indexed_document_total,
            "chunk_total": chunk_total,
            "storage_bytes": storage_bytes,
        },
        "retrieval": {
            "ready_knowledge_base_total": ready_kb_total,
            "indexed_document_total": indexed_document_total,
            "chunk_total": chunk_total,
        },
        "chat": {
            "conversation_total": conversation_total,
            "session_total": session_total,
            "message_total": message_total,
        },
        "models": {
            "provider_total": provider_total,
            "model_total": model_total,
            "enabled_model_total": enabled_model_total,
            "llm_total": llm_total,
            "embedding_total": embedding_total,
        },
        "users": {
            "member_total": member_total,
        },
    }


def _scalar(db: Session, stmt) -> int:
    value = db.execute(stmt).scalar_one()
    return int(value or 0)
