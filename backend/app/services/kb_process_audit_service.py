from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

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
from app.services.platform_audit_service import record_platform_audit

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

_FAILED_DOC_STATUSES = (
    KnowledgeDocumentStatus.FAILED.value,
    KnowledgeDocumentStatus.GRAPH_FAILED.value,
)

_TERMINAL_ITEM_STATUSES = (
    KbProcessBatchItemStatus.SUCCESS.value,
    KbProcessBatchItemStatus.FAILED.value,
    KbProcessBatchItemStatus.CANCELLED.value,
)

_TERMINAL_BATCH_STATUSES = (
    KbProcessBatchStatus.SUCCESS.value,
    KbProcessBatchStatus.FAILED.value,
    KbProcessBatchStatus.PARTIAL_FAILED.value,
)

_PLATFORM_AUDIT_ACTIONS = {
    "upload": "knowledge_document.batch.upload",
    "parse": "knowledge_document.batch.parse",
    "reindex": "knowledge_document.batch.reindex",
    "delete": "knowledge_document.batch.delete",
    "cancel": "knowledge_document.batch.cancel",
}


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


def _batch_duration_seconds(
    batch: KbProcessBatch,
    items: list[KbProcessBatchItem] | None = None,
) -> float | None:
    """优先用明细项的起止时间（真实作业耗时），回退到批次级时间戳。"""
    if items:
        started_times = [item.started_at for item in items if item.started_at is not None]
        finished_times = [item.finished_at for item in items if item.finished_at is not None]
        if (
            started_times
            and len(finished_times) == len(items)
            and batch.status in _TERMINAL_BATCH_STATUSES
        ):
            return max(0.0, (max(finished_times) - min(started_times)).total_seconds())

    if batch.started_at is None:
        return None
    if batch.finished_at is not None:
        return max(0.0, (batch.finished_at - batch.started_at).total_seconds())
    if batch.status == KbProcessBatchStatus.RUNNING.value:
        return max(0.0, (_utcnow() - batch.started_at).total_seconds())
    return None


def format_duration_label(seconds: float | None, *, running: bool = False) -> str:
    if running and seconds is None:
        return "进行中"
    if seconds is None:
        return "—"
    if seconds < 1:
        return "不足 1 秒"
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours} 小时 {minutes} 分 {secs} 秒"
    if minutes > 0:
        return f"{minutes} 分 {secs} 秒"
    return f"{secs} 秒"


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
    _maybe_record_platform_audit(db, batch)


def _maybe_record_platform_audit(db: Session, batch: KbProcessBatch) -> None:
    if batch.status not in _TERMINAL_BATCH_STATUSES:
        return

    meta = batch.metadata_json if isinstance(batch.metadata_json, dict) else {}
    if meta.get("platform_audit_recorded"):
        return

    force = bool(meta.get("force"))
    username = str(meta.get("username") or _get_username(db, batch.user_id))
    action_label = _action_label(batch.action, total_count=batch.total_count, force=force)
    items = db.execute(
        select(KbProcessBatchItem).where(KbProcessBatchItem.batch_id == batch.id)
    ).scalars().all()
    duration_seconds = _batch_duration_seconds(batch, items)
    duration_label = format_duration_label(
        duration_seconds,
        running=batch.status == KbProcessBatchStatus.RUNNING.value,
    )
    summary = batch.summary or _build_summary(
        username=username,
        action=batch.action,
        total_count=batch.total_count,
        force=force,
    )
    message = summary
    if duration_label not in {"—", "进行中"}:
        message = f"{summary}（耗时 {duration_label}）"

    audit_action = _PLATFORM_AUDIT_ACTIONS.get(batch.action, f"knowledge_document.batch.{batch.action}")
    record_platform_audit(
        db,
        action=audit_action,
        resource_type="knowledge_document",
        resource_id=batch.knowledge_base_id,
        enterprise_space_id=batch.enterprise_space_id,
        user_id=batch.user_id,
        detail={
            "batch_id": batch.id,
            "batch_uid": batch.batch_uid,
            "knowledge_base_id": batch.knowledge_base_id,
            "action": batch.action,
            "action_label": action_label,
            "status": batch.status,
            "total_count": batch.total_count,
            "success_count": batch.success_count,
            "failed_count": batch.failed_count,
            "started_at": batch.started_at.isoformat() if batch.started_at else None,
            "finished_at": batch.finished_at.isoformat() if batch.finished_at else None,
            "duration_seconds": duration_seconds,
            "duration_label": duration_label,
            "summary": summary,
        },
        message=message,
    )
    meta = dict(meta)
    meta["platform_audit_recorded"] = True
    batch.metadata_json = meta


