from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class KbProcessLogSummaryResponse(BaseModel):
    total_documents: int
    indexed_documents: int
    processing_documents: int
    recent_24h_success: int
    recent_24h_failed: int


class KbProcessLogEventResponse(BaseModel):
    id: int
    batch_uid: str
    username: str
    action: str
    action_label: str
    status: str
    total_count: int
    success_count: int
    failed_count: int
    started_at: datetime
    finished_at: datetime | None
    summary: str


class KbProcessLogEventListResponse(BaseModel):
    items: list[KbProcessLogEventResponse]
    total: int
    page: int
    page_size: int


class KbProcessLogBatchItemResponse(BaseModel):
    id: int
    document_id: int | None
    file_name: str
    status: str
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class KbProcessLogBatchItemsResponse(BaseModel):
    batch: KbProcessLogEventResponse
    items: list[KbProcessLogBatchItemResponse]


class UploadBatchAuditItemRequest(BaseModel):
    document_id: int = Field(..., ge=1)
    file_name: str = Field(..., min_length=1, max_length=255)


class UploadBatchAuditRequest(BaseModel):
    batch_uid: str = Field(..., min_length=8, max_length=64)
    items: list[UploadBatchAuditItemRequest] = Field(..., min_length=1)


class StartProcessBatchRequest(BaseModel):
    batch_uid: str = Field(..., min_length=8, max_length=64)
    action: Literal["parse", "reindex", "delete"]
    force: bool = False
