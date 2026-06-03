"""从 FastAPI Request 写入平台审计。"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.request_context import get_request_id
from app.services.platform_audit_service import record_platform_audit


def audit_action(
    db: Session,
    request: Request | None,
    *,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    enterprise_space_id: int | None = None,
    user_id: int | None = None,
    detail: dict[str, Any] | None = None,
    message: str | None = None,
) -> None:
    request_id = get_request_id() if request is None else request.headers.get("X-Request-ID") or get_request_id()
    ip_address = None
    if request is not None and request.client is not None:
        ip_address = request.client.host
    record_platform_audit(
        db,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        enterprise_space_id=enterprise_space_id,
        user_id=user_id,
        request_id=request_id,
        ip_address=ip_address,
        detail=detail,
        message=message,
    )
