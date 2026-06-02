from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.enterprise_space import User
from app.models.knowledge_base import (
    KbProcessBatch,
    KbProcessBatchItem,
    KbProcessBatchItemStatus,
    KbProcessBatchStatus,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
)
from app.services.knowledge_base_service import get_knowledge_base_or_error

ACTION_LABELS: dict[str, str] = {
    "upload": "上传",
    "parse": "解析",
    "reindex": "重建索引",
    "delete": "删除",
    "cancel": "取消解析",
}

_PROCESSING_STATUSES = (
    KnowledgeDocumentStatus.PARSING.value,
    KnowledgeDocumentStatus.CHUNKING.value,
    KnowledgeDocumentStatus.INDEXING.value,
    KnowledgeDocumentStatus.GRAPH_INDEXING.value,
)

_INDEXED_STATUSES = (
    KnowledgeDocumentStatus.INDEXED.value,
    KnowledgeDocumentStatus.GRAPH_INDEXED.value,
)

_TERMINAL_ITEM_STATUSES = (
    KbProcessBatchItemStatus.SUCCESS.value,
    KbProcessBatchItemStatus.FAILED.value,
    KbProcessBatchItemStatus.CANCELLED.value,
)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _action_label(action: str, *, total_count: int, force: bool = False) -> str:
    if action == "parse" and force:
        return "重新解析" if total_count <= 1 else "批量重新解析"
    if action == "reindex" and force:
        return "重新解析" if total_count <= 1 else "批量重新解析"
    if total_count > 1:
        if action == "parse":
            return "批量解析"
        if action == "reindex":
            return "批量重建索引"
        if action == "delete":
            return "批量删除"
        if action == "upload":
            return "批量上传"
    return ACTION_LABELS.get(action, action)


def _build_summary(*, username: str, action: str, total_count: int, force: bool = False) -> str:
    label = _action_label(action, total_count=total_count, force=force)
    if total_count > 1:
        return f"{username} {label} {total_count} 个文档"
    if action == "delete":
        return f"{username} 删除了 1 个文档"
    if action == "upload":
        return f"{username} 上传了 1 个文档"
    if action == "cancel":
        return f"{username} 取消了解析"
    return f"{username} {label} 1 个文档"


def _recompute_batch(db: Session, batch: KbProcessBatch) -> None:
    items = db.execute(
        select(KbProcessBatchItem).where(KbProcessBatchItem.batch_id == batch.id)
    ).scalars().all()
    if not items:
        return

    running = 0
    success = 0
    failed = 0
    finished_times: list[datetime] = []
    for item in items:
        if item.status == KbProcessBatchItemStatus.RUNNING.value:
            running += 1
        elif item.status == KbProcessBatchItemStatus.SUCCESS.value:
            success += 1
            if item.finished_at:
                finished_times.append(item.finished_at)
        else:
            failed += 1
            if item.finished_at:
                finished_times.append(item.finished_at)

    batch.total_count = len(items)
    batch.success_count = success
    batch.failed_count = failed

    if running > 0:
        batch.status = KbProcessBatchStatus.RUNNING.value
        batch.finished_at = None
    elif failed == len(items):
        batch.status = KbProcessBatchStatus.FAILED.value
        batch.finished_at = max(finished_times) if finished_times else _utcnow()
    elif success == len(items):
        batch.status = KbProcessBatchStatus.SUCCESS.value
        batch.finished_at = max(finished_times) if finished_times else _utcnow()
    else:
        batch.status = KbProcessBatchStatus.PARTIAL_FAILED.value
        batch.finished_at = max(finished_times) if finished_times else _utcnow()

    meta = batch.metadata_json if isinstance(batch.metadata_json, dict) else {}
    force = bool(meta.get("force"))
    username = meta.get("username") or "用户"
    batch.summary = _build_summary(
        username=str(username),
        action=batch.action,
        total_count=batch.total_count,
        force=force,
    )


def _get_username(db: Session, user_id: int | None) -> str:
    if user_id is None:
        return "系统"
    user = db.get(User, user_id)
    if user is None:
        return "未知用户"
    return user.username


