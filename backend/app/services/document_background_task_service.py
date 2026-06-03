"""文档索引后台任务：DB 持久化 + 可选 Celery 分发。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document_background_task import DocumentBackgroundTask

logger = logging.getLogger(__name__)


def create_document_background_task(
    db: Session,
    *,
    enterprise_space_id: int,
    knowledge_base_id: int,
    document_id: int,
    action: str,
) -> DocumentBackgroundTask:
    row = DocumentBackgroundTask(
        task_uid=uuid.uuid4().hex,
        enterprise_space_id=enterprise_space_id,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        action=action,
        status="pending",
    )
    db.add(row)
    db.flush()
    return row


def mark_task_running(db: Session, task_id: int, *, celery_task_id: str | None = None) -> None:
    row = db.get(DocumentBackgroundTask, task_id)
    if row is None:
        return
    row.status = "running"
    row.started_at = datetime.utcnow()
    if celery_task_id:
        row.celery_task_id = celery_task_id
    db.flush()


def mark_task_completed(db: Session, task_id: int) -> None:
    row = db.get(DocumentBackgroundTask, task_id)
    if row is None:
        return
    row.status = "completed"
    row.finished_at = datetime.utcnow()
    row.error_message = None
    db.flush()


def mark_task_failed(db: Session, task_id: int, *, error_message: str) -> None:
    row = db.get(DocumentBackgroundTask, task_id)
    if row is None:
        return
    row.status = "failed"
    row.finished_at = datetime.utcnow()
    row.error_message = error_message[:2000]
    db.flush()


def list_document_background_tasks(
    db: Session,
    *,
    enterprise_space_id: int,
    knowledge_base_id: int | None = None,
    limit: int = 50,
) -> list[DocumentBackgroundTask]:
    stmt = (
        select(DocumentBackgroundTask)
        .where(DocumentBackgroundTask.enterprise_space_id == enterprise_space_id)
        .order_by(DocumentBackgroundTask.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    if knowledge_base_id is not None:
        stmt = stmt.where(DocumentBackgroundTask.knowledge_base_id == knowledge_base_id)
    return list(db.execute(stmt).scalars().all())


def celery_enabled() -> bool:
    settings = get_settings()
    return bool(settings.celery_enabled and settings.redis_url)


def revoke_celery_task(celery_task_id: str | None) -> None:
    if not celery_task_id:
        return
    try:
        from app.worker.tasks import celery_app

        celery_app.control.revoke(celery_task_id, terminate=True, signal="SIGTERM")
    except Exception:
        logger.exception("Failed to revoke Celery task %s", celery_task_id)


def get_background_task_or_none(db: Session, task_id: int) -> DocumentBackgroundTask | None:
    return db.get(DocumentBackgroundTask, task_id)


def try_dispatch_celery_index_task(
    *,
    task_uid: str,
    space_id: int,
    kb_id: int,
    document_id: int,
    mode: str,
    embedding_model_id: int | None,
    user_id: int | None,
    batch_uid: str | None,
    force: bool,
) -> str | None:
    if not celery_enabled():
        return None
    try:
        from app.worker.tasks import index_document_background

        async_result = index_document_background.delay(
            task_uid=task_uid,
            space_id=space_id,
            kb_id=kb_id,
            document_id=document_id,
            mode=mode,
            embedding_model_id=embedding_model_id,
            user_id=user_id,
            batch_uid=batch_uid,
            force=force,
        )
        return async_result.id
    except Exception:
        logger.exception("Celery dispatch failed, fallback to in-process thread")
        return None
