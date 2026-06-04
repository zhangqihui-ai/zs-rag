"""Celery 应用与文档索引任务。"""

from __future__ import annotations

import logging

from celery import Celery
from celery.signals import worker_ready
from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import SessionLocal
from app.models.document_background_task import DocumentBackgroundTask
from app.services import document_background_task_service as bg
from app.services.document_process_tasks import DocumentProcessCancelled
from app.services.knowledge_document_service import execute_document_process_job

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "zs_rag",
    broker=settings.redis_url or "redis://localhost:6379/0",
    backend=settings.redis_url or "redis://localhost:6379/0",
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)


@worker_ready.connect
def _log_worker_document_parse_config(**_kwargs) -> None:
    s = get_settings()
    logger.info(
        "Celery worker document parse config: mineru_enabled=%s mineru_base_url=%s odl_enabled=%s",
        s.mineru_enabled,
        s.mineru_base_url,
        s.odl_enabled,
    )
    if not s.mineru_enabled:
        logger.warning(
            "MINERU_ENABLED=false：Celery worker 将跳过 MinerU，复杂 PDF 可能降级到 pypdf 并失败。"
            "请确保 celery-worker 与 backend 使用相同的 MinerU/ODL 环境变量。"
        )


@celery_app.task(name="index_document_background", bind=True, max_retries=0)
def index_document_background(
    self,
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
) -> dict:
    with SessionLocal() as db:
        row = db.execute(
            select(DocumentBackgroundTask).where(DocumentBackgroundTask.task_uid == task_uid)
        ).scalar_one_or_none()
        if row is None:
            return {"status": "missing", "task_uid": task_uid}
        if row.status == "completed":
            return {"status": "completed", "task_uid": task_uid}
        if row.status == "failed":
            return {"status": "failed", "task_uid": task_uid}
        if (
            row.status == "running"
            and row.celery_task_id
            and row.celery_task_id != self.request.id
        ):
            return {"status": "skipped", "task_uid": task_uid, "reason": "superseded"}
        bg.mark_task_running(db, row.id, celery_task_id=self.request.id)
        db.commit()
        task_id = row.id

    with SessionLocal() as db:
        try:
            execute_document_process_job(
                db,
                space_id=space_id,
                kb_id=kb_id,
                document_id=document_id,
                embedding_model_id=embedding_model_id,
                mode=mode,  # type: ignore[arg-type]
                force=force,
                user_id=user_id,
                batch_uid=batch_uid,
            )
            bg.mark_task_completed(db, task_id)
            db.commit()
            return {"status": "completed", "task_uid": task_uid}
        except DocumentProcessCancelled:
            bg.mark_task_failed(db, task_id, error_message="cancelled")
            db.commit()
            return {"status": "cancelled", "task_uid": task_uid}
        except AppError as exc:
            bg.mark_task_failed(db, task_id, error_message=exc.message)
            db.commit()
            return {"status": "failed", "task_uid": task_uid, "message": exc.message}
        except Exception as exc:
            bg.mark_task_failed(db, task_id, error_message=str(exc))
            db.commit()
            return {"status": "failed", "task_uid": task_uid, "message": str(exc)}
