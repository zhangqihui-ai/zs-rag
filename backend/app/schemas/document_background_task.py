from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DocumentBackgroundTaskResponse(BaseModel):
    id: int
    task_uid: str
    enterprise_space_id: int
    knowledge_base_id: int
    document_id: int
    action: str
    status: str
    retry_count: int
    max_retries: int
    error_message: str | None
    celery_task_id: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}