def _get_username(db: Session, user_id: int | None) -> str:
    if user_id is None:
        return "系统"
    user = db.get(User, user_id)
    if user is None:
        return "未知用户"
    return user.username


def _find_open_process_batch_item(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    document_id: int,
    action: str,
) -> tuple[KbProcessBatch, KbProcessBatchItem] | None:
    """begin 未传 batch_uid 时，complete 应复用同一进行中的批次，避免重复建批导致耗时为 0。"""
    item = db.execute(
        select(KbProcessBatchItem)
        .join(KbProcessBatch, KbProcessBatchItem.batch_id == KbProcessBatch.id)
        .where(
            KbProcessBatch.enterprise_space_id == space_id,
            KbProcessBatch.knowledge_base_id == kb_id,
            KbProcessBatch.action == action,
            KbProcessBatch.status == KbProcessBatchStatus.RUNNING.value,
            KbProcessBatchItem.document_id == document_id,
            KbProcessBatchItem.status == KbProcessBatchItemStatus.RUNNING.value,
        )
        .order_by(KbProcessBatchItem.started_at.desc(), KbProcessBatchItem.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if item is None:
        return None
    batch = db.get(KbProcessBatch, item.batch_id)
    if batch is None:
        return None
    return batch, item


def _load_batch_items_map(
    db: Session,
    batch_ids: list[int],
) -> dict[int, list[KbProcessBatchItem]]:
    if not batch_ids:
        return {}
    rows = db.execute(
        select(KbProcessBatchItem)
        .where(KbProcessBatchItem.batch_id.in_(batch_ids))
        .order_by(KbProcessBatchItem.started_at.asc(), KbProcessBatchItem.id.asc())
    ).scalars().all()
    grouped: dict[int, list[KbProcessBatchItem]] = {}
    for row in rows:
        grouped.setdefault(row.batch_id, []).append(row)
    return grouped


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


def record_delete_batch(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    user_id: int | None,
    batch_uid: str,
    items: list[dict[str, Any]],
) -> None:
    """批量删除完成后一次性写入审计批次。"""
    if not items:
        return
    batch = ensure_batch(
        db,
        space_id=space_id,
        kb_id=kb_id,
        user_id=user_id,
        action="delete",
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
    batch: KbProcessBatch | None = None
    if batch_uid:
        batch = ensure_batch(
            db,
            space_id=space_id,
            kb_id=kb_id,
            user_id=user_id,
            action=mode,
            batch_uid=batch_uid,
            force=force,
        )
    else:
        found = _find_open_process_batch_item(
            db,
            space_id=space_id,
            kb_id=kb_id,
            document_id=document_id,
            action=mode,
        )
        if found is not None:
            batch, _ = found
        else:
            batch = ensure_batch(
                db,
                space_id=space_id,
                kb_id=kb_id,
                user_id=user_id,
                action=mode,
                batch_uid=None,
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


def _infer_item_outcome_from_document(document: KnowledgeDocument | None) -> Literal["success", "failed", "cancelled"] | None:
    if document is None:
        return "failed"
    status = document.status
    if status in _INDEXED_STATUSES:
        return "success"
    if status in _FAILED_DOC_STATUSES:
        return "failed"
    if status == KnowledgeDocumentStatus.UPLOADED.value:
        return "cancelled"
    if status == KnowledgeDocumentStatus.DELETED.value:
        return "failed"
    return None


def reconcile_batch_running_items(db: Session, *, batch: KbProcessBatch) -> bool:
    """根据文档实际状态修正仍为 running 的审计明细（解析已完成但审计未收尾时）。"""
    items = db.execute(
        select(KbProcessBatchItem).where(
            KbProcessBatchItem.batch_id == batch.id,
            KbProcessBatchItem.status == KbProcessBatchItemStatus.RUNNING.value,
        )
    ).scalars().all()
    if not items:
        return False

    changed = False
    for item in items:
        if item.document_id is None:
            continue
        document = db.get(KnowledgeDocument, item.document_id)
        outcome = _infer_item_outcome_from_document(document)
        if outcome is None:
            continue
        finish_item(
            db,
            batch=batch,
            document_id=item.document_id,
            status=outcome,
            file_name=item.file_name,
            error_message=document.error_message if document and outcome == "failed" else None,
        )
        changed = True
        logger.info(
            "Reconciled process audit item batch_id=%s document_id=%s outcome=%s",
            batch.id,
            item.document_id,
            outcome,
        )

    if changed:
        _recompute_batch(db, batch)
    return changed


def reconcile_batch_by_uid(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    batch_uid: str,
) -> KbProcessBatch | None:
    batch = _find_batch_by_uid(db, space_id=space_id, kb_id=kb_id, batch_uid=batch_uid)
    if batch is None:
        return None
    if reconcile_batch_running_items(db, batch=batch):
        db.commit()
        db.refresh(batch)
    return batch


def complete_process_item_in_new_session(
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
    """解析线程在独立 Session 中收尾审计，避免长事务 Session 状态导致未提交。"""
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        complete_process_item(
            db,
            space_id=space_id,
            kb_id=kb_id,
            batch_uid=batch_uid,
            document_id=document_id,
            file_name=file_name,
            mode=mode,
            outcome=outcome,
            error_message=error_message,
            user_id=user_id,
            force=force,
        )


def finalize_process_audit_from_document(
    *,
    space_id: int,
    kb_id: int,
    batch_uid: str | None,
    document_id: int,
    file_name: str,
    mode: Literal["parse", "reindex"],
    user_id: int | None = None,
    force: bool = False,
) -> None:
    """worker 异常退出时按文档状态兜底写入审计终态。"""
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        document = db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.knowledge_base_id == kb_id,
                KnowledgeDocument.enterprise_space_id == space_id,
            )
        ).scalar_one_or_none()
        if document is None:
            logger.warning("finalize_process_audit: document %s not found", document_id)
            return
        outcome = _infer_item_outcome_from_document(document)
        if outcome is None:
            return
        complete_process_item(
            db,
            space_id=space_id,
            kb_id=kb_id,
            batch_uid=batch_uid,
            document_id=document_id,
            file_name=file_name or document.file_name,
            mode=mode,
            outcome=outcome,
            error_message=document.error_message if outcome == "failed" else None,
            user_id=user_id,
            force=force,
        )


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


def _serialize_batch(
    db: Session,
    batch: KbProcessBatch,
    *,
    items: list[KbProcessBatchItem] | None = None,
) -> dict[str, Any]:
    meta = batch.metadata_json if isinstance(batch.metadata_json, dict) else {}
    force = bool(meta.get("force"))
    username = _get_username(db, batch.user_id)
    running = batch.status == KbProcessBatchStatus.RUNNING.value
    if items is None:
        items = db.execute(
            select(KbProcessBatchItem).where(KbProcessBatchItem.batch_id == batch.id)
        ).scalars().all()
    duration_seconds = _batch_duration_seconds(batch, items)
    if duration_seconds is not None:
        duration_label = format_duration_label(duration_seconds)
    elif running:
        duration_label = "进行中"
    else:
        duration_label = "—"
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
        "duration_seconds": duration_seconds,
        "duration_label": duration_label,
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

    dirty = False
    for row in rows:
        if row.status == KbProcessBatchStatus.RUNNING.value or (
            row.success_count + row.failed_count < row.total_count
        ):
            if reconcile_batch_running_items(db, batch=row):
                dirty = True
    if dirty:
        db.commit()

    items_map = _load_batch_items_map(db, [row.id for row in rows])
    return {
        "items": [_serialize_batch(db, row, items=items_map.get(row.id, [])) for row in rows],
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

    if reconcile_batch_running_items(db, batch=batch):
        db.commit()
        db.refresh(batch)

    items = db.execute(
        select(KbProcessBatchItem)
        .where(KbProcessBatchItem.batch_id == batch.id)
        .order_by(KbProcessBatchItem.started_at.asc(), KbProcessBatchItem.id.asc())
    ).scalars().all()

    return {
        "batch": _serialize_batch(db, batch, items=items),
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