def _find_batch_by_uid(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    batch_uid: str,
) -> KbProcessBatch | None:
    return db.execute(
        select(KbProcessBatch).where(
            KbProcessBatch.batch_uid == batch_uid,
            KbProcessBatch.knowledge_base_id == kb_id,
            KbProcessBatch.enterprise_space_id == space_id,
        )
    ).scalar_one_or_none()


def ensure_batch(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    user_id: int | None,
    action: Literal["upload", "parse", "reindex", "delete", "cancel"],
    batch_uid: str | None = None,
    force: bool = False,
) -> KbProcessBatch:
    get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)
    username = _get_username(db, user_id)

    if batch_uid:
        existing = _find_batch_by_uid(db, space_id=space_id, kb_id=kb_id, batch_uid=batch_uid)
        if existing is not None:
            return existing

    resolved_uid = batch_uid or str(uuid4())
    batch = KbProcessBatch(
        batch_uid=resolved_uid,
        enterprise_space_id=space_id,
        knowledge_base_id=kb_id,
        user_id=user_id,
        action=action,
        status=KbProcessBatchStatus.RUNNING.value,
        metadata_json={"force": force, "username": username},
        started_at=_utcnow(),
    )
    db.add(batch)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if batch_uid:
            existing = _find_batch_by_uid(db, space_id=space_id, kb_id=kb_id, batch_uid=batch_uid)
            if existing is not None:
                return existing
        raise
    return batch


def start_process_batch(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    user_id: int | None,
    batch_uid: str,
    action: Literal["parse", "reindex", "delete"],
    force: bool = False,
) -> KbProcessBatch:
    """批量操作开始前预创建批次，避免并发解析/删除各自新建重复批次。"""
    batch = ensure_batch(
        db,
        space_id=space_id,
        kb_id=kb_id,
        user_id=user_id,
        action=action,
        batch_uid=batch_uid,
        force=force,
    )
    db.commit()
    return batch


