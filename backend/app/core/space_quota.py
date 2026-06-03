"""企业空间级文档数与存储配额检查。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.knowledge_base import KnowledgeDocument, KnowledgeDocumentStatus


def get_space_usage(db: Session, *, space_id: int) -> dict[str, int]:
    row = db.execute(
        select(
            func.count(KnowledgeDocument.id),
            func.coalesce(func.sum(KnowledgeDocument.file_size), 0),
        ).where(
            KnowledgeDocument.enterprise_space_id == space_id,
            KnowledgeDocument.status != KnowledgeDocumentStatus.DELETED.value,
        )
    ).one()
    return {
        "document_count": int(row[0] or 0),
        "storage_bytes": int(row[1] or 0),
    }


def assert_space_upload_quota(
    db: Session,
    *,
    space_id: int,
    additional_bytes: int,
    is_new_document: bool,
) -> None:
    settings = get_settings()
    max_docs = int(settings.space_max_documents or 0)
    max_bytes = int(settings.space_max_storage_bytes or 0)
    if max_docs <= 0 and max_bytes <= 0:
        return

    usage = get_space_usage(db, space_id=space_id)
    if max_docs > 0 and is_new_document and usage["document_count"] >= max_docs:
        raise AppError(
            status_code=429,
            code="SPACE_DOCUMENT_QUOTA_EXCEEDED",
            message=f"企业空间文档数已达上限（{max_docs}）",
        )
    if max_bytes > 0 and usage["storage_bytes"] + max(0, additional_bytes) > max_bytes:
        raise AppError(
            status_code=429,
            code="SPACE_STORAGE_QUOTA_EXCEEDED",
            message="企业空间存储配额不足",
        )
