from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PlatformAuditEventResponse(BaseModel):
    id: int
    enterprise_space_id: int | None
    user_id: int | None
    username: str | None = None
    space_name: str | None = None
    action: str
    resource_type: str
    resource_id: str | None
    request_id: str | None
    ip_address: str | None
    detail: dict | None
    message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PlatformAuditEventListResponse(BaseModel):
    items: list[PlatformAuditEventResponse]
    total: int
    skip: int
    limit: int
