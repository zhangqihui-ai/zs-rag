from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chat import ChatConversation, ChatMessage, ChatSession
from app.models.enterprise_space import EnterpriseSpace, Membership
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseType, KnowledgeChunk, KnowledgeDocument
from app.models.model_management import AIModel, AIModelProvider
from app.services.platform_audit_service import list_platform_audit_events


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
    agentic_conversation_total = _scalar(
        db,
        select(func.count(ChatConversation.id)).where(
            ChatConversation.enterprise_space_id == space_id,
            ChatConversation.rag_mode == "agentic",
        ),
    )
    classic_conversation_total = max(0, conversation_total - agentic_conversation_total)
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

    knowledge_usage = _aggregate_knowledge_usage(db, space_id)
    document_pipeline = _aggregate_document_pipeline(db, space_id)
    recent_audit = _recent_audit_events(db, space_id)

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
            "agentic_conversation_total": agentic_conversation_total,
            "classic_conversation_total": classic_conversation_total,
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
        "knowledge_usage": knowledge_usage,
        "document_pipeline": document_pipeline,
        "recent_audit": recent_audit,
    }


def _aggregate_knowledge_usage(db: Session, space_id: int) -> dict[str, Any]:
    bind_counts: dict[int, int] = defaultdict(int)
    conv_rows = db.execute(
        select(ChatConversation.knowledge_base_ids).where(
            ChatConversation.enterprise_space_id == space_id,
        )
    ).scalars().all()
    for kb_ids in conv_rows:
        if not kb_ids:
            continue
        for raw_id in kb_ids:
            try:
                bind_counts[int(raw_id)] += 1
            except (TypeError, ValueError):
                continue

    recall_counts: dict[int, int] = defaultdict(int)
    citation_rows = db.execute(
        select(ChatMessage.citations)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(
            ChatSession.enterprise_space_id == space_id,
            ChatMessage.role == "assistant",
            ChatMessage.citations.isnot(None),
        )
    ).scalars().all()
    for citations in citation_rows:
        if not isinstance(citations, list):
            continue
        for item in citations:
            if not isinstance(item, dict):
                continue
            kb_id = item.get("knowledge_base_id")
            if kb_id is None:
                continue
            try:
                recall_counts[int(kb_id)] += 1
            except (TypeError, ValueError):
                continue

    candidate_ids = set(bind_counts) | set(recall_counts)
    name_map: dict[int, str] = {}
    if candidate_ids:
        kb_name_rows = db.execute(
            select(KnowledgeBase.id, KnowledgeBase.name).where(
                KnowledgeBase.enterprise_space_id == space_id,
                KnowledgeBase.id.in_(candidate_ids),
                KnowledgeBase.status != "deleted",
            )
        ).all()
        name_map = {int(row[0]): str(row[1]) for row in kb_name_rows}

    top_items: list[dict[str, Any]] = []
    for kb_id in candidate_ids:
        name = name_map.get(kb_id)
        if not name:
            continue
        top_items.append(
            {
                "kb_id": kb_id,
                "kb_name": name,
                "conversation_bind_count": bind_counts.get(kb_id, 0),
                "recall_count": recall_counts.get(kb_id, 0),
            }
        )
    top_items.sort(key=lambda x: (x["recall_count"], x["conversation_bind_count"]), reverse=True)
    top_items = top_items[:5]

    ext_rows = db.execute(
        select(KnowledgeDocument.file_ext, func.count(KnowledgeDocument.id))
        .where(
            KnowledgeDocument.enterprise_space_id == space_id,
            KnowledgeDocument.status != "deleted",
        )
        .group_by(KnowledgeDocument.file_ext)
        .order_by(func.count(KnowledgeDocument.id).desc())
    ).all()
    file_ext_distribution = [
        {
            "file_ext": (row[0] or "unknown").lower().lstrip("."),
            "count": int(row[1] or 0),
        }
        for row in ext_rows
    ]

    return {
        "top_knowledge_bases": top_items,
        "file_ext_distribution": file_ext_distribution,
    }


def _aggregate_document_pipeline(db: Session, space_id: int) -> dict[str, int]:
    base = (
        KnowledgeDocument.enterprise_space_id == space_id,
        KnowledgeDocument.status != "deleted",
    )
    parsing = _scalar(
        db,
        select(func.count(KnowledgeDocument.id)).where(
            *base,
            KnowledgeDocument.status.in_(("parsing", "chunking", "indexing", "graph_indexing", "uploaded")),
        ),
    )
    indexed = _scalar(
        db,
        select(func.count(KnowledgeDocument.id)).where(
            *base,
            KnowledgeDocument.status.in_(("indexed", "graph_indexed")),
        ),
    )
    failed = _scalar(
        db,
        select(func.count(KnowledgeDocument.id)).where(
            *base,
            KnowledgeDocument.status.in_(("failed", "graph_failed")),
        ),
    )
    return {"parsing": parsing, "indexed": indexed, "failed": failed}


def _recent_audit_events(db: Session, space_id: int) -> list[dict[str, Any]]:
    items, _ = list_platform_audit_events(
        db,
        enterprise_space_id=space_id,
        skip=0,
        limit=8,
    )
    return [
        {
            "id": item.id,
            "action": item.action,
            "resource_type": item.resource_type,
            "resource_id": item.resource_id,
            "username": item.username,
            "message": item.message,
            "created_at": item.created_at,
        }
        for item in items
    ]


def get_top_chat_conversations(
    db: Session,
    *,
    space_id: int,
    range_key: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    from datetime import datetime

    from app.services.usage_metrics_service import UsageRange, get_range_start

    rk: UsageRange = range_key if range_key in ("24h", "7d", "30d") else "24h"
    start = get_range_start(datetime.utcnow(), rk)

    session_rows = db.execute(
        select(
            ChatSession.conversation_id,
            func.count(ChatSession.id),
        )
        .where(
            ChatSession.enterprise_space_id == space_id,
            ChatSession.created_at >= start,
        )
        .group_by(ChatSession.conversation_id)
    ).all()

    message_rows = db.execute(
        select(
            ChatSession.conversation_id,
            func.count(ChatMessage.id),
        )
        .join(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(
            ChatSession.enterprise_space_id == space_id,
            ChatMessage.created_at >= start,
        )
        .group_by(ChatSession.conversation_id)
    ).all()

    session_map = {str(cid): int(cnt) for cid, cnt in session_rows}
    message_map = {str(cid): int(cnt) for cid, cnt in message_rows}
    candidate_ids = set(session_map) | set(message_map)
    if not candidate_ids:
        return []

    conv_rows = db.execute(
        select(ChatConversation.id, ChatConversation.title).where(
            ChatConversation.enterprise_space_id == space_id,
            ChatConversation.id.in_(candidate_ids),
        )
    ).all()

    items: list[dict[str, Any]] = []
    for cid, title in conv_rows:
        key = str(cid)
        session_count = session_map.get(key, 0)
        message_count = message_map.get(key, 0)
        if session_count == 0 and message_count == 0:
            continue
        items.append(
            {
                "conversation_id": key,
                "title": (title or "未命名对话").strip() or "未命名对话",
                "session_count": session_count,
                "message_count": message_count,
            }
        )

    items.sort(key=lambda x: (x["message_count"], x["session_count"]), reverse=True)
    return items[:limit]


def _scalar(db: Session, stmt) -> int:
    value = db.execute(stmt).scalar_one()
    return int(value or 0)
