from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.enterprise_space_context import CurrentSpace, CurrentUser, get_membership
from app.core.membership_roles import SPACE_ADMIN
from app.db.session import get_db
from app.models.enterprise_space import EnterpriseSpace, Membership, User
from app.schemas.platform_audit import PlatformAuditEventListResponse, PlatformAuditEventResponse
from app.services.platform_audit_service import list_platform_audit_events, record_platform_audit

router = APIRouter(prefix="/platform-audit", tags=["platform-audit"])


def _require_space_admin_or_system(
    current_user: User,
    current_space: EnterpriseSpace,
    db: Session,
) -> Membership | None:
    """系统管理员直接放行；否则要求当前空间 space_admin。"""
    if current_user.is_admin:
        return get_membership(current_user, current_space, db)
    membership = get_membership(current_user, current_space, db)
    if membership is None or membership.role != SPACE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有企业空间管理员或系统管理员可以执行此操作",
        )
    return membership


@router.get("/events", response_model=PlatformAuditEventListResponse)
def list_audit_events(
    current_user: CurrentUser,
    current_space: CurrentSpace,
    db: Session = Depends(get_db),
    enterprise_space_id: int | None = Query(default=None, description="平台管理员可选，按企业空间筛选"),
    user_id: int | None = Query(default=None, description="按操作用户筛选"),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
) -> PlatformAuditEventListResponse:
    _require_space_admin_or_system(current_user, current_space, db)

    if current_user.is_admin:
        scoped_space_id = enterprise_space_id
        if scoped_space_id is not None and db.get(EnterpriseSpace, scoped_space_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="企业空间不存在")
    else:
        scoped_space_id = current_space.id

    items, total = list_platform_audit_events(
        db,
        enterprise_space_id=scoped_space_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        created_from=created_from,
        created_to=created_to,
        skip=skip,
        limit=limit,
    )
    return PlatformAuditEventListResponse(items=items, total=total, skip=skip, limit=limit)


@router.post("/events/test", response_model=PlatformAuditEventResponse, include_in_schema=False)
def create_test_audit_event(
    request: Request,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> PlatformAuditEventResponse:
    _require_space_admin_or_system(current_user, current_space, db)
    row = record_platform_audit(
        db,
        action="audit.test",
        resource_type="system",
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
        request_id=request.headers.get("X-Request-ID"),
        ip_address=request.client.host if request.client else None,
        message="audit pipeline smoke test",
    )
    db.commit()
    db.refresh(row)
    return PlatformAuditEventResponse.model_validate(row)