def start_item(
    db: Session,
    *,
    batch: KbProcessBatch,
    document_id: int | None,
    file_name: str,
) -> KbProcessBatchItem:
    if document_id is not None:
        existing = db.execute(
            select(KbProcessBatchItem).where(
                KbProcessBatchItem.batch_id == batch.id,
                KbProcessBatchItem.document_id == document_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.file_name = file_name
            existing.status = KbProcessBatchItemStatus.RUNNING.value
            existing.error_message = None
            existing.started_at = _utcnow()
            existing.finished_at = None
            _recompute_batch(db, batch)
            return existing

    item = KbProcessBatchItem(
        batch_id=batch.id,
        document_id=document_id,
        file_name=file_name,
        status=KbProcessBatchItemStatus.RUNNING.value,
        started_at=_utcnow(),
    )
    db.add(item)
    db.flush()
    _recompute_batch(db, batch)
    return item


def finish_item(
    db: Session,
    *,
    batch: KbProcessBatch,
    document_id: int | None,
    status: Literal["success", "failed", "cancelled"],
    error_message: str | None = None,
    file_name: str | None = None,
) -> None:
    query = select(KbProcessBatchItem).where(KbProcessBatchItem.batch_id == batch.id)
    if document_id is not None:
        query = query.where(KbProcessBatchItem.document_id == document_id)
    else:
        query = query.order_by(KbProcessBatchItem.id.desc())

    item = db.execute(query).scalar_one_or_none()
    if item is None:
        item = KbProcessBatchItem(
            batch_id=batch.id,
            document_id=document_id,
            file_name=file_name or "未知文档",
            status=KbProcessBatchItemStatus.RUNNING.value,
            started_at=_utcnow(),
        )
        db.add(item)
        db.flush()

    if file_name:
        item.file_name = file_name
    item.status = status
    item.error_message = error_message
    item.finished_at = _utcnow()
    _recompute_batch(db, batch)


def record_upload(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    user_id: int | None,
    document_id: int,
    file_name: str,
    batch_uid: str | None = None,
    skipped: bool = False,
) -> None:
    if skipped:
        return
    batch = ensure_batch(
        db,
        space_id=space_id,
        kb_id=kb_id,
        user_id=user_id,
        action="upload",
        batch_uid=batch_uid,
    )
    start_item(db, batch=batch, document_id=document_id, file_name=file_name)
    finish_item(db, batch=batch, document_id=document_id, status="success", file_name=file_name)
    db.commit()


def record_upload_batch(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    user_id: int | None,
    batch_uid: str,
    items: list[dict[str, Any]],
) -> None:
    """批量上传完成后一次性写入审计批次，避免每个文件单独带 batch_id 上传。"""
    if not items:
        return
    batch = ensure_batch(
        db,
        space_id=space_id,
        kb_id=kb_id,
        user_id=user_id,
        action="upload",
        batch_uid=batch_uid,
    )
    for item in items:
        document_id = item.get("document_id")
        file_name = str(item.get("file_name") or "未知文档")
        if not isinstance(document_id, int):
            continue
        start_item(db, batch=batch, document_id=document_id, file_name=file_name)
        finish_item(
            db,
            batch=batch,
            document_id=document_id,
            status="success",
            file_name=file_name,
        )
    db.commit()


def record_delete(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    user_id: int | None,
    document_id: int,
    file_name: str,
    batch_uid: str | None = None,
) -> None:
    batch = ensure_batch(
        db,
        space_id=space_id,
        kb_id=kb_id,
        user_id=user_id,
        action="delete",
        batch_uid=batch_uid,
    )
    start_item(db, batch=batch, document_id=document_id, file_name=file_name)
    finish_item(db, batch=batch, document_id=document_id, status="success", file_name=file_name)
    db.commit()


def record_cancel(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    user_id: int | None,
    document_id: int,
    file_name: str,
) -> None:
    batch = ensure_batch(
        db,
        space_id=space_id,
        kb_id=kb_id,
        user_id=user_id,
        action="cancel",
    )
    start_item(db, batch=batch, document_id=document_id, file_name=file_name)
    finish_item(db, batch=batch, document_id=document_id, status="cancelled", file_name=file_name)
    db.commit()


def begin_process_item(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    user_id: int | None,
    document_id: int,
    file_name: str,
    mode: Literal["parse", "reindex"],
    batch_uid: str | None = None,
    force: bool = False,
) -> KbProcessBatch:
    batch = ensure_batch(
        db,
        space_id=space_id,
        kb_id=kb_id,
        user_id=user_id,
        action=mode,
        batch_uid=batch_uid,
        force=force,
    )
    start_item(db, batch=batch, document_id=document_id, file_name=file_name)
    db.commit()
    return batch


def complete_process_item(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    batch_uid: str | None,
    document_id: int,
    file_name: str,
    mode: Literal["parse", "reindex"],
    outcome: Literal["success", "failed", "cancelled"],
    error_message: str | None = None,
    user_id: int | None = None,
    force: bool = False,
) -> None:
    batch = ensure_batch(
        db,
        space_id=space_id,
        kb_id=kb_id,
        user_id=user_id,
        action=mode,
        batch_uid=batch_uid,
        force=force,
    )
    finish_item(
        db,
        batch=batch,
        document_id=document_id,
        status=outcome,
        error_message=error_message,
        file_name=file_name,
    )
    db.commit()


def get_process_log_summary(db: Session, *, space_id: int, kb_id: int) -> dict[str, Any]:
    get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)
    doc_base = (
        KnowledgeDocument.knowledge_base_id == kb_id,
        KnowledgeDocument.enterprise_space_id == space_id,
        KnowledgeDocument.status != KnowledgeDocumentStatus.DELETED.value,
    )

    total_documents = db.scalar(select(func.count(KnowledgeDocument.id)).where(*doc_base)) or 0
    indexed_documents = db.scalar(
        select(func.count(KnowledgeDocument.id)).where(
            *doc_base,
            KnowledgeDocument.status.in_(_INDEXED_STATUSES),
        )
    ) or 0
    processing_documents = db.scalar(
        select(func.count(KnowledgeDocument.id)).where(
            *doc_base,
            KnowledgeDocument.status.in_(_PROCESSING_STATUSES),
        )
    ) or 0

    since = _utcnow() - timedelta(hours=24)
    recent_item_base = (
        KbProcessBatch.knowledge_base_id == kb_id,
        KbProcessBatch.enterprise_space_id == space_id,
        KbProcessBatch.action.in_(("parse", "reindex")),
        KbProcessBatchItem.finished_at.isnot(None),
        KbProcessBatchItem.finished_at >= since,
        KbProcessBatchItem.status.in_(_TERMINAL_ITEM_STATUSES),
    )

    recent_success = db.scalar(
        select(func.count(KbProcessBatchItem.id))
        .select_from(KbProcessBatchItem)
        .join(KbProcessBatch, KbProcessBatchItem.batch_id == KbProcessBatch.id)
        .where(*recent_item_base, KbProcessBatchItem.status == KbProcessBatchItemStatus.SUCCESS.value)
    ) or 0
    recent_failed = db.scalar(
        select(func.count(KbProcessBatchItem.id))
        .select_from(KbProcessBatchItem)
        .join(KbProcessBatch, KbProcessBatchItem.batch_id == KbProcessBatch.id)
        .where(
            *recent_item_base,
            KbProcessBatchItem.status.in_(
                (KbProcessBatchItemStatus.FAILED.value, KbProcessBatchItemStatus.CANCELLED.value)
            ),
        )
    ) or 0

    return {
        "total_documents": total_documents,
        "indexed_documents": indexed_documents,
        "processing_documents": processing_documents,
        "recent_24h_success": recent_success,
        "recent_24h_failed": recent_failed,
    }


def _serialize_batch(db: Session, batch: KbProcessBatch) -> dict[str, Any]:
    meta = batch.metadata_json if isinstance(batch.metadata_json, dict) else {}
    force = bool(meta.get("force"))
    username = _get_username(db, batch.user_id)
    return {
        "id": batch.id,
        "batch_uid": batch.batch_uid,
        "username": username,
        "action": batch.action,
        "action_label": _action_label(batch.action, total_count=batch.total_count, force=force),
        "status": batch.status,
        "total_count": batch.total_count,
        "success_count": batch.success_count,
        "failed_count": batch.failed_count,
        "started_at": batch.started_at,
        "finished_at": batch.finished_at,
        "summary": batch.summary or _build_summary(
            username=username,
            action=batch.action,
            total_count=batch.total_count,
            force=force,
        ),
    }


def list_process_log_events(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
) -> dict[str, Any]:
    get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    filters = [
        KbProcessBatch.knowledge_base_id == kb_id,
        KbProcessBatch.enterprise_space_id == space_id,
    ]
    if action:
        filters.append(KbProcessBatch.action == action)
    if status:
        filters.append(KbProcessBatch.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        filters.append(
            or_(
                KbProcessBatch.summary.ilike(like),
                KbProcessBatch.batch_uid.ilike(like),
                KbProcessBatch.id.in_(
                    select(KbProcessBatchItem.batch_id).where(KbProcessBatchItem.file_name.ilike(like))
                ),
                KbProcessBatch.user_id.in_(select(User.id).where(User.username.ilike(like))),
            )
        )

    total = db.scalar(select(func.count(KbProcessBatch.id)).where(*filters)) or 0
    rows = db.execute(
        select(KbProcessBatch)
        .where(*filters)
        .order_by(KbProcessBatch.started_at.desc(), KbProcessBatch.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return {
        "items": [_serialize_batch(db, row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_process_log_batch_items(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    batch_id: int,
) -> dict[str, Any]:
    batch = db.execute(
        select(KbProcessBatch).where(
            KbProcessBatch.id == batch_id,
            KbProcessBatch.knowledge_base_id == kb_id,
            KbProcessBatch.enterprise_space_id == space_id,
        )
    ).scalar_one_or_none()
    if batch is None:
        raise AppError(status_code=404, code="BATCH_NOT_FOUND", message="批次不存在")

    items = db.execute(
        select(KbProcessBatchItem)
        .where(KbProcessBatchItem.batch_id == batch.id)
        .order_by(KbProcessBatchItem.started_at.asc(), KbProcessBatchItem.id.asc())
    ).scalars().all()

    return {
        "batch": _serialize_batch(db, batch),
        "items": [
            {
                "id": item.id,
                "document_id": item.document_id,
                "file_name": item.file_name,
                "status": item.status,
                "error_message": item.error_message,
                "started_at": item.started_at,
                "finished_at": item.finished_at,
            }
            for item in items
        ],
    }
