"""平台级 audit_events 写入与查询。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.enterprise_space import EnterpriseSpace, User
from app.models.platform_audit import PlatformAuditEvent
from app.schemas.platform_audit import PlatformAuditEventResponse


def record_platform_audit(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    enterprise_space_id: int | None = None,
    user_id: int | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    detail: dict[str, Any] | None = None,
    message: str | None = None,
    commit: bool = False,
) -> PlatformAuditEvent:
    row = PlatformAuditEvent(
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        enterprise_space_id=enterprise_space_id,
        user_id=user_id,
        request_id=request_id,
        ip_address=ip_address,
        detail=detail,
        message=message,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    if commit:
        db.commit()
        db.refresh(row)
    return row


def _apply_audit_filters(
    stmt,
    *,
    enterprise_space_id: int | None = None,
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
):
    if enterprise_space_id is not None:
        stmt = stmt.where(PlatformAuditEvent.enterprise_space_id == enterprise_space_id)
    if user_id is not None:
        stmt = stmt.where(PlatformAuditEvent.user_id == user_id)
    if action:
        stmt = stmt.where(PlatformAuditEvent.action == action)
    if resource_type:
        stmt = stmt.where(PlatformAuditEvent.resource_type == resource_type)
    if created_from is not None:
        stmt = stmt.where(PlatformAuditEvent.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(PlatformAuditEvent.created_at <= created_to)
    return stmt


def list_platform_audit_events(
    db: Session,
    *,
    enterprise_space_id: int | None = None,
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[PlatformAuditEventResponse], int]:
    count_stmt = select(func.count()).select_from(PlatformAuditEvent)
    count_stmt = _apply_audit_filters(
        count_stmt,
        enterprise_space_id=enterprise_space_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        created_from=created_from,
        created_to=created_to,
    )
    total = int(db.execute(count_stmt).scalar_one())

    stmt = (
        select(
            PlatformAuditEvent,
            User.username,
            EnterpriseSpace.name,
        )
        .outerjoin(User, PlatformAuditEvent.user_id == User.id)
        .outerjoin(EnterpriseSpace, PlatformAuditEvent.enterprise_space_id == EnterpriseSpace.id)
    )
    stmt = _apply_audit_filters(
        stmt,
        enterprise_space_id=enterprise_space_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        created_from=created_from,
        created_to=created_to,
    )
    stmt = stmt.order_by(desc(PlatformAuditEvent.created_at)).offset(max(skip, 0)).limit(min(max(limit, 1), 200))
    rows = db.execute(stmt).all()

    items = [
        PlatformAuditEventResponse(
            id=event.id,
            enterprise_space_id=event.enterprise_space_id,
            user_id=event.user_id,
            username=username,
            space_name=space_name,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            request_id=event.request_id,
            ip_address=event.ip_address,
            detail=event.detail,
            message=event.message,
            created_at=event.created_at,
        )
        for event, username, space_name in rows
    ]
    return items, total
